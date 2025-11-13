Demo link - https://drive.google.com/file/d/1HXMg9XOK_vER1nPxsEOAOSFhHj3vcDpD/view?usp=sharing

🚀 QueueCTL — Lightweight Job Queue with Workers, Retries & DLQ

QueueCTL is a minimal, production-ready background job queue built with Python.
It supports persistent storage, multiple workers, automatic retries with exponential backoff, and a Dead Letter Queue (DLQ), all accessible via a simple CLI.

🔧 1. Setup Instructions
Install dependencies
pip install -r requirements.txt

Install the CLI
pip install -e .

Verify installation
queuectl --help

📦 2. Usage Examples
Enqueue jobs
queuectl enqueue '{"command": "echo Hello"}'
queuectl enqueue '{"command": "exit 1"}'
queuectl enqueue '{"command": "nonexistentcommand123"}'

Check queue status
queuectl status

List jobs
queuectl list --state pending
queuectl dlq list

Start workers
queuectl worker start --count 2

Retry a DLQ job
queuectl dlq retry <job_id>

Update configuration
queuectl config set max-retries 5

🏛 3. Architecture Overview
Job Lifecycle

pending → waiting for worker

processing → actively executing

completed → finished successfully

failed → failed but retryable

dead → permanently failed (DLQ)

Workers

Poll for pending/failed jobs

Execute commands using subprocess

Apply exponential backoff (delay = base^attempts)

Move exhausted jobs to DLQ

Graceful shutdown support

Persistence

Jobs stored in SQLite (jobs.db)

WAL mode for safe concurrent worker access

All fields stored: id, command, state, attempts, timestamps, error, worker_id

CLI Layer

Powered by Click

Provides enqueue, listing, config, worker management, DLQ tools

⚖️ 4. Assumptions & Trade-offs

SQLite selected for simplicity & reliability (no external dependencies).

FIFO job ordering (no priorities implemented).

Commands executed via shell; assumes worker OS supports them.

No scheduling (run_at) added for simplicity.

Backoff is exponential and non-configurable per job (config-based only).

🧪 5. Testing Instructions
Manual tests

Enqueue multiple job types (success, fail, invalid commands).

Start workers and observe:

job processing

retries with backoff

jobs moving to DLQ

Retry DLQ job and confirm it moves back to pending.

Stop/start workers and confirm job persistence.

Modify config (e.g., max retries) and verify effect.

Recommended demo

Run the auto-generator script:

python demo_loop.py


Then inspect DB:

python view_db.py
