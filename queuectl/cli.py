"""
CLI interface for queuectl using Click
Main entry point for all commands
"""
import click
import json
import multiprocessing
import time
import sys
from tabulate import tabulate

from .queue import QueueManager
from .workers import start_worker
from .config import get_config
from .models import JobState


@click.group()
def cli():
    """
    queuectl - A CLI-based background job queue system
    
    Manage background jobs with workers, retries, and Dead Letter Queue.
    """
    pass


@cli.command()
@click.argument('job_json')
def enqueue(job_json):
    """
    Enqueue a new job.
    
    JOB_JSON: JSON string containing job data
    
    Example:
        queuectl enqueue '{"id":"job1","command":"echo Hello"}'
        queuectl enqueue '{"command":"sleep 5"}'
    """
    queue = QueueManager()
    
    # Parse JSON
    success, result = queue.parse_job_json(job_json)
    if not success:
        click.echo(click.style(result, fg='red'))
        sys.exit(1)
    
    job_data = result
    
    # Enqueue job
    success, message = queue.enqueue(job_data)
    
    if success:
        click.echo(click.style(message, fg='green'))
    else:
        click.echo(click.style(message, fg='red'))
        sys.exit(1)


@cli.group()
def worker():
    """Manage worker processes"""
    pass


@worker.command()
@click.option('--count', '-c', default=1, help='Number of workers to start')
def start(count):
    """
    Start one or more worker processes.
    
    Example:
        queuectl worker start --count 3
    """
    if count < 1:
        click.echo(click.style("Error: Worker count must be at least 1", fg='red'))
        sys.exit(1)
    
    click.echo(f"Starting {count} worker(s)...")
    
    # Start workers in separate processes
    processes = []
    for i in range(count):
        p = multiprocessing.Process(target=start_worker, args=(f"worker-{i+1}",))
        p.start()
        processes.append(p)
        click.echo(f"Started worker-{i+1} (PID: {p.pid})")
    
    click.echo(click.style(f"\n[OK] {count} worker(s) started successfully", fg='green'))
    click.echo("Press Ctrl+C to stop all workers...\n")
    
    try:
        # Wait for all processes
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        click.echo("\n\nStopping workers gracefully...")
        for p in processes:
            p.terminate()
        
        # Wait for graceful shutdown (max 5 seconds)
        for p in processes:
            p.join(timeout=5)
            if p.is_alive():
                p.kill()
        
        click.echo(click.style("[OK] All workers stopped", fg='green'))


@worker.command()
def stop():
    """
    Stop running workers gracefully.
    
    Note: This is handled by Ctrl+C when workers are running.
    For background workers, use system process management tools.
    """
    click.echo("To stop workers, press Ctrl+C in the terminal where they are running.")
    click.echo("Workers will finish their current job before stopping.")


@cli.command()
def status():
    """
    Show queue status summary.
    
    Displays job counts by state and active worker count.
    """
    queue = QueueManager()
    status_info = queue.get_status()
    
    click.echo(click.style("\n=== Queue Status ===", fg='cyan', bold=True))
    click.echo(f"\nTotal Jobs: {status_info['total_jobs']}")
    click.echo(f"Active Workers: {status_info['active_workers']}")
    
    click.echo("\nJobs by State:")
    for state, count in status_info['jobs'].items():
        color = {
            'pending': 'yellow',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'magenta',
            'dead': 'red'
        }.get(state, 'white')
        
        click.echo(f"  {state.capitalize()}: {click.style(str(count), fg=color)}")
    
    click.echo()


@cli.command()
@click.option('--state', '-s', help='Filter by state (pending, processing, completed, failed, dead)')
@click.option('--format', '-f', type=click.Choice(['table', 'json']), default='table', help='Output format')
def list(state, format):
    """
    List jobs, optionally filtered by state.
    
    Example:
        queuectl list --state pending
        queuectl list --format json
    """
    queue = QueueManager()
    
    try:
        jobs = queue.list_jobs(state)
    except ValueError as e:
        click.echo(click.style(f"Error: {e}", fg='red'))
        sys.exit(1)
    
    if not jobs:
        msg = f"No jobs found" + (f" with state '{state}'" if state else "")
        click.echo(click.style(msg, fg='yellow'))
        return
    
    if format == 'json':
        # JSON output
        jobs_data = [job.to_dict() for job in jobs]
        click.echo(json.dumps(jobs_data, indent=2))
    else:
        # Table output
        headers = ['ID', 'Command', 'State', 'Attempts', 'Created At']
        rows = []
        
        for job in jobs:
            # Truncate command if too long
            cmd = job.command if len(job.command) <= 40 else job.command[:37] + "..."
            rows.append([
                job.id,
                cmd,
                job.state,
                f"{job.attempts}/{job.max_retries}",
                job.created_at[:19]  # Remove milliseconds
            ])
        
        click.echo(f"\n{len(jobs)} job(s) found:\n")
        click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
        click.echo()


