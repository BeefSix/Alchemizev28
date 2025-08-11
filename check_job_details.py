import sqlite3
import json
from datetime import datetime

def check_job_details():
    db_path = 'alchemize.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get the most recent completed videoclip job with full details
        cursor.execute("""
            SELECT id, job_type, status, created_at, updated_at, 
                   progress_details, results, error_message
            FROM jobs 
            WHERE job_type = 'videoclip' AND status = 'COMPLETED'
            ORDER BY updated_at DESC 
            LIMIT 1
        """)
        
        job = cursor.fetchone()
        
        if job:
            job_id, job_type, status, created_at, updated_at, progress_details, results, error_message = job
            
            print(f"\n=== MOST RECENT VIDEOCLIP JOB ===")
            print(f"Job ID: {job_id}")
            print(f"Type: {job_type}")
            print(f"Status: {status}")
            print(f"Created: {created_at}")
            print(f"Updated: {updated_at}")
            
            if progress_details:
                print(f"\nProgress Details:")
                try:
                    progress_data = json.loads(progress_details)
                    print(json.dumps(progress_data, indent=2))
                except:
                    print(progress_details)
            
            if results:
                print(f"\nResults:")
                try:
                    results_data = json.loads(results)
                    print(json.dumps(results_data, indent=2))
                except:
                    print(results)
            
            if error_message:
                print(f"\nError: {error_message}")
        else:
            print("No completed videoclip jobs found")
        
        conn.close()
        
    except Exception as e:
        print(f"Error checking job details: {e}")

if __name__ == "__main__":
    check_job_details()