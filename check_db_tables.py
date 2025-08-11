import sqlite3
import os
import json

# Check current job status
conn = sqlite3.connect('alchemize.db')
cursor = conn.cursor()

# Check for active jobs
print("=== ACTIVE JOBS ===")
cursor.execute("SELECT id, job_type, status, created_at, progress_details FROM jobs WHERE status = 'IN_PROGRESS' ORDER BY created_at DESC LIMIT 5")
active_jobs = cursor.fetchall()

if active_jobs:
    for job in active_jobs:
        job_id, job_type, status, created_at, progress_details = job
        print(f"\nJob ID: {job_id[:8]}...")
        print(f"Type: {job_type}")
        print(f"Status: {status}")
        print(f"Created: {created_at}")
        if progress_details:
            try:
                progress = json.loads(progress_details) if isinstance(progress_details, str) else progress_details
                print(f"Progress: {progress.get('percentage', 0)}% - {progress.get('description', 'Processing...')}")
            except:
                print(f"Progress: {progress_details[:100]}...")
else:
    print("No active jobs found")

# Check most recent completed jobs
print("\n=== RECENT COMPLETED JOBS ===")
cursor.execute("SELECT id, job_type, status, created_at, progress_details FROM jobs WHERE status = 'COMPLETED' ORDER BY created_at DESC LIMIT 3")
recent_jobs = cursor.fetchall()

for job in recent_jobs:
    job_id, job_type, status, created_at, progress_details = job
    print(f"\nJob ID: {job_id[:8]}... | Type: {job_type} | Completed: {created_at}")
    if progress_details:
        try:
            progress = json.loads(progress_details) if isinstance(progress_details, str) else progress_details
            print(f"Final: {progress.get('description', 'Completed')}")
        except:
            print(f"Details: {progress_details[:100]}...")

conn.close()