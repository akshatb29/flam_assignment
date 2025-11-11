"""
Job model and state definitions for queuectl
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Optional


class JobState(Enum):
    """Valid job states in the system"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"


@dataclass
class Job:
    """
    Represents a background job in the queue system.
    
    Attributes:
        id: Unique identifier for the job
        command: Shell command to execute
        state: Current state of the job
        attempts: Number of execution attempts so far
        max_retries: Maximum retry attempts before moving to DLQ
        created_at: ISO timestamp of job creation
        updated_at: ISO timestamp of last update
        error_message: Optional error message from last failure
        worker_id: ID of worker currently processing this job
    """
    id: str
    command: str
    state: str = JobState.PENDING.value
    attempts: int = 0
    max_retries: int = 3
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    error_message: Optional[str] = None
    worker_id: Optional[str] = None
    
    def __post_init__(self):
        """Set timestamps if not provided"""
        now = datetime.utcnow().isoformat() + "Z"
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
    
    def to_dict(self) -> dict:
        """Convert job to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Job':
        """Create job from dictionary"""
        return cls(**data)
    
    def should_retry(self) -> bool:
        """Check if job should be retried"""
        return self.attempts < self.max_retries
    
    def move_to_dlq(self):
        """Move job to Dead Letter Queue"""
        self.state = JobState.DEAD.value
        self.updated_at = datetime.utcnow().isoformat() + "Z"
    
    def mark_processing(self, worker_id: str):
        """Mark job as being processed"""
        self.state = JobState.PROCESSING.value
        self.worker_id = worker_id
        self.attempts += 1
        self.updated_at = datetime.utcnow().isoformat() + "Z"
    
    def mark_completed(self):
        """Mark job as completed"""
        self.state = JobState.COMPLETED.value
        self.worker_id = None
        self.updated_at = datetime.utcnow().isoformat() + "Z"
    
    def mark_failed(self, error_message: str):
        """Mark job as failed"""
        self.error_message = error_message
        self.worker_id = None
        self.updated_at = datetime.utcnow().isoformat() + "Z"
        
        if self.should_retry():
            self.state = JobState.FAILED.value
        else:
            self.move_to_dlq()