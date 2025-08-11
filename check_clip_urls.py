#!/usr/bin/env python3
"""
Check clip URLs from recent jobs to see where files should be
"""

import sqlite3
import json
import os
from pathlib import Path

def check_clip_urls():
    """Check clip URLs from recent completed jobs"""
    
    db_files = ['zuexis.db', 'alchemize.db', 'app.db']
    
    for db_file in db_files:
        try:
            print(f"\n🔍 Checking clip URLs in: {db_file}")
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Get recent completed video jobs with results
            cursor.execute("""
                SELECT id, job_type, status, results
                FROM jobs 
                WHERE job_type = 'videoclip' 
                AND status = 'COMPLETED' 
                AND results IS NOT NULL
                ORDER BY created_at DESC 
                LIMIT 5
            """)
            
            jobs = cursor.fetchall()
            
            if not jobs:
                print(f"   📭 No completed video jobs found in {db_file}")
                conn.close()
                continue
            
            print(f"   📊 Found {len(jobs)} completed video jobs:")
            
            for i, job in enumerate(jobs, 1):
                job_id, job_type, status, results = job
                
                print(f"\n   Job {i}: {job_id[:8]}...")
                
                if results:
                    try:
                        results_data = json.loads(results)
                        clips_by_platform = results_data.get('clips_by_platform', {})
                        
                        if 'all' in clips_by_platform:
                            clips = clips_by_platform['all']
                            print(f"      Found {len(clips)} clips:")
                            
                            for j, clip in enumerate(clips, 1):
                                url = clip.get('url', 'No URL')
                                file_size = clip.get('file_size', 'Unknown size')
                                success = clip.get('success', False)
                                
                                print(f"         Clip {j}: {url}")
                                print(f"                  Size: {file_size} bytes")
                                print(f"                  Success: {success}")
                                
                                # Check if file actually exists
                                if url.startswith('/static/'):
                                    # Convert URL to file path
                                    file_path = url.replace('/static/', 'static/')
                                    file_path = file_path.replace('/', os.sep)  # Handle Windows paths
                                    
                                    full_path = os.path.join(os.getcwd(), file_path)
                                    exists = os.path.exists(full_path)
                                    
                                    print(f"                  File path: {full_path}")
                                    print(f"                  File exists: {exists}")
                                    
                                    if exists:
                                        actual_size = os.path.getsize(full_path)
                                        print(f"                  Actual size: {actual_size} bytes")
                                    else:
                                        print(f"                  ❌ File not found!")
                                        
                                        # Check if file exists in other common locations
                                        possible_paths = [
                                            os.path.join('static', 'generated', os.path.basename(url)),
                                            os.path.join('uploads', os.path.basename(url)),
                                            os.path.join('temp', os.path.basename(url)),
                                            os.path.basename(url)  # Current directory
                                        ]
                                        
                                        for possible_path in possible_paths:
                                            if os.path.exists(possible_path):
                                                print(f"                  ✅ Found at: {possible_path}")
                                                break
                                        else:
                                            print(f"                  ❌ File not found in any common location")
                        else:
                            print(f"      No 'all' clips found in results")
                            print(f"      Available keys: {list(clips_by_platform.keys())}")
                    
                    except json.JSONDecodeError as e:
                        print(f"      ❌ Invalid JSON in results: {e}")
                else:
                    print(f"      No results data")
            
            conn.close()
            return True  # Found and processed jobs
            
        except Exception as e:
            print(f"   ❌ Error accessing {db_file}: {e}")
            continue
    
    print("\n❌ Could not access any database files")
    return False

if __name__ == "__main__":
    print("🚀 Checking clip URLs and file locations...")
    check_clip_urls()