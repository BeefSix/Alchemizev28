#!/usr/bin/env python3
import sqlite3
import json

def check_results_structure():
    try:
        conn = sqlite3.connect('alchemize.db')
        cursor = conn.cursor()
        
        # Get the most recent completed videoclip job
        cursor.execute("""
            SELECT id, results FROM jobs 
            WHERE job_type = 'videoclip' AND status = 'COMPLETED' 
            ORDER BY created_at DESC LIMIT 1
        """)
        
        row = cursor.fetchone()
        if row:
            job_id, results_json = row
            print(f"Job ID: {job_id}")
            
            if results_json:
                try:
                    results = json.loads(results_json)
                    print("\nResults structure:")
                    print(f"- clips_by_platform exists: {'clips_by_platform' in results}")
                    
                    if 'clips_by_platform' in results:
                        clips_by_platform = results['clips_by_platform']
                        print(f"- clips_by_platform.all exists: {'all' in clips_by_platform}")
                        print(f"- clips_by_platform keys: {list(clips_by_platform.keys())}")
                        
                        if 'all' in clips_by_platform:
                            clips = clips_by_platform['all']
                            print(f"- Number of clips in 'all': {len(clips)}")
                            if clips:
                                print(f"- First clip keys: {list(clips[0].keys())}")
                        else:
                            print("- 'all' key missing from clips_by_platform")
                    
                    print(f"\nAll top-level keys in results: {list(results.keys())}")
                    
                except Exception as e:
                    print(f"Error parsing results JSON: {e}")
                    print(f"Raw results (first 200 chars): {results_json[:200]}...")
            else:
                print("No results data found")
        else:
            print("No completed videoclip jobs found")
        
        conn.close()
        
    except Exception as e:
        print(f"Error checking results structure: {e}")

if __name__ == "__main__":
    check_results_structure()