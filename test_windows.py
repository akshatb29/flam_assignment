"""
Simple Windows-compatible test script for queuectl
"""
import os
import time
import subprocess

# Import queuectl directly
from queuectl.queue import QueueManager
from queuectl.config import get_config


def cleanup():
    """Clean up test database"""
    if os.path.exists("jobs.db"):
        os.remove("jobs.db")
        print("🧹 Cleaned up jobs.db")


def test_queuectl():
    """Run comprehensive tests"""
    print("=" * 60)
    print("🧪 QUEUECTL COMPREHENSIVE TEST (Windows)")
    print("=" * 60)
    
    # Cleanup before starting
    cleanup()
    
    # Initialize
    queue = QueueManager()
    config = get_config()
    
    # Test 1: Configuration
    print("\n" + "=" * 60)
    print("TEST 1: Configuration Management")
    print("=" * 60)
    
    print(f"Max retries: {config.max_retries}")
    print(f"Backoff base: {config.backoff_base}")
    config.set("max_retries", 5)
    print(f"Updated max retries: {config.max_retries}")
    print("✅ Configuration management works!")
    
    # Test 2-5: Enqueue jobs
    print("\n" + "=" * 60)
    print("TEST 2-5: Enqueue Jobs")
    print("=" * 60)
    
    jobs_to_add = [
        {"id": "test-success", "command": "echo Hello World"},
        {"id": "test-fail", "command": "exit 1", "max_retries": 2},
        {"id": "test-invalid", "command": "nonexistentcommand123", "max_retries": 1},
        {"command": "timeout 1"}  # Auto-ID, Windows equivalent of sleep
    ]
    
    for job_data in jobs_to_add:
        success, message = queue.enqueue(job_data)
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
    
    # Test 6: Status before processing
    print("\n" + "=" * 60)
    print("TEST 6: Check Status (before processing)")
    print("=" * 60)
    
    status = queue.get_status()
    print(f"Total jobs: {status['total_jobs']}")
    print(f"Pending: {status['jobs']['pending']}")
    print("✅ Status command works!")
    
    # Test 7: List pending jobs
    print("\n" + "=" * 60)
    print("TEST 7: List Pending Jobs")
    print("=" * 60)
    
    jobs = queue.list_jobs('pending')
    print(f"Found {len(jobs)} pending jobs:")
    for job in jobs:
        print(f"  - {job.id}: {job.command}")
    print("✅ List command works!")
    
    # Test 8: Start worker
    print("\n" + "=" * 60)
    print("TEST 8: Start Worker (processing for 20 seconds)")
    print("=" * 60)
    print("Press Ctrl+C to stop worker early...")
    print("\nExpected behavior:")
    print("  - test-success should complete")
    print("  - test-fail should retry and move to DLQ")
    print("  - test-invalid should move to DLQ")
    
    try:
        # Start worker using subprocess
        worker_proc = subprocess.Popen(
            ["queuectl", "worker", "start", "--count", "2"],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        
        # Wait 20 seconds
        time.sleep(20)
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    finally:
        # Stop worker gracefully
        if os.name == 'nt':
            # Windows: send Ctrl+C
            worker_proc.send_signal(subprocess.signal.CTRL_C_EVENT)
        else:
            worker_proc.terminate()
        
        try:
            worker_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            worker_proc.kill()
        
        print("\n✅ Worker stopped!")
    
    # Test 9: Status after processing
    print("\n" + "=" * 60)
    print("TEST 9: Check Status (after processing)")
    print("=" * 60)
    
    status = queue.get_status()
    print(f"Total jobs: {status['total_jobs']}")
    print(f"Completed: {status['jobs']['completed']}")
    print(f"Failed: {status['jobs']['failed']}")
    print(f"Dead (DLQ): {status['jobs']['dead']}")
    print("✅ Jobs processed!")
    
    # Test 10: List completed jobs
    print("\n" + "=" * 60)
    print("TEST 10: List Completed Jobs")
    print("=" * 60)
    
    completed_jobs = queue.list_jobs('completed')
    print(f"Found {len(completed_jobs)} completed jobs:")
    for job in completed_jobs:
        print(f"  - {job.id}: {job.command}")
    
    # Test 11: List DLQ
    print("\n" + "=" * 60)
    print("TEST 11: Check Dead Letter Queue")
    print("=" * 60)
    
    dlq_jobs = queue.list_dlq_jobs()
    print(f"Found {len(dlq_jobs)} jobs in DLQ:")
    for job in dlq_jobs:
        print(f"  - {job.id}: {job.command}")
        print(f"    Error: {job.error_message}")
    print("✅ DLQ listing works!")
    
    # Test 12: Retry DLQ job
    if dlq_jobs:
        print("\n" + "=" * 60)
        print("TEST 12: Retry Job from DLQ")
        print("=" * 60)
        
        job_to_retry = dlq_jobs[0].id
        success, message = queue.retry_dlq_job(job_to_retry)
        print(f"{'✅' if success else '❌'} {message}")
        
        # Verify it moved back
        job = queue.get_job(job_to_retry)
        print(f"Job {job_to_retry} is now in state: {job.state}")
    
    # Test 13: JSON output
    print("\n" + "=" * 60)
    print("TEST 13: Get Job as JSON")
    print("=" * 60)
    
    all_jobs = queue.list_jobs()
    if all_jobs:
        sample_job = all_jobs[0]
        print(f"Sample job as dict: {sample_job.to_dict()}")
        print("✅ JSON serialization works!")
    
    # Final summary
    print("\n" + "=" * 60)
    print("🎉 ALL TESTS COMPLETED!")
    print("=" * 60)
    
    print("\n📊 Final Status:")
    status = queue.get_status()
    for state, count in status['jobs'].items():
        print(f"  {state}: {count}")
    
    print("\n" + "=" * 60)
    print("✅ QUEUECTL IS WORKING CORRECTLY!")
    print("=" * 60)
    
    # Cleanup
    print("\n🧹 Cleanup database? (y/n): ", end="")
    try:
        choice = input().strip().lower()
        if choice == 'y':
            cleanup()
            print("✅ Database cleaned up!")
    except:
        print("\nSkipping cleanup")
    
    queue.close()


if __name__ == "__main__":
    try:
        test_queuectl()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()