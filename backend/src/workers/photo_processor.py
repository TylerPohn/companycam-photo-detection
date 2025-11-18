"""Photo processor worker for async message processing"""

import logging
import json
import signal
import sys
from typing import Optional, Dict
from datetime import datetime

from src.config import settings
from src.database import get_db
from src.services.queue_service import QueueService
from src.services.processing_job_service import ProcessingJobService
from src.models.processing_job import ProcessingStatus
from src.models.photo import Photo, PhotoStatus
from src.schemas.processing_job import PhotoDetectionMessage
from src.workers.retry_manager import RetryManager

logger = logging.getLogger(__name__)


class PhotoProcessor:
    """
    Worker service for processing photo detection messages from SQS queues.

    Responsibilities:
    - Consume messages from priority queues
    - Validate message schema
    - Update database with processing status
    - Trigger detection processing (placeholder for now)
    - Handle errors and retry logic
    - Send messages to DLQ on failure
    """

    def __init__(
        self,
        priority: str = QueueService.PRIORITY_NORMAL,
        max_workers: int = 4,
        poll_interval: int = 20,
    ):
        """
        Initialize photo processor worker.

        Args:
            priority: Queue priority to consume from (high, normal, low)
            max_workers: Number of concurrent workers (default: 4)
            poll_interval: Long polling interval in seconds (default: 20)
        """
        self.priority = priority
        self.max_workers = max_workers
        self.poll_interval = poll_interval
        self.running = False

        # Initialize services
        self.queue_service = QueueService()
        self.retry_manager = RetryManager()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info(
            f"Initialized PhotoProcessor for {priority} priority queue "
            f"with {max_workers} workers"
        )

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def process_message(self, message: Dict) -> bool:
        """
        Process a single SQS message.

        Args:
            message: SQS message dictionary

        Returns:
            True if processed successfully, False otherwise
        """
        message_id = message.get("MessageId", "unknown")
        receipt_handle = message.get("ReceiptHandle")

        logger.info(f"Processing message {message_id} from {self.priority} queue")

        try:
            # Parse message body
            body = json.loads(message.get("Body", "{}"))

            # Add message_id to body for validation
            body["message_id"] = message_id

            # Validate message schema
            validated_message = self.queue_service.validate_message(body)
            if not validated_message:
                logger.error(f"Invalid message schema for {message_id}, sending to DLQ")
                # Don't delete - let it go to DLQ after max retries
                return False

            # Get database session
            db = next(get_db())
            try:
                # Create or get processing job
                job = ProcessingJobService.get_job_by_message_id(db, message_id)
                if not job:
                    job = ProcessingJobService.create_job(
                        db=db,
                        photo_id=validated_message.photo_id,
                        queue_name=f"{self.priority}-priority-queue",
                        message_id=message_id,
                        status=ProcessingStatus.QUEUED,
                    )

                # Update status to received
                ProcessingJobService.mark_received(db, job.id)

                # Process the photo
                success = self._process_photo_detection(db, validated_message, job.id)

                if success:
                    # Mark as completed
                    ProcessingJobService.mark_completed(db, job.id)

                    # Update photo status
                    photo = db.query(Photo).filter(Photo.id == validated_message.photo_id).first()
                    if photo:
                        photo.status = PhotoStatus.COMPLETED

                    db.commit()

                    # Delete message from queue
                    self.queue_service.delete_message(receipt_handle, self.priority)
                    logger.info(f"Successfully processed message {message_id}")
                    return True
                else:
                    # Increment retry count
                    ProcessingJobService.increment_retry_count(db, job.id)

                    # Check if we should retry
                    if job.retry_count >= self.retry_manager.max_retries - 1:
                        # Max retries reached, mark as failed
                        ProcessingJobService.mark_failed(
                            db, job.id, "Max retries exceeded"
                        )
                        logger.error(f"Max retries exceeded for message {message_id}")

                    # Don't delete - let SQS retry or move to DLQ
                    return False

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error processing message {message_id}: {e}", exc_info=True)
            # Don't delete message - let it retry or go to DLQ
            return False

    def _process_photo_detection(
        self, db, message: PhotoDetectionMessage, job_id
    ) -> bool:
        """
        Process photo detection request.

        This is a placeholder for the actual detection pipeline.
        In the full implementation, this would:
        1. Download photo from S3
        2. Run detection models
        3. Store detection results
        4. Update photo metadata

        Args:
            db: Database session
            message: Validated detection message
            job_id: Processing job ID

        Returns:
            True if successful, False otherwise
        """
        try:
            # Update status to processing
            ProcessingJobService.mark_processing(db, job_id)

            logger.info(
                f"Processing photo {message.photo_id} with detection types: "
                f"{message.detection_types}"
            )

            # TODO: Implement actual detection pipeline
            # For now, this is a placeholder that simulates processing

            # Simulate detection processing
            # In real implementation:
            # 1. Download photo from S3 using message.s3_url
            # 2. Run detection models based on message.detection_types
            # 3. Store detection results in database
            # 4. Generate bounding boxes and confidence scores

            logger.info(
                f"Photo {message.photo_id} detection processing completed "
                f"(placeholder implementation)"
            )

            return True

        except Exception as e:
            error_msg = f"Detection processing failed: {str(e)}"
            logger.error(error_msg, exc_info=True)

            # Check if error is transient
            if not self.retry_manager.is_transient_error(e):
                # Permanent error - mark as failed immediately
                ProcessingJobService.mark_failed(db, job_id, error_msg)
                db.commit()

            return False

    def start(self):
        """
        Start the worker to consume and process messages.

        This runs in an infinite loop, polling the queue and processing messages.
        """
        self.running = True
        logger.info(
            f"Starting PhotoProcessor worker for {self.priority} priority queue"
        )

        consecutive_errors = 0
        max_consecutive_errors = 10

        while self.running:
            try:
                # Receive messages from queue
                messages = self.queue_service.receive_messages(
                    priority=self.priority,
                    max_messages=self.max_workers,
                    wait_time_seconds=self.poll_interval,
                )

                if not messages:
                    # No messages, continue polling
                    consecutive_errors = 0
                    continue

                logger.info(
                    f"Received {len(messages)} messages from {self.priority} queue"
                )

                # Process each message
                for message in messages:
                    if not self.running:
                        logger.info("Worker shutting down, stopping message processing")
                        break

                    try:
                        self.process_message(message)
                        consecutive_errors = 0
                    except Exception as e:
                        logger.error(f"Error processing message: {e}", exc_info=True)
                        consecutive_errors += 1

                        if consecutive_errors >= max_consecutive_errors:
                            logger.critical(
                                f"Too many consecutive errors ({consecutive_errors}), "
                                "shutting down worker"
                            )
                            self.running = False
                            break

            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {e}", exc_info=True)
                consecutive_errors += 1

                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(
                        f"Too many consecutive errors ({consecutive_errors}), "
                        "shutting down worker"
                    )
                    self.running = False
                    break

        logger.info("PhotoProcessor worker stopped")

    def get_health_status(self) -> Dict:
        """
        Get health status of the worker.

        Returns:
            Dictionary with worker health information
        """
        metrics = self.queue_service.get_queue_metrics(self.priority)

        return {
            "status": "running" if self.running else "stopped",
            "priority": self.priority,
            "max_workers": self.max_workers,
            "poll_interval": self.poll_interval,
            "queue_metrics": metrics,
            "timestamp": datetime.utcnow().isoformat(),
        }


def main():
    """
    Main entry point for running the worker as a standalone process.

    Usage:
        python -m src.workers.photo_processor --priority normal
    """
    import argparse

    parser = argparse.ArgumentParser(description="Photo Detection Worker")
    parser.add_argument(
        "--priority",
        type=str,
        default="normal",
        choices=["high", "normal", "low"],
        help="Queue priority to process (default: normal)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of concurrent workers (default: 4)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=20,
        help="Long polling interval in seconds (default: 20)",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Create and start worker
    worker = PhotoProcessor(
        priority=args.priority,
        max_workers=args.workers,
        poll_interval=args.poll_interval,
    )

    try:
        worker.start()
    except Exception as e:
        logger.error(f"Worker failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
