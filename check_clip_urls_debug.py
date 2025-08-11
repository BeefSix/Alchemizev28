#!/usr/bin/env python3

import sys
import os
sys.path.append('.')

from app.models.job import Job
from app.database import get_db
import json

def main():
    db = next(get_db())
    
    # Get the most recent completed job
    job = db.query(Job).filter(Job.status == 'COMPLETED').order_by(Job.id.desc()).first()
    
    if not job:
        print("No completed jobs found")
        return
    
    print(f"Job ID: {job.id}")
    print(f"Status: {job.status}")
    
    # Parse results
    if isinstance(job.results, str):
        results = json.loads(job.results)
    else:
        results = job.results
    
    print("\nResults structure:")
    print(json.dumps(results, indent=2))
    
    # Check clips
    clips = results.get('clips_by_platform', {}).get('all', [])
    print(f"\nFound {len(clips)} clips:")
    
    for i, clip in enumerate(clips):
        print(f"  Clip {i+1}:")
        print(f"    URL: {clip.get('url', 'N/A')}")
        print(f"    Duration: {clip.get('duration', 'N/A')}s")
        print(f"    File size: {clip.get('file_size', 'N/A')} bytes")
        
        # Check if file exists
        url = clip.get('url', '')
        if url.startswith('/static/'):
            # Convert URL to file path
            file_path = url.replace('/static/', 'static/')
            if os.path.exists(file_path):
                print(f"    File exists: YES ({file_path})")
            else:
                print(f"    File exists: NO ({file_path})")
        print()

if __name__ == '__main__':
    main()