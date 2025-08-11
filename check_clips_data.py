import sqlite3
import json
from datetime import datetime

def check_clips_data():
    db_path = 'alchemize.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get the most recent completed videoclip job
        cursor.execute("""
            SELECT id, results
            FROM jobs 
            WHERE job_type = 'videoclip' AND status = 'COMPLETED'
            ORDER BY updated_at DESC 
            LIMIT 1
        """)
        
        job = cursor.fetchone()
        
        if job:
            job_id, results = job
            
            print(f"\n=== CHECKING CLIPS DATA FOR JOB {job_id} ===")
            
            if results:
                try:
                    results_data = json.loads(results)
                    
                    # Check for clips data
                    if 'clips_by_platform' in results_data:
                        clips_data = results_data['clips_by_platform']
                        print(f"\nClips by platform found:")
                        
                        for platform, clips in clips_data.items():
                            print(f"\n{platform.upper()} Platform:")
                            if isinstance(clips, list):
                                print(f"  Number of clips: {len(clips)}")
                                for i, clip in enumerate(clips):
                                    print(f"  Clip {i+1}:")
                                    if isinstance(clip, dict):
                                        for key, value in clip.items():
                                            if key == 'url':
                                                print(f"    {key}: {value}")
                                            elif key in ['duration', 'file_size', 'captions_added']:
                                                print(f"    {key}: {value}")
                            else:
                                print(f"  Clips data: {clips}")
                    else:
                        print("\nNo 'clips_by_platform' found in results")
                        print("Available keys in results:")
                        for key in results_data.keys():
                            print(f"  - {key}")
                    
                    # Check total clips
                    if 'total_clips' in results_data:
                        print(f"\nTotal clips: {results_data['total_clips']}")
                    
                except Exception as e:
                    print(f"Error parsing results JSON: {e}")
                    print(f"Raw results: {results[:500]}...")
            else:
                print("No results data found")
        else:
            print("No completed videoclip jobs found")
        
        conn.close()
        
    except Exception as e:
        print(f"Error checking clips data: {e}")

if __name__ == "__main__":
    check_clips_data()