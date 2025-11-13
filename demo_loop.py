from queuectl.queue import QueueManager
import time, random

print("QueueCTL lightweight demo loop started")
queue = QueueManager()

commands = ["echo Demo cycle", "timeout 1", "exit 1", "nonexistentcommand123"]

while True:
    # Pick a random command
    cmd = random.choice(commands)

    # Enqueue the job (now returns job_id too)
    success, msg, job_id = queue.enqueue({"command": cmd})

    if success:
        # Fetch the job to print timestamps
        job = queue.get_job(job_id) #type:ignore

        print("\nJob Enqueued:")
        print(f"  ID:         {job.id}") #type:ignore
        print(f"  Command:    {job.command}") #type:ignore
        print(f"  State:      {job.state}") #type:ignore
        print(f"  Attempts:   {job.attempts}") #type:ignore
        print(f"  Created At: {job.created_at}") #type:ignore
        print(f"  Updated At: {job.updated_at}") #type:ignore

    else:
        print(f"\n❌ Failed: {msg}")

    # Print queue summary
    status = queue.get_status()
    print(f"\nQueue Summary → Total: {status['total_jobs']} | "
          f"Pending: {status['jobs']['pending']} | DLQ: {status['jobs']['dead']}")

    time.sleep(5)
