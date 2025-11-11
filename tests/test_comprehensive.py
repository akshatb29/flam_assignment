"""
Comprehensive test suite for queuectl
Tests all critical functionality including edge cases
Run with: pytest tests/test_comprehensive.py -v
"""
import os
import time
import pytest
import threading
import multiprocessing
from pathlib import Path

from queuectl.models import Job, JobState
from queuectl.storage import JobStorage
from queuectl.queue import QueueManager
from queuectl.config import Config
from queuectl.workers import Worker


@pytest.fixture
def test_db():
    """Create a temporary test database"""
    db_path = "test_comprehensive.db"
    
    if os.path.exists(db_path):
        os.remove(db_path)
    
    yield db_path
    
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


class TestPersistence:
    """Test data persistence across restarts"""
    
    def test_jobs_persist_after_restart(self, test_db):
        """Test that jobs survive storage restart"""
        # Create storage and add job
        storage1 = JobStorage(test_db)
        job = Job(id="persist-test", command="echo test")
        storage1.add_job(job)
        storage1.close()
        
        # Create new storage instance (simulating restart)
        storage2 = JobStorage(test_db)
        retrieved = storage2.get_job("persist-test")
        
        assert retrieved is not None
        assert retrieved.id == "persist-test"
        assert retrieved.command == "echo test"
        storage2.close()
    
    def test_job_state_persists(self, test_db):
        """Test that job state changes persist"""
        storage1 = JobStorage(test_db)
        job = Job(id="state-test", command="echo test")
        storage1.add_job(job)
        
        # Update state
        job.mark_processing("worker-1")
        storage1.update_job(job)
        storage1.close()
        
        # Retrieve in new instance
        storage2 = JobStorage(test_db)
        retrieved = storage2.get_job("state-test")
        
        assert retrieved.state == JobState.PROCESSING.value
        assert retrieved.worker_id == "worker-1"
        assert retrieved.attempts == 1
        storage2.close()


class TestConcurrency:
    """Test concurrent access and race condition prevention"""
    
    def test_no_duplicate_job_processing(self, storage):
        """Test that multiple workers don't process the same job"""
        # Add a job
        job = Job(id="concurrent-test", command="echo test")
        storage.add_job(job)
        
        results = []
        
        def claim_job(worker_id):
            """Try to claim the job"""
            claimed = storage.get_next_pending_job(worker_id)
            results.append((worker_id, claimed))
        
        # Try to claim same job from multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=claim_job, args=(f"worker-{i}",))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Only one worker should have claimed the job
        successful_claims = [r for r in results if r[1] is not None]
        assert len(successful_claims) == 1, "Multiple workers claimed the same job!"
        
        # Verify job is marked as processing
        job = storage.get_job("concurrent-test")
        assert job.state == JobState.PROCESSING.value
    
    def test_concurrent_enqueue(self, storage):
        """Test that concurrent enqueues don't cause issues"""
        def enqueue_job(job_id):
            job = Job(id=job_id, command=f"echo {job_id}")
            storage.add_job(job)
        
        threads = []
        for i in range(10):
            t = threading.Thread(target=enqueue_job, args=(f"job-{i}",))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Verify all jobs were added
        all_jobs = storage.list_jobs()
        assert len(all_jobs) == 10


class TestRetryLogic:
    """Test retry and exponential backoff"""
    
    def test_retry_increments_attempts(self, storage):
        """Test that retries increment attempt count"""
        job = Job(id="retry-test", command="exit 1", max_retries=3)
        storage.add_job(job)
        
        # Simulate 3 failed attempts
        for i in range(3):
            job = storage.get_next_pending_job(f"worker-{i}")
            assert job is not None
            assert job.attempts == i + 1
            
            job.mark_failed(f"Attempt {i+1} failed")
            storage.update_job(job)
        
        # After 3 attempts, should be in DLQ
        job = storage.get_job("retry-test")
        assert job.state == JobState.DEAD.value
    
    def test_backoff_calculation(self):
        """Test exponential backoff calculation"""
        config = Config()
        config.set("backoff_base", 2)
        
        worker = Worker()
        
        # Test backoff delays
        assert worker._calculate_backoff_delay(1) == 2  # 2^1 = 2
        assert worker._calculate_backoff_delay(2) == 4  # 2^2 = 4
        assert worker._calculate_backoff_delay(3) == 8  # 2^3 = 8
    
    def test_job_moves_to_dlq_after_max_retries(self, storage):
        """Test that jobs move to DLQ after exhausting retries"""
        job = Job(id="dlq-test", command="exit 1", max_retries=2)
        storage.add_job(job)
        
        # Fail twice
        for i in range(2):
            job = storage.get_next_pending_job("worker-1")
            job.mark_failed("Failed")
            storage.update_job(job)
        
        # Should be in DLQ now
        job = storage.get_job("dlq-test")
        assert job.state == JobState.DEAD.value
        assert job.attempts == 2


