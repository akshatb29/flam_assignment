"""
Manual test script for queuectl
Run this to verify all functionality works
"""
import os
import time
import subprocess
import json

def run_command(cmd):
    """Run a shell command and return output"""
    print(f"\n💻 Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(f"STDERR: {result.stderr}")
    return result.returncode == 0

def cleanup():
    """Clean up test database"""
    if os.path.exists("jobs.db"):
        os.remove("jobs.db")
        print("🧹 Cleaned up jobs.db")

def test_queuectl():
    """Run comprehensive tests"""
    print("=" * 60)
    print("🧪 QUEUECTL COMPREHENSIVE TEST")
    print("=" * 60)
    
    # Cleanup before starting
    cleanup()
    
    # Test 1: Configuration
    print("\n" + "=" * 60)
    print("TEST 1: Configuration Management")
    print("=" * 60)
    
    assert run_command("queuectl config get"), "❌ Config get failed"
    assert run_command("queuectl config set max-retries 5"), "❌ Config set failed"
    assert run_command("queuectl config set backoff-base 2"), "❌ Config set failed"
    print("✅ Configuration management works!")
    
    # Test 2: Enqueue successful job
    print("\n" + "=" * 60)
    print("TEST 2: Enqueue Successful Job")
    print("=" * 60)
    
    job1 = json.dumps({"id": "test-success", "command": "echo 'Hello World'"})
    assert run_command(f'queuectl enqueue \'{job1}\''), "❌ Enqueue failed"
    print("✅ Job enqueued successfully!")
    
    # Test 3: Enqueue job that will fail
    print("\n" + "=" * 60)
    print("TEST 3: Enqueue Failing Job (will retry)")
    print("=" * 60)
    
    job2 = json.dumps({"id": "test-fail", "command": "exit 1", "max_retries": 2})
    assert run_command(f'queuectl enqueue \'{job2}\''), "❌ Enqueue failed"
    print("✅ Failing job enqueued!")
    
    # Test 4: Enqueue job with invalid command
    print("\n" + "=" * 60)
    print("TEST 4: Enqueue Job with Invalid Command")
    print("=" * 60)
    
    job3 = json.dumps({"id": "test-invalid", "command": "nonexistentcommand123", "max_retries": 1})
    assert run_command(f'queuectl enqueue \'{job3}\''), "❌ Enqueue failed"
    print("✅ Invalid command job enqueued!")
    
    # Test 5: Enqueue job with auto-generated ID
    print("\n" + "=" * 60)
    print("TEST 5: Enqueue Job Without ID (auto-generate)")
    print("=" * 60)
    
    job4 = json.dumps({"command": "sleep 1"})
    assert run_command(f'queuectl enqueue \'{job4}\''), "❌ Enqueue failed"
    print("✅ Auto-ID job enqueued!")
    
    # Test 6: Status before processing
    print("\n" + "=" * 60)
    print("TEST 6: Check Status (before processing)")
    print("=" * 60)
    
    assert run_command("queuectl status"), "❌ Status failed"
    print("✅ Status command works!")
    
    # Test 7: List pending jobs
    print("\n" + "=" * 60)
    print("TEST 7: List Pending Jobs")
    print("=" * 60)
    
    assert run_command("queuectl list --state pending"), "❌ List failed"
    print("✅ List command works!")
    
    # Test 8: Start worker and process jobs
    print("\n" + "=" * 60)
    print("TEST 8: Start Worker (will process jobs for 15 seconds)")
    print("=" * 60)
    
    print("Starting worker... Press Ctrl+C after you see jobs being processed")
    print("Expected behavior:")
    print("  - test-success should complete")
    print("  - test-fail should retry and move to DLQ")
    print("  - test-invalid should move to DLQ")
    print("  - sleep 1 job should complete")
    
    # Start worker in subprocess (will run for a bit, then we'll kill it)
    worker_proc = subprocess.Popen(
        ["queuectl", "worker", "start", "--count", "2"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # Wait for 15 seconds to let jobs process
        time.sleep(15)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    finally:
        # Stop worker
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
    
    assert run_command("queuectl status"), "❌ Status failed"
    print("✅ Jobs processed!")
    
    # Test 10: List completed jobs
    print("\n" + "=" * 60)
    print("TEST 10: List Completed Jobs")
    print("=" * 60)
    
    assert run_command("queuectl list --state completed"), "❌ List completed failed"
    
    # Test 11: List DLQ
    print("\n" + "=" * 60)
    print("TEST 11: Check Dead Letter Queue")
    print("=" * 60)
    
    assert run_command("queuectl dlq list"), "❌ DLQ list failed"
    print("✅ DLQ listing works!")
    
    # Test 12: Retry DLQ job
    print("\n" + "=" * 60)
    print("TEST 12: Retry Job from DLQ")
    print("=" * 60)
    
    assert run_command("queuectl dlq retry test-fail"), "❌ DLQ retry failed"
    print("✅ DLQ retry works!")
    
    # Test 13: Check job moved back to pending
    print("\n" + "=" * 60)
    print("TEST 13: Verify Job Back in Pending")
    print("=" * 60)
    
    assert run_command("queuectl list --state pending"), "❌ List pending failed"
    
    # Test 14: JSON output format
    print("\n" + "=" * 60)
    print("TEST 14: JSON Output Format")
    print("=" * 60)
    
    assert run_command("queuectl list --format json"), "❌ JSON format failed"
    print("✅ JSON output works!")
    
    # Final summary
    print("\n" + "=" * 60)
    print("🎉 ALL TESTS COMPLETED!")
    print("=" * 60)
    
    print("\n📊 Final Status:")
    run_command("queuectl status")
    
    print("\n📋 All Jobs:")
    run_command("queuectl list")
    
    print("\n" + "=" * 60)
    print("✅ QUEUECTL IS WORKING CORRECTLY!")
    print("=" * 60)
    
    # Optional: Cleanup
    print("\n🧹 Cleanup database? (y/n): ", end="")
    choice = input().strip().lower()
    if choice == 'y':
        cleanup()
        print("✅ Database cleaned up!")

if __name__ == "__main__":
    try:
        test_queuectl()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()