Demo link - https://drive.google.com/file/d/1HXMg9XOK_vER1nPxsEOAOSFhHj3vcDpD/view?usp=sharing


🎯 Overview

QueueCTL is a minimal yet production-inspired background job queue system, built from scratch using Python.

It provides:

A reliable job queue with persistent storage

Multiple worker processes for parallel execution

Retry mechanism with exponential backoff

Dead Letter Queue (DLQ) for permanently failed jobs

A clean and intuitive CLI interface (queuectl)

SQLite-backed persistence across restarts

Configurable runtime settings (max retries, backoff base, polling interval)

This project models how real-world systems like Celery, Sidekiq, or BullMQ work internally — but implemented cleanly and simply for demonstration and learning.

🧩 Features

✔ Enqueue jobs via CLI

✔ Execute commands in worker processes

✔ Track job states: pending → processing → completed/failed/dead

✔ Automatic retries with exponential backoff (2^n)

✔ Dead Letter Queue for failures after max attempts

✔ Persistent SQLite database (jobs.db)

✔ JSON-based configuration

✔ Multiple workers with concurrency-safe job locking

✔ Graceful worker shutdown

✔ Full CLI: enqueue, worker start/stop, status, list jobs, DLQ retry/list, config set/get

✔ Color-coded, table-formatted output

✔ Test scripts + demo loop for continuous processing

📦 Installation & Setup
1. Clone the repository
git clone https://github.com/yourusername/queuectl.git
cd queuectl

2. Install dependencies
pip install -r requirements.txt

3. Install the CLI globally (development mode)
pip install -e .


This creates a global command:

queuectl

4. Verify installation
queuectl --help

🚀 Usage Examples
1. Enqueue a job
queuectl enqueue '{"command": "echo Hello World"}'

2. Start workers

Start 2 workers:

queuectl worker start --count 2


Workers will continuously pick jobs, retry failures, and move dead jobs to DLQ.

3. Check system status
queuectl status


Example Output:

=== Queue Status ===
Total Jobs: 12
Active Workers: 2

Jobs by State:
  Pending:    3
  Processing: 1
  Completed: 5
  Dead:       3

4. List pending jobs
queuectl list --state pending

5. List DLQ
queuectl dlq list

6. Retry a DLQ job
queuectl dlq retry job-abc123

7. Set config values
queuectl config set max-retries 5
queuectl config set backoff-base 3

🏗️ Architecture Overview

QueueCTL is built using a clean multi-layer architecture:

1. models.py — Job Model & State Machine

Defines the core Job dataclass:

id

command

state

attempts

max_retries

timestamps (created_at, updated_at)

error_message

worker_id

Includes helper methods:

mark_processing(worker_id)

mark_completed()

mark_failed(error)

should_retry()

to_dict() / from_dict()

This makes each job behave like a small state machine.

2. config.py — Config Management

Stores user config in:

~/.queuectl/config.json


Includes:

max_retries

backoff_base

worker_poll_interval

db_path

Uses a global singleton to avoid repeated disk reads.

3. storage.py — SQLite Persistence Layer

Handles all durable storage:

Creates SQLite DB (jobs.db)

Enables WAL mode for concurrent read/write

Handles race-free job claiming with:

BEGIN IMMEDIATE;
SELECT ... FOR UPDATE;
UPDATE ... SET state="processing"


This prevents duplicate processing across workers.

Key methods:

add_job(job)

get_job(id)

update_job(job)

get_next_pending_job(worker_id) (atomic claim)

delete_job(id)

list_jobs(state)

4. queue.py — High-Level Queue API

Implements business logic:

Validates input

Generates IDs

Applies config defaults

Converts dict → Job objects

DLQ helpers:

list_dlq_jobs()

retry_dlq_job()

Acts as the API layer between CLI and storage.

5. worker.py — Worker Engine

Core worker loop:

while running:
    job = storage.get_next_pending_job()
    backoff = backoff_base ** attempts
    execute command using subprocess
    update job state


Handles:

Exponential backoff

Retry logic

SIGINT/SIGTERM graceful shutdown

Command execution

Error capture

DLQ movement

Each worker is an isolated process.

6. cli.py — Command Line Interface

Built using Click.

Commands include:

enqueue

worker start/stop

status

list

dlq list/retry

config get/set

Provides table formatting, color output, and user-friendly UX.

7. demo_loop.py — Continuous Demo Script

Runs a loop that:

Randomly generates jobs

Shows queue growing

Shows timestamps

Demonstrates worker behavior

Useful for demo video.

🔄 Job Lifecycle
pending → processing → completed
                    → failed → retry → processing
                    → (after max retries) → dead (DLQ)


All changes are timestamped and persisted.

⚙️ Retry & Backoff

For attempt n:

delay = backoff_base ^ n


Example with base=2:

2s → 4s → 8s → 16s → move to DLQ

📁 Database Persistence

Jobs are stored in:

jobs.db


Restarting workers does not lose data.

Completed, failed, dead, pending — all preserved.

📉 Assumptions & Trade-offs
✔ SQLite chosen for simplicity

Easy to embed, zero setup, safe concurrency with WAL mode.

✔ Focused on CLI workflow

No web dashboard (optional bonus).

✔ No scheduling or priority queues

Simplified for interview-style demonstration.

✔ One job executed at a time per worker

But multiple workers can run in parallel.

✔ Exponential backoff exponential growth

This is intentional for real-world retry logic.

🧪 Testing Instructions
1. Enqueue a successful job
queuectl enqueue '{"command":"echo Hello"}'

2. Enqueue a failing job
queuectl enqueue '{"command":"exit 1"}'

3. Start workers
queuectl worker start --count 2

4. Watch retries + DLQ
queuectl dlq list

5. Retry DLQ job
queuectl dlq retry job-abc123

6. Restart the system

Stop workers, restart terminal:
Check persistence:

queuectl status