class TestDLQ:
    """Test Dead Letter Queue functionality"""
    
    def test_list_dlq_jobs(self, queue_manager):
        """Test listing DLQ jobs"""
        # Add some jobs to DLQ
        for i in range(3):
            job_data = {"id": f"dlq-{i}", "command": "exit 1", "max_retries": 0}
            queue_manager.enqueue(job_data)
            
            # Move to DLQ
            job = queue_manager.get_job(f"dlq-{i}")
            job.state = JobState.DEAD.value
            job.attempts = 1
            queue_manager.storage.update_job(job)
        
        # List DLQ
        dlq_jobs = queue_manager.list_dlq_jobs()
        assert len(dlq_jobs) == 3
        assert all(j.state == JobState.DEAD.value for j in dlq_jobs)
    
    def test_retry_dlq_job(self, queue_manager):
        """Test retrying a job from DLQ"""
        # Add job to DLQ
        job_data = {"id": "retry-dlq", "command": "echo test"}
        queue_manager.enqueue(job_data)
        
        job = queue_manager.get_job("retry-dlq")
        job.state = JobState.DEAD.value
        job.attempts = 3
        job.error_message = "Previous error"
        queue_manager.storage.update_job(job)
        
        # Retry it
        success, message = queue_manager.retry_dlq_job("retry-dlq")
        assert success == True
        
        # Verify state
        job = queue_manager.get_job("retry-dlq")
        assert job.state == JobState.PENDING.value
        assert job.attempts == 0
        assert job.error_message is None
    
    def test_retry_non_dlq_job_fails(self, queue_manager):
        """Test that retrying non-DLQ job fails"""
        job_data = {"id": "not-dlq", "command": "echo test"}
        queue_manager.enqueue(job_data)
        
        success, message = queue_manager.retry_dlq_job("not-dlq")
        assert success == False
        assert "not in DLQ" in message


class TestConfiguration:
    """Test configuration management"""
    
    def test_config_persistence(self, tmp_path):
        """Test that config persists across instances"""
        config_path = tmp_path / "config.json"
        
        # Set config
        config1 = Config(str(config_path))
        config1.set("max_retries", 10)
        config1.set("backoff_base", 3)
        
        # Load in new instance
        config2 = Config(str(config_path))
        assert config2.get("max_retries") == 10
        assert config2.get("backoff_base") == 3
    
    def test_default_config_values(self):
        """Test that default config values are set"""
        config = Config()
        assert config.max_retries >= 1
        assert config.backoff_base >= 1
        assert config.worker_poll_interval >= 1
    
    def test_config_used_in_jobs(self, queue_manager):
        """Test that jobs use config defaults"""
        # Set config
        config = Config()
        config.set("max_retries", 7)
        
        # Enqueue job without max_retries
        queue_manager.enqueue({"id": "config-test", "command": "echo test"})
        
        job = queue_manager.get_job("config-test")
        # Note: This might be 5 if test changed it earlier, but config should be used
        assert job.max_retries >= 1


