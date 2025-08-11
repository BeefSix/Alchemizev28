import sqlite3
import json

def check_user_jobs():
    conn = sqlite3.connect('alchemize.db')
    cursor = conn.cursor()
    
    # Get jobs for merlino874@gmail.com
    cursor.execute('''
        SELECT j.id, j.status, j.results 
        FROM jobs j 
        JOIN users u ON j.user_id = u.id 
        WHERE u.email = 'merlino874@gmail.com' 
        ORDER BY j.created_at DESC 
        LIMIT 3
    ''')
    
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} jobs for merlino874@gmail.com:")
    print("=" * 60)
    
    for job_id, status, results_str in rows:
        print(f"\nJob ID: {job_id}")
        print(f"Status: {status}")
        
        if results_str:
            try:
                results = json.loads(results_str)
                print(f"Results keys: {list(results.keys())}")
                
                # Check for clips
                if 'clips_by_platform' in results:
                    clips_data = results['clips_by_platform']
                    print(f"Clips platforms: {list(clips_data.keys())}")
                    
                    if 'all' in clips_data:
                        clips = clips_data['all']
                        print(f"Total clips: {len(clips)}")
                        if clips:
                            print(f"First clip URL: {clips[0].get('url', 'No URL')}")
                    else:
                        print("No 'all' platform found in clips_by_platform")
                else:
                    print("No clips_by_platform found")
                    
            except json.JSONDecodeError as e:
                print(f"Error parsing results JSON: {e}")
        else:
            print("No results data")
        
        print("-" * 40)
    
    conn.close()

if __name__ == "__main__":
    check_user_jobs()