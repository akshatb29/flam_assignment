"""
High-level queue management API
Provides interface for enqueuing jobs and managing the queue
"""
import json
import uuid
from typing import List, Optional, Dict

from .storage import JobStorage
from .config import get_config
from .models import Job, JobState


class QueueManager:
    """
    High-level interface for managing the job queue.
    Provides methods for enqueuing, listing, and managing jobs.
    """
    
    def __init__(self):
        """Initialize queue manager"""
        self.config = get_config()
        self.storage = JobStorage(self.config.db_path)
    
    def enqueue(self, job_data: dict) -> tuple[bool, str]:
        """
        Enqueue a new job.
        
        Args:
            job_data: Dictionary containing job fields
                Required: command
                Optional: id, max_retries
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        # Validate required fields
        if "command" not in job_data:
            return False, "Error: 'command' field is required"
        
        # Generate ID if not provided
        if "id" not in job_data:
            job_data["id"] = f"job-{uuid.uuid4().hex[:12]}"
        
        # Use default max_retries from config if not provided
        if "max_retries" not in job_data:
            job_data["max_retries"] = self.config.max_retries
        
        # Create job object
        try:
            job = Job(
                id=job_data["id"],
                command=job_data["command"],
                max_retries=job_data.get("max_retries", self.config.max_retries)
            )
        except Exception as e:
            return False, f"Error creating job: {e}"
        
        # Add to storage
        success = self.storage.add_job(job)
        
        if success:
            return True, f"Job {job.id} enqueued successfully"
        else:
            return False, f"Error: Job with ID '{job.id}' already exists"
    
    def list_jobs(self, state: Optional[str] = None) -> List[Job]:
        """
        List all jobs, optionally filtered by state.
        
        Args:
            state: Optional state filter (pending, processing, completed, failed, dead)
        
        Returns:
            List of Job objects
        """
        if state:
            # Validate state
            valid_states = [s.value for s in JobState]
            if state not in valid_states:
                raise ValueError(f"Invalid state: {state}. Must be one of {valid_states}")
        
        return self.storage.list_jobs(state)
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get a specific job by ID.
        
        Args:
            job_id: Job ID to retrieve
        
        Returns:
            Job object or None if not found
        """
        return self.storage.get_job(job_id)
    
    def get_status(self) -> Dict[str, any]:
        """
        Get queue status summary.
        
        Returns:
            Dictionary with job counts and system info
        """
        summary = self.storage.get_status_summary()
        
        # Count active workers (jobs in processing state)
        active_workers = summary.get(JobState.PROCESSING.value, 0)
        
        return {
            "jobs": summary,
            "total_jobs": sum(summary.values()),
            "active_workers": active_workers
        }
    
    def retry_dlq_job(self, job_id: str) -> tuple[bool, str]:
        """
        Retry a job from the Dead Letter Queue.
        Resets the job to pending state with attempt count reset.
        
        Args:
            job_id: Job ID to retry
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        job = self.storage.get_job(job_id)
        
        if job is None:
            return False, f"Error: Job '{job_id}' not found"
        
        if job.state != JobState.DEAD.value:
            return False, f"Error: Job '{job_id}' is not in DLQ (current state: {job.state})"
        
        # Reset job for retry
        job.state = JobState.PENDING.value
        job.attempts = 0
        job.error_message = None
        job.worker_id = None
        
        from datetime import datetime
        job.updated_at = datetime.utcnow().isoformat() + "Z"
        
        self.storage.update_job(job)
        
        return True, f"Job {job_id} moved back to pending queue"
    
    def list_dlq_jobs(self) -> List[Job]:
        """
        List all jobs in the Dead Letter Queue.
        
        Returns:
            List of dead jobs
        """
        return self.storage.list_jobs(JobState.DEAD.value)
    
    def delete_job(self, job_id: str) -> tuple[bool, str]:
        """
        Delete a job from the queue.
        
        Args:
            job_id: Job ID to delete
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        success = self.storage.delete_job(job_id)
        
        if success:
            return True, f"Job {job_id} deleted successfully"
        else:
            return False, f"Error: Job '{job_id}' not found"
    
    def parse_job_json(self, json_str: str) -> tuple[bool, any]:
        """
        Parse job JSON string into dictionary.
        
        Args:
            json_str: JSON string containing job data
        
        Returns:
            Tuple of (success: bool, result: dict or error_message: str)
        """
        try:
            job_data = json.loads(json_str)
            
            if not isinstance(job_data, dict):
                return False, "Error: Job data must be a JSON object"
            
            return True, job_data
        
        except json.JSONDecodeError as e:
            return False, f"Error: Invalid JSON - {e}"
    
    def close(self):
        """Close storage connection"""
        self.storage.close()