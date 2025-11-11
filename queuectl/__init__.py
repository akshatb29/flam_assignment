"""
queuectl - A CLI-based background job queue system

A minimal, production-grade job queue with:
- Worker processes
- Exponential backoff retries
- Dead Letter Queue
- Persistent storage
"""

__version__ = "1.0.0"
__author__ = "Your Name"

from .queue import QueueManager
from .workers import Worker
from .models import Job, JobState
from .config import get_config

__all__ = [
    "QueueManager",
    "Worker",
    "Job",
    "JobState",
    "get_config"
]