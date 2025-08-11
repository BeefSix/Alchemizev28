import sqlite3
import json
import os

def check_clips():
    conn = sqlite3.connect('alchemize.db')
    cursor = conn.cursor()
    
    # Get completed jobs with results
    cursor.execute('''
        SELECT id, results FROM jobs 
        WHERE status = 'COMPLETED' 
        AND results IS NOT NULL 
        AND results != '{}' 
        LIMIT 3
    ''')
    
    rows = cursor.fetchall()
    
    for job_id, results_str in rows:
        print(f"\n=== JOB {job_id} ===")
        try:
            results = json.loads(results_str)
            print(f"Results keys: {list(results.keys())}")
            
            # Check for clips in different locations
            clips = []
            if 'clips_by_platform' in results:
                print("Found clips_by_platform")
                for platform, platform_clips in results['clips_by_platform'].items():
                    print(f"  Platform {platform}: {len(platform_clips) if isinstance(platform_clips, list) else 'not a list'}")
                    if isinstance(platform_clips, list):
                        clips.extend(platform_clips)
            
            if 'clips' in results:
                print(f"Found clips array: {len(results['clips'])}")
                clips.extend(results['clips'])
            
            if 'generated_clips' in results:
                print(f"Found generated_clips: {len(results['generated_clips'])}")
                clips.extend(results['generated_clips'])
            
            print(f"Total clips found: {len(clips)}")
            
            # Check first few clips
            for i, clip in enumerate(clips[:3]):
                print(f"  Clip {i+1}:")
                print(f"    Keys: {list(clip.keys()) if isinstance(clip, dict) else 'not a dict'}")
                if isinstance(clip, dict):
                    url = clip.get('url') or clip.get('file_path') or clip.get('path')
                    print(f"    URL/Path: {url}")
                    if url and os.path.exists(url.replace('http://localhost:8001', '.')):
                        print(f"    File exists: YES")
                    else:
                        print(f"    File exists: NO")
                        
        except Exception as e:
            print(f"Error parsing results: {e}")
    
    conn.close()

if __name__ == '__main__':
    check_clips()