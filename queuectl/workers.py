"""
Worker process for executing jobs with exponential backoff retry logic
"""
import subprocess
import time
import signal
import uuid
from typing import Optional
from datetime import datetime

from .storage import JobStorage
from .config import get_config
from .models import Job, JobState


class Worker:
    """
    Worker process that polls for jobs and executes them.
    Implements exponential backoff for retries and graceful shutdown.
    """
    
    def __init__(self, worker_id: Optional[str] = None):
        """
        Initialize worker.
        
        Args:
            worker_id: Optional worker ID (generated if not provided)
        """
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.storage = JobStorage(get_config().db_path)
        self.config = get_config()
        self.running = False
        self.current_job = None
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\n[{self.worker_id}] Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def start(self):
        """
        Start the worker main loop.
        Polls for jobs, executes them, and handles retries.
        """
        self.running = True
        print(f"[{self.worker_id}] Worker started")
        
        try:
            while self.running:
                # Get next available job
                job = self.storage.get_next_pending_job(self.worker_id)
                
                if job is None:
                    # No jobs available, wait before polling again
                    time.sleep(self.config.worker_poll_interval)
                    continue
                
                self.current_job = job
                print(f"[{self.worker_id}] Processing job {job.id} (attempt {job.attempts}/{job.max_retries})")
                
                # Check if job needs backoff delay
                if job.attempts > 1:
                    delay = self._calculate_backoff_delay(job.attempts - 1)
                    print(f"[{self.worker_id}] Waiting {delay}s before retry...")
                    
                    # Sleep in small chunks to allow graceful shutdown
                    for _ in range(int(delay)):
                        if not self.running:
                            break
                        time.sleep(1)
                    
                    if not self.running:
                        # Release job if shutting down
                        self._release_job(job)
                        break
                
                # Execute the job
                self._execute_job(job)
                self.current_job = None
        
        except Exception as e:
            print(f"[{self.worker_id}] Error: {e}")
        
        finally:
            print(f"[{self.worker_id}] Worker stopped")
            self.storage.close()
    
    def _execute_job(self, job: Job):
        """
        Execute a job's command and update its state.
        
        Args:
            job: Job to execute
        """
        try:
            # Execute command with timeout
            result = subprocess.run(
                job.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                # Job succeeded
                job.mark_completed()
                self.storage.update_job(job)
                print(f"[{self.worker_id}] ✓ Job {job.id} completed successfully")
                
                if result.stdout:
                    print(f"[{self.worker_id}]   Output: {result.stdout.strip()}")
            
            else:
                # Job failed
                error_msg = f"Exit code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr.strip()}"
                
                self._handle_job_failure(job, error_msg)
        
        except subprocess.TimeoutExpired:
            error_msg = "Command timed out after 5 minutes"
            self._handle_job_failure(job, error_msg)
        
        except FileNotFoundError:
            error_msg = "Command not found or not executable"
            self._handle_job_failure(job, error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._handle_job_failure(job, error_msg)
    
    def _handle_job_failure(self, job: Job, error_message: str):
        """
        Handle a failed job execution.
        Determines if job should retry or move to DLQ.
        
        Args:
            job: Failed job
            error_message: Error description
        """
        job.mark_failed(error_message)
        self.storage.update_job(job)
        
        if job.state == JobState.DEAD.value:
            print(f"[{self.worker_id}] ✗ Job {job.id} moved to DLQ after {job.attempts} attempts")
            print(f"[{self.worker_id}]   Error: {error_message}")
        else:
            next_delay = self._calculate_backoff_delay(job.attempts)
            print(f"[{self.worker_id}] ✗ Job {job.id} failed (attempt {job.attempts}/{job.max_retries})")
            print(f"[{self.worker_id}]   Error: {error_message}")
            print(f"[{self.worker_id}]   Will retry in {next_delay}s")
    
    def _calculate_backoff_delay(self, attempts: int) -> int:
        """
        Calculate exponential backoff delay.
        delay = base^attempts seconds
        
        Args:
            attempts: Number of attempts so far
        
        Returns:
            Delay in seconds
        """
        base = self.config.backoff_base
        return base ** attempts
    
    def _release_job(self, job: Job):
        """
        Release a job back to pending state (for graceful shutdown).
        
        Args:
            job: Job to release
        """
        job.state = JobState.PENDING.value
        job.worker_id = None
        job.attempts -= 1  # Decrement since we didn't actually process it
        job.updated_at = datetime.utcnow().isoformat() + "Z"
        self.storage.update_job(job)
        print(f"[{self.worker_id}] Released job {job.id} back to pending")
    
    def stop(self):
        """Stop the worker gracefully"""
        self.running = False


def start_worker(worker_id: Optional[str] = None):
    """
    Start a single worker process.
    
    Args:
        worker_id: Optional worker ID
    """
    worker = Worker(worker_id)
    worker.start()