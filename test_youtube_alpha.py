#!/usr/bin/env python3
"""
YouTube bypass test script adapted for your alpha architecture
"""

import os
import sys
import time
import subprocess

# Import your existing modules
try:
    import utils
    print("✅ Successfully imported utils module")
except ImportError as e:
    print(f"❌ Failed to import utils: {e}")
    sys.exit(1)

def test_dependencies():
    """Test if all dependencies are available"""
    print("🔍 Checking dependencies...")
    
    # Test yt-dlp
    try:
        import yt_dlp
        print(f"✅ yt-dlp available")
    except ImportError:
        print("❌ yt-dlp not available")
        return False
    
    # Test selenium
    try:
        import selenium
        print(f"✅ selenium available")
    except ImportError:
        print("⚠️ selenium not available (some methods will fail)")
    
    # Test undetected-chromedriver
    try:
        import undetected_chromedriver
        print(f"✅ undetected-chromedriver available")
    except ImportError:
        print("⚠️ undetected-chromedriver not available")
    
    return True

def test_youtube_functions():
    """Test YouTube-related functions in your utils"""
    print("\n🧪 Testing YouTube functions...")
    
    # Test URL validation
    test_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=0OKjUhhq8Eg",  # Your problem video
    ]
    
    for url in test_urls:
        print(f"\n📺 Testing URL: {url}")
        
        # Test is_youtube_url function
        if hasattr(utils, 'is_youtube_url'):
            is_yt = utils.is_youtube_url(url)
            print(f"   is_youtube_url: {'✅ PASS' if is_yt else '❌ FAIL'}")
        
        # Test validate_video_request if available
        if hasattr(utils, 'validate_video_request'):
            try:
                can_validate, result = utils.validate_video_request(url)
                print(f"   validate_video_request: {'✅ PASS' if can_validate else '⚠️ CONDITIONAL'}")
                if not can_validate:
                    print(f"     Reason: {result}")
            except Exception as e:
                print(f"   validate_video_request: ❌ ERROR - {e}")

def test_download_simple():
    """Test a simple download with your existing download_media function"""
    print("\n🎯 Testing simple download...")
    
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll - reliable test
    
    if hasattr(utils, 'download_media'):
        try:
            print(f"🎵 Testing audio download: {test_url}")
            start_time = time.time()
            result = utils.download_media(test_url, is_video=False)
            end_time = time.time()
            
            if result.get('success'):
                print(f"✅ Audio download: SUCCESS in {end_time - start_time:.1f}s")
                print(f"   Title: {result.get('title', 'Unknown')}")
                print(f"   Duration: {result.get('duration', 0)}s")
                print(f"   File: {result.get('file', 'N/A')}")
                
                # Clean up test file
                try:
                    if result.get('file') and os.path.exists(result['file']):
                        os.remove(result['file'])
                        print("   Cleaned up test file")
                except:
                    pass
                
                return True
            else:
                print(f"❌ Audio download: FAILED - {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"❌ Audio download: EXCEPTION - {e}")
            return False
    else:
        print("❌ download_media function not found in utils")
        return False

def test_problem_video():
    """Test your specific problem video"""
    print("\n🔧 Testing your problem video...")
    
    problem_url = "https://www.youtube.com/watch?v=0OKjUhhq8Eg"
    
    if hasattr(utils, 'download_media'):
        try:
            print(f"🎵 Testing problem video: {problem_url}")
            result = utils.download_media(problem_url, is_video=False)
            
            if result.get('success'):
                print("✅ Problem video: SUCCESS!")
                print(f"   Title: {result.get('title', 'Unknown')}")
                
                # Clean up
                try:
                    if result.get('file') and os.path.exists(result['file']):
                        os.remove(result['file'])
                except:
                    pass
                
                return True
            else:
                print(f"❌ Problem video: FAILED - {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"❌ Problem video: EXCEPTION - {e}")
            return False

def run_comprehensive_test():
    """Run all tests"""
    print("🚀 Starting YouTube Bypass Test for Alpha Architecture")
    print("=" * 60)
    
    # Test dependencies
    if not test_dependencies():
        print("❌ Dependency check failed!")
        return False
    
    # Test functions
    test_youtube_functions()
    
    # Test simple download
    simple_success = test_download_simple()
    
    # Test problem video
    problem_success = test_problem_video()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    print(f"🎯 Simple Download: {'✅ PASS' if simple_success else '❌ FAIL'}")
    print(f"🔧 Problem Video: {'✅ PASS' if problem_success else '❌ FAIL'}")
    
    if simple_success and problem_success:
        print("\n🎉 ALL TESTS PASSED! YouTube bypass is working in your alpha.")
    elif simple_success:
        print("\n⚠️ Basic functionality works, but your specific video may be restricted.")
        print("   Try a different video or check if it's age-restricted/region-blocked.")
    else:
        print("\n❌ Tests failed. Try the following:")
        print("   1. Run the quick fix script: ./youtube_quick_fix.sh")
        print("   2. Update your utils.py with the new bypass methods")
        print("   3. Restart your application")
    
    return simple_success and problem_success

if __name__ == "__main__":
    run_comprehensive_test()