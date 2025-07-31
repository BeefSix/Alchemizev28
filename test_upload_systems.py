#!/usr/bin/env python3
"""
Test script to verify the upload system is working
Run this after rebuilding your containers
"""

import os
import sys
import subprocess

def test_ffmpeg():
    """Test if FFmpeg is working properly"""
    print("🎬 Testing FFmpeg installation...")
    
    try:
        # Test ffmpeg
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ FFmpeg is installed")
            # Get version info
            version_line = result.stdout.split('\n')[0]
            print(f"   Version: {version_line}")
        else:
            print("❌ FFmpeg test failed")
            return False
            
        # Test ffprobe
        result = subprocess.run(['ffprobe', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ FFprobe is installed")
        else:
            print("❌ FFprobe test failed")
            return False
            
        # Test audio extraction on a test file
        print("\n🎵 Testing audio extraction...")
        
        # Create a simple test video using FFmpeg
        test_video = "/tmp/test_video.mp4"
        test_audio = "/tmp/test_audio.mp3"
        
        # Generate 5 seconds of test video with audio
        cmd = [
            'ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=5:size=320x240:rate=30',
            '-f', 'lavfi', '-i', 'sine=frequency=1000:duration=5',
            '-pix_fmt', 'yuv420p', '-c:v', 'libx264', '-c:a', 'aac',
            '-y', test_video
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Failed to create test video: {result.stderr}")
            return False
        
        # Extract audio
        cmd = ['ffmpeg', '-i', test_video, '-q:a', '0', '-map', 'a', '-y', test_audio]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(test_audio):
            size = os.path.getsize(test_audio)
            print(f"✅ Audio extraction works! Created {size} byte MP3 file")
            
            # Cleanup
            os.remove(test_video)
            os.remove(test_audio)
            return True
        else:
            print(f"❌ Audio extraction failed: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("❌ FFmpeg not found in PATH")
        return False
    except Exception as e:
        print(f"❌ FFmpeg test error: {e}")
        return False

def test_directories():
    """Test if all required directories exist with correct permissions"""
    print("\n📁 Testing directory structure...")
    
    dirs_to_check = [
        "/app/static/generated",
        "/app/static/generated/uploads",
        "/app/static/generated/temp_downloads",
        "/app/.cache/huggingface",
    ]
    
    all_good = True
    for dir_path in dirs_to_check:
        if os.path.exists(dir_path):
            # Check if writable
            test_file = os.path.join(dir_path, "test_write.tmp")
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                print(f"✅ {dir_path} - exists and writable")
            except:
                print(f"❌ {dir_path} - exists but not writable")
                all_good = False
        else:
            print(f"❌ {dir_path} - does not exist")
            all_good = False
    
    return all_good

def test_imports():
    """Test if all required Python modules can be imported"""
    print("\n🐍 Testing Python imports...")
    
    modules_to_test = [
        ("pydub", "AudioSegment"),
        ("openai", "OpenAI"),
        ("yt_dlp", None),
        ("app.services.utils", "transcribe_local_audio_file"),
    ]
    
    all_good = True
    for module_name, attr_name in modules_to_test:
        try:
            if '.' in module_name:
                # Add app to path for local imports
                sys.path.insert(0, '/app')
            
            module = __import__(module_name, fromlist=[''])
            
            if attr_name:
                if hasattr(module, attr_name):
                    print(f"✅ {module_name}.{attr_name} - available")
                else:
                    print(f"❌ {module_name}.{attr_name} - attribute not found")
                    all_good = False
            else:
                print(f"✅ {module_name} - imported successfully")
                
        except ImportError as e:
            print(f"❌ {module_name} - import failed: {e}")
            all_good = False
    
    return all_good

def main():
    print("🚀 Alchemize Upload System Test")
    print("=" * 50)
    
    results = {
        "FFmpeg": test_ffmpeg(),
        "Directories": test_directories(),
        "Python Imports": test_imports(),
    }
    
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    if all(results.values()):
        print("\n🎉 All tests passed! Your upload system should work now.")
        print("\nNext steps:")
        print("1. Upload a video file through the web interface")
        print("2. Check the worker logs for processing status")
        print("3. Verify clips are generated correctly")
    else:
        print("\n❌ Some tests failed. Please fix the issues above.")
        print("\nTroubleshooting:")
        print("1. Rebuild your Docker containers: docker-compose build --no-cache")
        print("2. Check container logs: docker-compose logs worker")
        print("3. Ensure all environment variables are set in .env")

if __name__ == "__main__":
    main()