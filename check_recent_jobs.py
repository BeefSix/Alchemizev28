#!/usr/bin/env python3
"""
Check recent jobs in the database to identify problematic entries
"""

import sqlite3
import json
from datetime import datetime

def check_recent_jobs():
    """Check recent jobs for problematic data"""
    
    # Try different database files
    db_files = ['zuexis.db', 'alchemize.db', 'app.db']
    
    for db_file in db_files:
        try:
            print(f"\n🔍 Checking database: {db_file}")
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Check if jobs table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
            if not cursor.fetchone():
                print(f"   ❌ No jobs table found in {db_file}")
                conn.close()
                continue
            
            # Get recent jobs
            cursor.execute("""
                SELECT id, job_type, status, created_at, progress_details, results, error_message
                FROM jobs 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            
            jobs = cursor.fetchall()
            
            if not jobs:
                print(f"   📭 No jobs found in {db_file}")
                conn.close()
                continue
            
            print(f"   📊 Found {len(jobs)} recent jobs:")
            
            for i, job in enumerate(jobs, 1):
                job_id, job_type, status, created_at, progress_details, results, error_message = job
                
                print(f"\n   Job {i}: {job_id[:8]}...")
                print(f"      Type: {job_type}")
                print(f"      Status: {status}")
                print(f"      Created: {created_at}")
                
                # Check progress_details
                if progress_details:
                    print(f"      Progress Details Type: {type(progress_details)}")
                    if isinstance(progress_details, str):
                        try:
                            parsed = json.loads(progress_details)
                            print(f"      Progress Details: Valid JSON with keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'Not a dict'}")
                        except json.JSONDecodeError as e:
                            print(f"      Progress Details: ❌ Invalid JSON - {e}")
                    else:
                        print(f"      Progress Details: ❌ Not a string! Type: {type(progress_details)}")
                        print(f"      Progress Details Value: {progress_details}")
                
                # Check results
                if results:
                    print(f"      Results Type: {type(results)}")
                    if isinstance(results, str):
                        try:
                            parsed = json.loads(results)
                            print(f"      Results: Valid JSON with keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'Not a dict'}")
                        except json.JSONDecodeError as e:
                            print(f"      Results: ❌ Invalid JSON - {e}")
                    else:
                        print(f"      Results: ❌ Not a string! Type: {type(results)}")
                        print(f"      Results Value: {str(results)[:200]}...")
                
                if error_message:
                    print(f"      Error: {error_message[:100]}...")
            
            conn.close()
            return True  # Found and processed jobs
            
        except Exception as e:
            print(f"   ❌ Error accessing {db_file}: {e}")
            continue
    
    print("\n❌ Could not access any database files")
    return False

def check_database_integrity():
    """Check database integrity"""
    
    db_files = ['zuexis.db', 'alchemize.db', 'app.db']
    
    for db_file in db_files:
        try:
            print(f"\n🔍 Checking integrity of: {db_file}")
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Check database integrity
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            
            if result and result[0] == 'ok':
                print(f"   ✅ Database integrity: OK")
            else:
                print(f"   ❌ Database integrity issues: {result}")
            
            # Check jobs table schema
            cursor.execute("PRAGMA table_info(jobs)")
            columns = cursor.fetchall()
            
            print(f"   📋 Jobs table columns:")
            for col in columns:
                print(f"      {col[1]} ({col[2]})")
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"   ❌ Error checking {db_file}: {e}")
            continue
    
    return False

if __name__ == "__main__":
    print("🚀 Checking recent jobs for data issues...")
    
    integrity_ok = check_database_integrity()
    if integrity_ok:
        jobs_checked = check_recent_jobs()
        if jobs_checked:
            print("\n✅ Job data analysis complete.")
        else:
            print("\n❌ Could not analyze job data.")
    else:
        print("\n❌ Database integrity check failed.")