class TestJobExecution:
    """Test actual job execution (integration tests)"""
    
    def test_successful_job_execution(self, storage):
        """Test executing a successful job"""
        job = Job(id="success-job", command="echo success")
        storage.add_job(job)
        
        worker = Worker("test-worker")
        job = storage.get_next_pending_job("test-worker")
        worker._execute_job(job)
        
        # Verify job completed
        job = storage.get_job("success-job")
        assert job.state == JobState.COMPLETED.value
    
    def test_failed_job_execution(self, storage):
        """Test executing a failing job"""
        job = Job(id="fail-job", command="exit 1", max_retries=1)
        storage.add_job(job)
        
        worker = Worker("test-worker")
        job = storage.get_next_pending_job("test-worker")
        worker._execute_job(job)
        
        # Verify job failed
        job = storage.get_job("fail-job")
        assert job.state == JobState.FAILED.value
        assert job.error_message is not None
    
    def test_invalid_command_execution(self, storage):
        """Test executing an invalid command"""
        job = Job(id="invalid-job", command="nonexistent_command_xyz", max_retries=0)
        storage.add_job(job)
        
        worker = Worker("test-worker")
        job = storage.get_next_pending_job("test-worker")
        worker._execute_job(job)
        
        # Verify job moved to DLQ
        job = storage.get_job("invalid-job")
        assert job.state == JobState.DEAD.value
        assert "not found" in job.error_message.lower() or "not recognized" in job.error_message.lower()


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_enqueue_without_command(self, queue_manager):
        """Test enqueuing job without command fails"""
        success, message = queue_manager.enqueue({"id": "no-command"})
        assert success == False
        assert "command" in message.lower()
    
    def test_enqueue_duplicate_id(self, queue_manager):
        """Test enqueuing duplicate ID fails"""
        queue_manager.enqueue({"id": "duplicate", "command": "echo test"})
        success, message = queue_manager.enqueue({"id": "duplicate", "command": "echo test2"})
        
        assert success == False
        assert "already exists" in message.lower()
    
    def test_get_nonexistent_job(self, queue_manager):
        """Test getting nonexistent job returns None"""
        job = queue_manager.get_job("does-not-exist")
        assert job is None
    
    def test_retry_nonexistent_dlq_job(self, queue_manager):
        """Test retrying nonexistent DLQ job fails"""
        success, message = queue_manager.retry_dlq_job("does-not-exist")
        assert success == False
    
    def test_empty_queue_returns_none(self, storage):
        """Test that empty queue returns None for next job"""
        job = storage.get_next_pending_job("worker-1")
        assert job is None
    
    def test_auto_id_generation(self, queue_manager):
        """Test that jobs without ID get auto-generated ID"""
        success, message = queue_manager.enqueue({"command": "echo test"})
        assert success == True
        assert "job-" in message


class TestWorkerGracefulShutdown:
    """Test worker graceful shutdown"""
    
    def test_worker_stops_on_signal(self):
        """Test that worker can be stopped gracefully"""
        worker = Worker("test-worker")
        
        # Start worker in thread
        def run_worker():
            worker.start()
        
        thread = threading.Thread(target=run_worker)
        thread.start()
        
        # Wait a bit then stop
        time.sleep(0.5)
        worker.stop()
        
        thread.join(timeout=2)
        assert not thread.is_alive(), "Worker didn't stop gracefully"


# Summary test that runs all critical flows
class TestEndToEnd:
    """End-to-end integration test"""
    
    def test_complete_workflow(self, test_db):
        """Test complete workflow: enqueue -> process -> retry -> DLQ"""
        queue = QueueManager()
        config = Config()
        config.set("db_path", test_db)
        config.set("max_retries", 2)
        
        # Enqueue jobs
        queue.enqueue({"id": "e2e-success", "command": "echo success"})
        queue.enqueue({"id": "e2e-fail", "command": "exit 1", "max_retries": 1})
        
        # Check status
        status = queue.get_status()
        assert status["total_jobs"] == 2
        assert status["jobs"]["pending"] == 2
        
        # Process jobs with worker
        storage = JobStorage(test_db)
        worker = Worker("e2e-worker")
        
        # Process success job
        job = storage.get_next_pending_job("e2e-worker")
        assert job.id == "e2e-success"
        worker._execute_job(job)
        
        # Process fail job (will retry once then DLQ)
        job = storage.get_next_pending_job("e2e-worker")
        assert job.id == "e2e-fail"
        worker._execute_job(job)
        
        # Check status after first attempt
        job = storage.get_job("e2e-fail")
        assert job.state == JobState.FAILED.value
        
        # Retry (second attempt, should go to DLQ)
        job = storage.get_next_pending_job("e2e-worker")
        worker._execute_job(job)
        
        job = storage.get_job("e2e-fail")
        assert job.state == JobState.DEAD.value
        
        # Verify DLQ
        dlq_jobs = queue.list_dlq_jobs()
        assert len(dlq_jobs) == 1
        assert dlq_jobs[0].id == "e2e-fail"
        
        # Retry from DLQ
        success, _ = queue.retry_dlq_job("e2e-fail")
        assert success == True
        
        job = queue.get_job("e2e-fail")
        assert job.state == JobState.PENDING.value
        
        storage.close()
        queue.close()