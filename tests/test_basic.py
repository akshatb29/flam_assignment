"""
Unit tests for queuectl
Run with: pytest tests/
"""
import os
import time
import pytest
from pathlib import Path

from queuectl.models import Job, JobState
from queuectl.storage import JobStorage
from queuectl.queue import QueueManager
from queuectl.config import Config


@pytest.fixture
def test_db():
    """Create a temporary test database"""
    db_path = "test_jobs.db"
    
    # Remove if exists
    if os.path.exists(db_path):
        os.remove(db_path)
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def storage(test_db):
    """Create a JobStorage instance"""
    return JobStorage(test_db)


@pytest.fixture
def queue_manager(test_db):
    """Create a QueueManager with test database"""
    config = Config()
    config.set("db_path", test_db)
    return QueueManager()


class TestJob:
    """Test Job model"""
    
    def test_job_creation(self):
        """Test creating a job"""
        job = Job(id="test1", command="echo hello")
        
        assert job.id == "test1"
        assert job.command == "echo hello"
        assert job.state == JobState.PENDING.value
        assert job.attempts == 0
        assert job.max_retries == 3
        assert job.created_at is not None
        assert job.updated_at is not None
    
    def test_job_should_retry(self):
        """Test retry logic"""
        job = Job(id="test1", command="echo hello", max_retries=3)
        
        assert job.should_retry() == True
        
        job.attempts = 3
        assert job.should_retry() == False
    
    def test_job_state_transitions(self):
        """Test job state transitions"""
        job = Job(id="test1", command="echo hello")
        
        # Mark as processing
        job.mark_processing("worker-1")
        assert job.state == JobState.PROCESSING.value
        assert job.worker_id == "worker-1"
        assert job.attempts == 1
        
        # Mark as completed
        job.mark_completed()
        assert job.state == JobState.COMPLETED.value
        assert job.worker_id is None
    
    def test_job_move_to_dlq(self):
        """Test moving job to DLQ"""
        job = Job(id="test1", command="echo hello", max_retries=3, attempts=3)
        
        job.mark_failed("Test error")
        assert job.state == JobState.DEAD.value
        assert job.error_message == "Test error"


class TestStorage:
    """Test JobStorage"""
    
    def test_add_job(self, storage):
        """Test adding a job"""
        job = Job(id="test1", command="echo hello")
        
        success = storage.add_job(job)
        assert success == True
        
        # Try adding duplicate
        success = storage.add_job(job)
        assert success == False
    
    def test_get_job(self, storage):
        """Test retrieving a job"""
        job = Job(id="test1", command="echo hello")
        storage.add_job(job)
        
        retrieved = storage.get_job("test1")
        assert retrieved is not None
        assert retrieved.id == "test1"
        assert retrieved.command == "echo hello"
        
        # Non-existent job
        retrieved = storage.get_job("nonexistent")
        assert retrieved is None
    
    def test_update_job(self, storage):
        """Test updating a job"""
        job = Job(id="test1", command="echo hello")
        storage.add_job(job)
        
        job.state = JobState.COMPLETED.value
        storage.update_job(job)
        
        retrieved = storage.get_job("test1")
        assert retrieved.state == JobState.COMPLETED.value
    
    def test_list_jobs(self, storage):
        """Test listing jobs"""
        job1 = Job(id="test1", command="echo 1")
        job2 = Job(id="test2", command="echo 2", state=JobState.COMPLETED.value)
        
        storage.add_job(job1)
        storage.add_job(job2)
        
        # List all
        all_jobs = storage.list_jobs()
        assert len(all_jobs) == 2
        
        # List by state
        pending_jobs = storage.list_jobs(JobState.PENDING.value)
        assert len(pending_jobs) == 1
        assert pending_jobs[0].id == "test1"
    
    def test_get_next_pending_job(self, storage):
        """Test getting and locking next pending job"""
        job1 = Job(id="test1", command="echo 1")
        job2 = Job(id="test2", command="echo 2")
        
        storage.add_job(job1)
        storage.add_job(job2)
        
        # First worker gets first job
        next_job = storage.get_next_pending_job("worker-1")
        assert next_job is not None
        assert next_job.id == "test1"
        assert next_job.state == JobState.PROCESSING.value
        assert next_job.worker_id == "worker-1"
        
        # Second worker gets second job
        next_job = storage.get_next_pending_job("worker-2")
        assert next_job is not None
        assert next_job.id == "test2"
    
    def test_get_status_summary(self, storage):
        """Test status summary"""
        job1 = Job(id="test1", command="echo 1")
        job2 = Job(id="test2", command="echo 2", state=JobState.COMPLETED.value)
        job3 = Job(id="test3", command="echo 3", state=JobState.DEAD.value)
        
        storage.add_job(job1)
        storage.add_job(job2)
        storage.add_job(job3)
        
        summary = storage.get_status_summary()
        assert summary[JobState.PENDING.value] == 1
        assert summary[JobState.COMPLETED.value] == 1
        assert summary[JobState.DEAD.value] == 1
    
    def test_delete_job(self, storage):
        """Test deleting a job"""
        job = Job(id="test1", command="echo hello")
        storage.add_job(job)
        
        success = storage.delete_job("test1")
        assert success == True
        
        # Verify deleted
        retrieved = storage.get_job("test1")
        assert retrieved is None
        
        # Delete non-existent
        success = storage.delete_job("nonexistent")
        assert success == False


