import sqlite3
import json

def check_video_jobs():
    try:
        conn = sqlite3.connect('alchemize.db')
        cursor = conn.cursor()
        
        # Check for completed video jobs
        cursor.execute("""
            SELECT id, status, job_type, user_id, results, created_at 
            FROM jobs 
            WHERE job_type = 'videoclip' AND status = 'COMPLETED' 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        
        jobs = cursor.fetchall()
        
        print(f"Found {len(jobs)} completed video jobs:")
        
        for job in jobs:
            job_id, status, job_type, user_id, results, created_at = job
            print(f"\nJob ID: {job_id}")
            print(f"Status: {status}")
            print(f"User ID: {user_id}")
            print(f"Created: {created_at}")
            
            if results:
                try:
                    results_data = json.loads(results)
                    clips_data = results_data.get('clips_by_platform', {})
                    all_clips = clips_data.get('all', [])
                    print(f"Clips found: {len(all_clips)}")
                    if all_clips:
                        print(f"First clip URL: {all_clips[0].get('url', 'No URL')}")
                except Exception as e:
                    print(f"Error parsing results: {e}")
            else:
                print("No results data")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_video_jobs()