"""Unit tests for Processing Job Service"""

import pytest
from datetime import datetime
from uuid import uuid4

from src.services.processing_job_service import ProcessingJobService
from src.models.processing_job import ProcessingJob, ProcessingStatus


class TestProcessingJobService:
    """Test processing job service operations"""

    def test_create_job(self, db_session):
        """Test creating a new processing job"""
        photo_id = uuid4()
        queue_name = "test-queue"
        message_id = "msg-123"

        job = ProcessingJobService.create_job(
            db=db_session,
            photo_id=photo_id,
            queue_name=queue_name,
            message_id=message_id,
        )

        assert job is not None
        assert job.photo_id == photo_id
        assert job.queue_name == queue_name
        assert job.message_id == message_id
        assert job.status == ProcessingStatus.QUEUED
        assert job.retry_count == 0
        assert job.started_at is None
        assert job.completed_at is None

    def test_update_status_to_received(self, db_session):
        """Test updating job status to received"""
        photo_id = uuid4()
        job = ProcessingJobService.create_job(
            db=db_session,
            photo_id=photo_id,
            queue_name="test-queue",
            message_id="msg-123",
        )

        updated_job = ProcessingJobService.update_status(
            db=db_session,
            job_id=job.id,
            status=ProcessingStatus.RECEIVED,
        )

        assert updated_job is not None
        assert updated_job.status == ProcessingStatus.RECEIVED
        assert updated_job.started_at is not None

    def test_update_status_to_processing(self, db_session):
        """Test updating job status to processing"""
        photo_id = uuid4()
        job = ProcessingJobService.create_job(
            db=db_session,
            photo_id=photo_id,
            queue_name="test-queue",
            message_id="msg-123",
        )

        updated_job = ProcessingJobService.update_status(
            db=db_session,
            job_id=job.id,
            status=ProcessingStatus.PROCESSING,
        )

        assert updated_job is not None
        assert updated_job.status == ProcessingStatus.PROCESSING
        assert updated_job.started_at is not None

    def test_update_status_to_completed(self, db_session):
        """Test updating job status to completed"""
        photo_id = uuid4()
        job = ProcessingJobService.create_job(
            db=db_session,
            photo_id=photo_id,
            queue_name="test-queue",
            message_id="msg-123",
        )

        # Set started_at first
        ProcessingJobService.update_status(
            db=db_session,
            job_id=job.id,
            status=ProcessingStatus.PROCESSING,
        )

        # Complete the job
        updated_job = ProcessingJobService.update_status(
            db=db_session,
            job_id=job.id,
            status=ProcessingStatus.COMPLETED,
        )

        assert updated_job is not None
        assert updated_job.status == ProcessingStatus.COMPLETED
        assert updated_job.completed_at is not None
        assert updated_job.processing_time_ms is not None
        assert updated_job.processing_time_ms >= 0

    def test_update_status_to_failed(self, db_session):
        """Test updating job status to failed with error message"""
        photo_id = uuid4()
        job = ProcessingJobService.create_job(
            db=db_session,
            photo_id=photo_id,
            queue_name="test-queue",
            message_id="msg-123",
        )

        error_message = "Processing failed: timeout"
        updated_job = ProcessingJobService.update_status(
            db=db_session,
            job_id=job.id,
            status=ProcessingStatus.FAILED,
            error_message=error_message,
        )

        assert updated_job is not None
        assert updated_job.status == ProcessingStatus.FAILED
        assert updated_job.error_message == error_message
        assert updated_job.completed_at is not None

    def test_mark_received(self, db_session):
        """Test mark_received convenience method"""
        photo_id = uuid4()
        job = ProcessingJobService.create_job(
            db=db_session,
            photo_id=photo_id,
            queue_name="test-queue",
            message_id="msg-123",
        )

        updated_job = ProcessingJobService.mark_received(db_session, job.id)

        assert updated_job is not None
        assert updated_job.status == ProcessingStatus.RECEIVED

    def test_mark_processing(self, db_session):
        """Test mark_processing convenience method"""
        photo_id = uuid4()
        job = ProcessingJobService.create_job(
            db=db_session,
            photo_id=photo_id,
            queue_name="test-queue",
            message_id="msg-123",
        )

        updated_job = ProcessingJobService.mark_processing(db_session, job.id)

        assert updated_job is not None
        assert updated_job.status == ProcessingStatus.PROCESSING

    def test_mark_completed(self, db_session):
        """Test mark_completed convenience method"""
        photo_id = uuid4()
        job = ProcessingJobService.create_job(
            db=db_session,
            photo_id=photo_id,
            queue_name="test-queue",
            message_id="msg-123",
        )

        updated_job = ProcessingJobService.mark_completed(db_session, job.id)

        assert updated_job is not None
        assert updated_job.status == ProcessingStatus.COMPLETED

    def test_mark_failed(self, db_session):
        """Test mark_failed convenience method"""
        photo_id = uuid4()
        job = ProcessingJobService.create_job(
            db=db_session,
            photo_id=photo_id,
            queue_name="test-queue",
            message_id="msg-123",
        )

        error_msg = "Test error"
        updated_job = ProcessingJobService.mark_failed(
            db_session, job.id, error_msg
        )

        assert updated_job is not None
        assert updated_job.status == ProcessingStatus.FAILED
        assert updated_job.error_message == error_msg

    def test_increment_retry_count(self, db_session):
        """Test incrementing retry count"""
        photo_id = uuid4()
        job = ProcessingJobService.create_job(
            db=db_session,
            photo_id=photo_id,
            queue_name="test-queue",
            message_id="msg-123",
        )

        assert job.retry_count == 0

        # Increment first time
        updated_job = ProcessingJobService.increment_retry_count(db_session, job.id)
        assert updated_job.retry_count == 1

        # Increment second time
        updated_job = ProcessingJobService.increment_retry_count(db_session, job.id)
        assert updated_job.retry_count == 2

    def test_get_job_by_message_id(self, db_session):
        """Test retrieving job by message ID"""
        photo_id = uuid4()
        message_id = "unique-msg-123"

        job = ProcessingJobService.create_job(
            db=db_session,
            photo_id=photo_id,
            queue_name="test-queue",
            message_id=message_id,
        )

        retrieved_job = ProcessingJobService.get_job_by_message_id(
            db_session, message_id
        )

        assert retrieved_job is not None
        assert retrieved_job.id == job.id
        assert retrieved_job.message_id == message_id

    def test_get_job_by_message_id_not_found(self, db_session):
        """Test retrieving job by non-existent message ID"""
        job = ProcessingJobService.get_job_by_message_id(
            db_session, "non-existent-msg"
        )

        assert job is None

    def test_get_job_by_photo_id(self, db_session, create_user, create_project):
        """Test retrieving latest job for a photo"""
        # Create test data
        user = create_user()
        project = create_project(user_id=user.id)

        from src.models.photo import Photo, PhotoStatus

        photo = Photo(
            user_id=user.id,
            project_id=project.id,
            s3_url="https://example.com/photo.jpg",
            s3_key="test/photo.jpg",
            status=PhotoStatus.UPLOADED,
        )
        db_session.add(photo)
        db_session.commit()

        # Create multiple jobs for same photo
        job1 = ProcessingJobService.create_job(
            db=db_session,
            photo_id=photo.id,
            queue_name="test-queue",
            message_id="msg-1",
        )

        job2 = ProcessingJobService.create_job(
            db=db_session,
            photo_id=photo.id,
            queue_name="test-queue",
            message_id="msg-2",
        )

        # Get latest job
        latest_job = ProcessingJobService.get_job_by_photo_id(
            db_session, photo.id
        )

        assert latest_job is not None
        assert latest_job.id == job2.id  # Should return most recent

    def test_get_failed_jobs(self, db_session):
        """Test retrieving failed jobs"""
        photo_id = uuid4()

        # Create some jobs with different statuses
        job1 = ProcessingJobService.create_job(
            db=db_session,
            photo_id=photo_id,
            queue_name="test-queue",
            message_id="msg-1",
        )
        ProcessingJobService.mark_failed(db_session, job1.id, "Error 1")

        job2 = ProcessingJobService.create_job(
            db=db_session,
            photo_id=photo_id,
            queue_name="test-queue",
            message_id="msg-2",
        )
        ProcessingJobService.mark_completed(db_session, job2.id)

        job3 = ProcessingJobService.create_job(
            db=db_session,
            photo_id=photo_id,
            queue_name="test-queue",
            message_id="msg-3",
        )
        ProcessingJobService.mark_failed(db_session, job3.id, "Error 3")

        # Get failed jobs
        failed_jobs = ProcessingJobService.get_failed_jobs(db_session, limit=10)

        assert len(failed_jobs) == 2
        assert all(job.status == ProcessingStatus.FAILED for job in failed_jobs)

    def test_update_status_nonexistent_job(self, db_session):
        """Test updating status of non-existent job"""
        fake_job_id = uuid4()

        updated_job = ProcessingJobService.update_status(
            db=db_session,
            job_id=fake_job_id,
            status=ProcessingStatus.COMPLETED,
        )

        assert updated_job is None

    def test_processing_time_calculation(self, db_session):
        """Test processing time is calculated correctly"""
        import time

        photo_id = uuid4()
        job = ProcessingJobService.create_job(
            db=db_session,
            photo_id=photo_id,
            queue_name="test-queue",
            message_id="msg-123",
        )

        # Start processing
        ProcessingJobService.mark_processing(db_session, job.id)

        # Simulate some processing time
        time.sleep(0.1)

        # Complete processing
        updated_job = ProcessingJobService.mark_completed(db_session, job.id)

        assert updated_job.processing_time_ms is not None
        # Should be at least 100ms
        assert updated_job.processing_time_ms >= 100
