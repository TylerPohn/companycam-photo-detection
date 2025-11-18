"""Processing job service for database operations"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from src.models.processing_job import ProcessingJob, ProcessingStatus

logger = logging.getLogger(__name__)


class ProcessingJobService:
    """Service for managing processing job database operations"""

    @staticmethod
    def create_job(
        db: Session,
        photo_id: UUID,
        queue_name: str,
        message_id: str,
        status: str = ProcessingStatus.QUEUED,
    ) -> ProcessingJob:
        """
        Create a new processing job record.

        Args:
            db: Database session
            photo_id: UUID of the photo
            queue_name: Name of the queue
            message_id: SQS message ID
            status: Initial status (default: queued)

        Returns:
            Created ProcessingJob instance
        """
        job = ProcessingJob(
            photo_id=photo_id,
            queue_name=queue_name,
            message_id=message_id,
            status=status,
            retry_count=0,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        logger.info(f"Created processing job {job.id} for photo {photo_id}")
        return job

    @staticmethod
    def update_status(
        db: Session,
        job_id: UUID,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[ProcessingJob]:
        """
        Update processing job status.

        Args:
            db: Database session
            job_id: Processing job ID
            status: New status
            error_message: Optional error message

        Returns:
            Updated ProcessingJob or None if not found
        """
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            logger.error(f"Processing job {job_id} not found")
            return None

        job.status = status

        # Set timestamps based on status
        if status == ProcessingStatus.RECEIVED or status == ProcessingStatus.PROCESSING:
            if not job.started_at:
                job.started_at = datetime.utcnow()
        elif status == ProcessingStatus.COMPLETED or status == ProcessingStatus.FAILED:
            job.completed_at = datetime.utcnow()

            # Calculate processing time
            if job.started_at and job.completed_at:
                processing_time = (job.completed_at - job.started_at).total_seconds() * 1000
                job.processing_time_ms = int(processing_time)

        if error_message:
            job.error_message = error_message

        db.commit()
        db.refresh(job)

        logger.info(f"Updated processing job {job_id} status to {status}")
        return job

    @staticmethod
    def mark_received(db: Session, job_id: UUID) -> Optional[ProcessingJob]:
        """Mark job as received by worker"""
        return ProcessingJobService.update_status(
            db, job_id, ProcessingStatus.RECEIVED
        )

    @staticmethod
    def mark_processing(db: Session, job_id: UUID) -> Optional[ProcessingJob]:
        """Mark job as currently processing"""
        return ProcessingJobService.update_status(
            db, job_id, ProcessingStatus.PROCESSING
        )

    @staticmethod
    def mark_completed(db: Session, job_id: UUID) -> Optional[ProcessingJob]:
        """Mark job as successfully completed"""
        return ProcessingJobService.update_status(
            db, job_id, ProcessingStatus.COMPLETED
        )

    @staticmethod
    def mark_failed(
        db: Session, job_id: UUID, error_message: str
    ) -> Optional[ProcessingJob]:
        """Mark job as failed with error message"""
        return ProcessingJobService.update_status(
            db, job_id, ProcessingStatus.FAILED, error_message=error_message
        )

    @staticmethod
    def increment_retry_count(db: Session, job_id: UUID) -> Optional[ProcessingJob]:
        """
        Increment retry count for a job.

        Args:
            db: Database session
            job_id: Processing job ID

        Returns:
            Updated ProcessingJob or None if not found
        """
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            logger.error(f"Processing job {job_id} not found")
            return None

        job.retry_count += 1
        db.commit()
        db.refresh(job)

        logger.info(f"Incremented retry count for job {job_id} to {job.retry_count}")
        return job

    @staticmethod
    def get_job_by_message_id(
        db: Session, message_id: str
    ) -> Optional[ProcessingJob]:
        """
        Get processing job by message ID.

        Args:
            db: Database session
            message_id: SQS message ID

        Returns:
            ProcessingJob or None if not found
        """
        return (
            db.query(ProcessingJob)
            .filter(ProcessingJob.message_id == message_id)
            .first()
        )

    @staticmethod
    def get_job_by_photo_id(db: Session, photo_id: UUID) -> Optional[ProcessingJob]:
        """
        Get latest processing job for a photo.

        Args:
            db: Database session
            photo_id: Photo UUID

        Returns:
            Most recent ProcessingJob or None if not found
        """
        return (
            db.query(ProcessingJob)
            .filter(ProcessingJob.photo_id == photo_id)
            .order_by(ProcessingJob.created_at.desc())
            .first()
        )

    @staticmethod
    def get_failed_jobs(db: Session, limit: int = 100) -> list[ProcessingJob]:
        """
        Get failed processing jobs for analysis.

        Args:
            db: Database session
            limit: Maximum number of jobs to return

        Returns:
            List of failed ProcessingJob instances
        """
        return (
            db.query(ProcessingJob)
            .filter(ProcessingJob.status == ProcessingStatus.FAILED)
            .order_by(ProcessingJob.created_at.desc())
            .limit(limit)
            .all()
        )
