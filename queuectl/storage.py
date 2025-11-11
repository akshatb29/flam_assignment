"""
SQLite-based persistent storage for jobs
Handles all database operations with proper locking for concurrent access
"""
import sqlite3
import json
from typing import List, Optional
from contextlib import contextmanager
from datetime import datetime
import threading

from .models import Job, JobState


class JobStorage:
    """
    SQLite-based storage for job persistence.
    Thread-safe with proper locking for concurrent worker access.
    """
    
    def __init__(self, db_path: str = "jobs.db"):
        """
        Initialize storage with SQLite database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, 'connection'):
            # Enable WAL mode for better concurrent access
            self._local.connection = sqlite3.connect(
                self.db_path,
                isolation_level=None,  # autocommit mode
                check_same_thread=False
            )
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA busy_timeout=5000")  # 5 second timeout
        return self._local.connection
    
    def _init_db(self):
        """Create jobs table if it doesn't exist"""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                command TEXT NOT NULL,
                state TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error_message TEXT,
                worker_id TEXT
            )
        """)
        
        # Create indices for faster queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_state ON jobs(state)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_worker ON jobs(worker_id)")
        conn.commit()
    
    @contextmanager
    def _transaction(self):
        """Context manager for database transactions"""
        conn = self._get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def add_job(self, job: Job) -> bool:
        """
        Add a new job to the database.
        
        Args:
            job: Job to add
        
        Returns:
            True if successful, False if job ID already exists
        """
        try:
            with self._transaction() as conn:
                conn.execute("""
                    INSERT INTO jobs (
                        id, command, state, attempts, max_retries,
                        created_at, updated_at, error_message, worker_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job.id, job.command, job.state, job.attempts,
                    job.max_retries, job.created_at, job.updated_at,
                    job.error_message, job.worker_id
                ))
            return True
        except sqlite3.IntegrityError:
            # Job ID already exists
            return False
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get a job by ID.
        
        Args:
            job_id: Job ID to retrieve
        
        Returns:
            Job object or None if not found
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM jobs WHERE id = ?",
            (job_id,)
        )
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        return self._row_to_job(row)
    
    def update_job(self, job: Job):
        """
        Update an existing job in the database.
        
        Args:
            job: Job with updated fields
        """
        with self._transaction() as conn:
            conn.execute("""
                UPDATE jobs SET
                    command = ?,
                    state = ?,
                    attempts = ?,
                    max_retries = ?,
                    updated_at = ?,
                    error_message = ?,
                    worker_id = ?
                WHERE id = ?
            """, (
                job.command, job.state, job.attempts, job.max_retries,
                job.updated_at, job.error_message, job.worker_id, job.id
            ))
    
    def list_jobs(self, state: Optional[str] = None) -> List[Job]:
        """
        List all jobs, optionally filtered by state.
        
        Args:
            state: Optional state filter
        
        Returns:
            List of jobs
        """
        conn = self._get_connection()
        
        if state:
            cursor = conn.execute(
                "SELECT * FROM jobs WHERE state = ? ORDER BY created_at",
                (state,)
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at"
            )
        
        return [self._row_to_job(row) for row in cursor.fetchall()]
    
    def get_next_pending_job(self, worker_id: str) -> Optional[Job]:
        """
        Get next pending job and lock it for the worker.
        Uses database locking to prevent duplicate processing.
        
        Args:
            worker_id: ID of worker claiming the job
        
        Returns:
            Job object or None if no pending jobs
        """
        with self._transaction() as conn:
            # Find oldest pending or failed job
            cursor = conn.execute("""
                SELECT * FROM jobs 
                WHERE state IN (?, ?)
                ORDER BY created_at
                LIMIT 1
            """, (JobState.PENDING.value, JobState.FAILED.value))
            
            row = cursor.fetchone()
            if row is None:
                return None
            
            job = self._row_to_job(row)
            
            # Lock job for this worker
            job.mark_processing(worker_id)
            conn.execute("""
                UPDATE jobs SET
                    state = ?,
                    attempts = ?,
                    worker_id = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                job.state, job.attempts, job.worker_id,
                job.updated_at, job.id
            ))
            
            return job
    
    def get_status_summary(self) -> dict:
        """
        Get summary of job counts by state.
        
        Returns:
            Dict with counts for each state
        """
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT state, COUNT(*) as count
            FROM jobs
            GROUP BY state
        """)
        
        summary = {state.value: 0 for state in JobState}
        for row in cursor.fetchall():
            summary[row[0]] = row[1]
        
        return summary
    
    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job from the database.
        
        Args:
            job_id: Job ID to delete
        
        Returns:
            True if deleted, False if not found
        """
        with self._transaction() as conn:
            cursor = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            return cursor.rowcount > 0
    
    def _row_to_job(self, row: tuple) -> Job:
        """Convert database row to Job object"""
        return Job(
            id=row[0],
            command=row[1],
            state=row[2],
            attempts=row[3],
            max_retries=row[4],
            created_at=row[5],
            updated_at=row[6],
            error_message=row[7],
            worker_id=row[8]
        )
    
    def close(self):
        """Close database connection"""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()