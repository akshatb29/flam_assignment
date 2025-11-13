
# ⚡ QueueCTL — Lightweight Job Queue System with Workers, Retries & DLQ

QueueCTL is a minimal, production-ready background job processing system.
It supports persistent storage, multiple workers, automatic retries with exponential backoff, and a Dead Letter Queue (DLQ).
The entire system is accessible through a clean and powerful CLI.

demo link - https://drive.google.com/file/d/1HXMg9XOK_vER1nPxsEOAOSFhHj3vcDpD/view?usp=sharing

---

## ⭐ Features

* **Job Enqueueing:** Add jobs that run shell commands.
* **Parallel Workers:** Start multiple workers to process jobs concurrently.
* **Automatic Retries:** Failed jobs retry with exponential backoff (`base^attempts`).
* **Dead Letter Queue (DLQ):** Jobs exceeding `max_retries` are moved to DLQ for later inspection.
* **SQLite Persistence:** Jobs survive restarts and crashes via durable storage.
* **CLI Interface:** Manage jobs, workers, configuration, and DLQ with a simple command-line tool.
* **Configurable:** Modify retry limits, backoff base, and worker polling via config commands.

---

## 🔄 How It Works

1. A job is enqueued with a shell command (`echo Hello`, `timeout 1`, etc.).
2. A worker picks the next pending job and marks it as `processing`.
3. The job is executed via `subprocess`.
4. If the job:

   * **Succeeds:** → state becomes `completed`
   * **Fails:** → worker retries after exponential backoff
   * **Exceeds retries:** → moved to `dead` (DLQ)
5. SQLite ensures no duplicate processing and keeps full job history.

Jobs move through this lifecycle:

```
pending → processing → completed
              ↓
           failed → dead (DLQ)
```

---

## 🚀 Setup Instructions

### 1. Install dependencies

```
pip install -r requirements.txt
```

### 2. Install QueueCTL CLI

```
pip install -e .
```

### 3. Verify installation

```
queuectl --help
```

---

## 💻 Usage

### Enqueue jobs

```
queuectl enqueue '{"command":"echo Hello"}'
queuectl enqueue '{"command":"exit 1"}'
queuectl enqueue '{"command":"nonexistentcommand123"}'
```
or run the test script loop

```
python test.py
```

### Start workers

```
queuectl worker start --count 3
```

### Check queue status

```
queuectl status
```

### List jobs by state

```
queuectl list --state pending
queuectl dlq list
```

### Retry a DLQ job

```
queuectl dlq retry <job_id>
```

### Update configuration

```
queuectl config set max-retries 5
```

---

## 🧱 Architecture Overview

### Core Components

#### **1. Queue Manager**

* Validates and enqueues new jobs.
* Handles DLQ operations.
* Provides queue statistics.

#### **2. Workers**

* Execute shell commands.
* Apply exponential backoff on failures.
* Update job states safely using atomic DB operations.

#### **3. Storage Layer (SQLite)**

* WAL mode for concurrency.
* Stores all job metadata:
* Persistent storage

  * `id`, `command`, `state`, `attempts`
  * `created_at`, `updated_at`
  * `error_message`, `worker_id`

#### **4. CLI**

* Entry point for enqueueing, listing, inspecting, retrying, and worker control.

---

## ⚖ Assumptions & Trade-offs

* SQLite chosen for simplicity and reliability over distributed environments.
* No job priorities (FIFO only).
* No scheduling or delays beyond retry backoff.
* Designed to be minimal but production-ready for single-machine workloads.

---

## 🧪 Testing Instructions

To verify functionality:

1. **Enqueue success + failure jobs**

   * echo, timeout, exit 1, nonexistent commands.
2. **Start 1–2 workers** and confirm:

   * Jobs complete correctly.
   * Retry behavior works.
   * DLQ is populated.
3. **Retry DLQ jobs** and ensure they return to pending.
4. **Restart workers or CLI** to confirm job persistence.
5. Run the continuous demo:

   ```
   python demo_loop.py
   ```
6. Inspect database:

   ```
   python view_db.py
   ```

---
