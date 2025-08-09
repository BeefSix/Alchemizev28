#!/usr/bin/env python3
"""
Quick job status checker - bypasses rate limiting by direct database access
"""

import sqlite3
import sys
from datetime import datetime

def check_job_status(job_id=None):
    """Check specific job status or show recent jobs"""
    
    # Database paths to try
    db_paths = [
        'zuexis.db',
        './zuexis.db', 
        'app/zuexis.db',
        'app.db',
        './app.db',
        'app/app.db'
    ]
    
    db_path = None
    for path in db_paths:
        try:
            conn = sqlite3.connect(path)
            conn.execute("SELECT 1 FROM jobs LIMIT 1")
            db_path = path
            conn.close()
            break
        except:
            continue
    
    if not db_path:
        print("❌ Could not find database file")
        return
    
    print(f"📊 Checking jobs in database: {db_path}")
    print("=" * 60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    if job_id:
        # Check specific job
        cursor.execute("""
            SELECT id, job_type, status, user_id, created_at, progress_details, results, error_message
            FROM jobs 
            WHERE id = ?
        """, (job_id,))
        
        job = cursor.fetchone()
        if job:
            print(f"✅ Job Found: {job_id}")
            print(f"   Type: {job[1]}")
            print(f"   Status: {job[2]}")
            print(f"   User ID: {job[3]}")
            print(f"   Created: {job[4]}")
            print(f"   Progress: {job[5] or 'None'}")
            print(f"   Results: {job[6] or 'None'}")
            print(f"   Error: {job[7] or 'None'}")
        else:
            print(f"❌ Job NOT Found: {job_id}")
    else:
        # Show recent jobs
        cursor.execute("""
            SELECT id, job_type, status, user_id, created_at
            FROM jobs 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        
        jobs = cursor.fetchall()
        print("📋 Recent Jobs (last 10):")
        print("-" * 60)
        
        for i, job in enumerate(jobs, 1):
            print(f"{i:2d}. {job[0][:8]}... | {job[1]:10} | {job[2]:10} | User {job[3]} | {job[4]}")
    
    conn.close()

if __name__ == "__main__":
    job_id = sys.argv[1] if len(sys.argv) > 1 else None
    check_job_status(job_id)