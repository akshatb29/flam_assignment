import sqlite3
from tabulate import tabulate

conn = sqlite3.connect('jobs.db')
cursor = conn.cursor()

# Get all jobs
cursor.execute("SELECT id, command, state, attempts, max_retries, error_message FROM jobs")
rows = cursor.fetchall()

headers = ['ID', 'Command', 'State', 'Attempts', 'Max Retries', 'Error']
print("\n📊 All Jobs in Database:\n")
print(tabulate(rows, headers=headers, tablefmt='grid'))

# Summary by state
cursor.execute("SELECT state, COUNT(*) FROM jobs GROUP BY state")
summary = cursor.fetchall()

print("\n📈 Summary by State:\n")
print(tabulate(summary, headers=['State', 'Count'], tablefmt='grid'))

conn.close()