@cli.group()
def dlq():
    """Manage Dead Letter Queue"""
    pass


@dlq.command(name='list')
@click.option('--format', '-f', type=click.Choice(['table', 'json']), default='table', help='Output format')
def dlq_list(format):
    """
    List all jobs in the Dead Letter Queue.
    
    Example:
        queuectl dlq list
    """
    queue = QueueManager()
    jobs = queue.list_dlq_jobs()
    
    if not jobs:
        click.echo(click.style("No jobs in Dead Letter Queue", fg='green'))
        return
    
    if format == 'json':
        jobs_data = [job.to_dict() for job in jobs]
        click.echo(json.dumps(jobs_data, indent=2))
    else:
        headers = ['ID', 'Command', 'Attempts', 'Error', 'Created At']
        rows = []
        
        for job in jobs:
            cmd = job.command if len(job.command) <= 30 else job.command[:27] + "..."
            error = job.error_message if job.error_message else "N/A"
            error = error if len(error) <= 40 else error[:37] + "..."
            
            rows.append([
                job.id,
                cmd,
                job.attempts,
                error,
                job.created_at[:19]
            ])
        
        click.echo(f"\n{len(jobs)} job(s) in DLQ:\n")
        click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
        click.echo()


@dlq.command(name='retry')
@click.argument('job_id')
def dlq_retry(job_id):
    """
    Retry a job from the Dead Letter Queue.
    
    JOB_ID: ID of the job to retry
    
    Example:
        queuectl dlq retry job1
    """
    queue = QueueManager()
    success, message = queue.retry_dlq_job(job_id)
    
    if success:
        click.echo(click.style(message, fg='green'))
    else:
        click.echo(click.style(message, fg='red'))
        sys.exit(1)


@cli.group()
def config():
    """Manage configuration settings"""
    pass


@config.command(name='set')
@click.argument('key')
@click.argument('value')
def config_set(key, value):
    """
    Set a configuration value.
    
    Available keys: max-retries, backoff-base, worker-poll-interval
    
    Example:
        queuectl config set max-retries 5
        queuectl config set backoff-base 3
    """
    cfg = get_config()
    
    # Map CLI keys to internal keys
    key_map = {
        'max-retries': 'max_retries',
        'backoff-base': 'backoff_base',
        'worker-poll-interval': 'worker_poll_interval'
    }
    
    internal_key = key_map.get(key)
    if not internal_key:
        click.echo(click.style(f"Error: Unknown config key '{key}'", fg='red'))
        click.echo(f"Available keys: {', '.join(key_map.keys())}")
        sys.exit(1)
    
    # Try to convert to int if it looks like a number
    try:
        if value.isdigit():
            value = int(value)
    except:
        pass
    
    cfg.set(internal_key, value)
    click.echo(click.style(f"[OK] Config updated: {key} = {value}", fg='green'))


@config.command(name='get')
@click.argument('key', required=False)
def config_get(key):
    """
    Get configuration value(s).
    
    Example:
        queuectl config get max-retries
        queuectl config get
    """
    cfg = get_config()
    
    if key:
        # Get specific key
        key_map = {
            'max-retries': 'max_retries',
            'backoff-base': 'backoff_base',
            'worker-poll-interval': 'worker_poll_interval'
        }
        
        internal_key = key_map.get(key)
        if not internal_key:
            click.echo(click.style(f"Error: Unknown config key '{key}'", fg='red'))
            sys.exit(1)
        
        value = cfg.get(internal_key)
        click.echo(f"{key}: {value}")
    else:
        # Get all config
        all_config = cfg.get_all()
        click.echo(click.style("\n=== Configuration ===", fg='cyan', bold=True))
        for k, v in all_config.items():
            click.echo(f"  {k}: {v}")
        click.echo()


def main():
    """Main entry point"""
    cli()


if __name__ == '__main__':
    main()