class TestQueueManager:
    """Test QueueManager"""
    
    def test_enqueue_with_id(self, queue_manager):
        """Test enqueuing with explicit ID"""
        job_data = {"id": "test1", "command": "echo hello"}
        success, message = queue_manager.enqueue(job_data)
        
        assert success == True
        assert "test1" in message
    
    def test_enqueue_auto_id(self, queue_manager):
        """Test enqueuing with auto-generated ID"""
        job_data = {"command": "echo hello"}
        success, message = queue_manager.enqueue(job_data)
        
        assert success == True
        assert "job-" in message
    
    def test_enqueue_missing_command(self, queue_manager):
        """Test enqueuing without command"""
        job_data = {"id": "test1"}
        success, message = queue_manager.enqueue(job_data)
        
        assert success == False
        assert "command" in message.lower()
    
    def test_enqueue_duplicate_id(self, queue_manager):
        """Test enqueuing duplicate ID"""
        job_data = {"id": "test1", "command": "echo hello"}
        
        success1, _ = queue_manager.enqueue(job_data)
        success2, message2 = queue_manager.enqueue(job_data)
        
        assert success1 == True
        assert success2 == False
        assert "already exists" in message2.lower()
    
    def test_list_jobs(self, queue_manager):
        """Test listing jobs"""
        queue_manager.enqueue({"id": "test1", "command": "echo 1"})
        queue_manager.enqueue({"id": "test2", "command": "echo 2"})
        
        jobs = queue_manager.list_jobs()
        assert len(jobs) == 2
    
    def test_get_status(self, queue_manager):
        """Test getting status"""
        queue_manager.enqueue({"id": "test1", "command": "echo 1"})
        
        status = queue_manager.get_status()
        assert status["total_jobs"] == 1
        assert status["jobs"][JobState.PENDING.value] == 1
    
    def test_retry_dlq_job(self, queue_manager):
        """Test retrying DLQ job"""
        # Create a dead job
        queue_manager.enqueue({"id": "test1", "command": "echo 1"})
        job = queue_manager.get_job("test1")
        job.state = JobState.DEAD.value
        job.attempts = 3
        queue_manager.storage.update_job(job)
        
        # Retry it
        success, message = queue_manager.retry_dlq_job("test1")
        assert success == True
        
        # Verify state
        job = queue_manager.get_job("test1")
        assert job.state == JobState.PENDING.value
        assert job.attempts == 0
    
    def test_parse_job_json(self, queue_manager):
        """Test JSON parsing"""
        # Valid JSON
        success, result = queue_manager.parse_job_json('{"command": "echo hello"}')
        assert success == True
        assert result["command"] == "echo hello"
        
        # Invalid JSON
        success, result = queue_manager.parse_job_json('invalid json')
        assert success == False
        assert "invalid" in result.lower()


class TestConfig:
    """Test Config"""
    
    def test_config_defaults(self):
        """Test default configuration"""
        config = Config()
        
        assert config.max_retries == 3
        assert config.backoff_base == 2
        assert config.worker_poll_interval == 1
    
    def test_config_set_get(self):
        """Test setting and getting config"""
        config = Config()
        
        config.set("max_retries", 5)
        assert config.get("max_retries") == 5
        
        config.set("custom_key", "custom_value")
        assert config.get("custom_key") == "custom_value"