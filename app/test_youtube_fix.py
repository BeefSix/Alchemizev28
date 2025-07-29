#!/usr/bin/env python3
"""
Quick test script for YouTube bypass fixes
Run this inside your Docker container to test
"""

import os
import sys
sys.path.append('/app')

from app.services.utils import download_media, validate_video_request

def test_youtube_bypass():
    # Test URLs - use public, accessible videos
    test_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Roll - should always work
        "https://www.youtube.com/watch?v=0OKjUhhq8Eg",  # Your failing URL
    ]
    
    print("🧪 Testing YouTube Bypass Fixes...")
    
    for url in test_urls:
        print(f"\n📺 Testing: {url}")
        
        # Test validation first
        try:
            can_validate, result = validate_video_request(url)
            print(f"✅ Validation: {'PASS' if can_validate else 'FAIL'} - {result if not can_validate else 'OK'}")
        except Exception as e:
            print(f"❌ Validation Error: {e}")
            continue
        
        # Test audio download
        try:
            print("🎵 Testing audio download...")
            audio_result = download_media(url, is_video=False)
            if audio_result['success']:
                print(f"✅ Audio: SUCCESS - {audio_result['path']}")
                print(f"   Title: {audio_result.get('title', 'Unknown')}")
                print(f"   Duration: {audio_result.get('duration', 0)}s")
                
                # Verify file exists and has content
                if os.path.exists(audio_result['path']):
                    size = os.path.getsize(audio_result['path'])
                    print(f"   File size: {size} bytes")
                    if size > 1000:  # At least 1KB
                        print("✅ File appears valid")
                    else:
                        print("⚠️ File is very small, might be corrupted")
                else:
                    print("❌ File doesn't exist!")
            else:
                print(f"❌ Audio: FAILED - {audio_result['error']}")
        except Exception as e:
            print(f"❌ Audio download error: {e}")
        
        print("-" * 50)

if __name__ == "__main__":
    test_youtube_bypass()