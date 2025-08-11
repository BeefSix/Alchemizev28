#!/usr/bin/env python3
import sqlite3
import json
import requests
from datetime import datetime

def debug_frontend_job():
    try:
        # First, get the most recent completed job from database
        conn = sqlite3.connect('alchemize.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, job_type, status, results, user_id FROM jobs 
            WHERE job_type = 'videoclip' AND status = 'COMPLETED' 
            ORDER BY created_at DESC LIMIT 1
        """)
        
        row = cursor.fetchone()
        if row:
            job_id, job_type, status, results_json, user_id = row
            print(f"Database Job ID: {job_id}")
            print(f"Database Status: {status}")
            print(f"Database User ID: {user_id}")
            
            if results_json:
                try:
                    results = json.loads(results_json)
                    print(f"\nDatabase Results Structure:")
                    print(f"- Has results: True")
                    print(f"- Has clips_by_platform: {'clips_by_platform' in results}")
                    if 'clips_by_platform' in results:
                        print(f"- Has clips_by_platform.all: {'all' in results['clips_by_platform']}")
                        if 'all' in results['clips_by_platform']:
                            print(f"- Number of clips: {len(results['clips_by_platform']['all'])}")
                    print(f"- Top-level keys: {list(results.keys())}")
                except Exception as e:
                    print(f"Error parsing database results: {e}")
            else:
                print("\nNo results in database")
            
            # Now test the API endpoint that the frontend uses
            print(f"\n" + "="*50)
            print("TESTING API ENDPOINT (what frontend receives)")
            print("="*50)
            
            # Test without authentication first
            try:
                response = requests.get(f'http://localhost:8001/api/v1/jobs/{job_id}')
                print(f"\nAPI Response Status: {response.status_code}")
                
                if response.status_code == 401:
                    print("API requires authentication - this is expected")
                    print("The frontend should be sending proper auth headers")
                elif response.status_code == 200:
                    api_data = response.json()
                    print(f"\nAPI Response Structure:")
                    print(f"- Has results field: {'results' in api_data}")
                    if 'results' in api_data and api_data['results']:
                        print(f"- Results is not null: True")
                        print(f"- Results type: {type(api_data['results'])}")
                        if isinstance(api_data['results'], dict):
                            print(f"- Results keys: {list(api_data['results'].keys())}")
                            if 'clips_by_platform' in api_data['results']:
                                clips_data = api_data['results']['clips_by_platform']
                                print(f"- clips_by_platform keys: {list(clips_data.keys())}")
                                if 'all' in clips_data:
                                    print(f"- clips_by_platform.all length: {len(clips_data['all'])}")
                    else:
                        print(f"- Results is null or missing")
                    
                    print(f"\nFull API Response:")
                    print(json.dumps(api_data, indent=2))
                else:
                    print(f"Unexpected status code: {response.status_code}")
                    print(f"Response: {response.text}")
                    
            except requests.exceptions.ConnectionError:
                print("Cannot connect to API server - make sure it's running on port 8001")
            except Exception as e:
                print(f"Error testing API: {e}")
        else:
            print("No completed videoclip jobs found in database")
        
        conn.close()
        
    except Exception as e:
        print(f"Error in debug: {e}")

if __name__ == "__main__":
    debug_frontend_job()