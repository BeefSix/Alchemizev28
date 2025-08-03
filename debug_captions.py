# debug_captions.py - Run this to test caption functionality
import subprocess
import os
import json
from openai import OpenAI

def test_caption_pipeline():
    """Test the entire caption pipeline step by step"""
    print("🔍 ALCHEMIZE CAPTION DEBUGGING")
    print("=" * 50)
    
    # Test 1: Check Docker containers
    print("\n1. 📦 Checking Docker containers...")
    try:
        result = subprocess.run(['docker', 'ps', '--format', 'table {{.Names}}\t{{.Status}}'], 
                              capture_output=True, text=True)
        print(result.stdout)
    except Exception as e:
        print(f"❌ Docker check failed: {e}")
        return
    
    # Test 2: Check FFmpeg in worker container
    print("\n2. 🎬 Testing FFmpeg in worker container...")
    try:
        result = subprocess.run([
            'docker', 'exec', 'alchemize_worker', 
            'ffmpeg', '-version'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ FFmpeg is working")
            print(result.stdout.split('\n')[0])  # First line has version
        else:
            print(f"❌ FFmpeg failed: {result.stderr}")
    except Exception as e:
        print(f"❌ FFmpeg test failed: {e}")
    
    # Test 3: Check OpenAI API key
    print("\n3. 🤖 Testing OpenAI API connection...")
    try:
        # Read environment file
        env_file = ".env"
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                env_content = f.read()
                if "OPENAI_API_KEY=" in env_content:
                    api_key_line = [line for line in env_content.split('\n') if line.startswith('OPENAI_API_KEY=')]
                    if api_key_line:
                        api_key = api_key_line[0].split('=', 1)[1].strip()
                        if api_key and len(api_key) > 10:
                            print(f"✅ API key found (length: {len(api_key)})")
                            
                            # Test actual OpenAI connection
                            try:
                                client = OpenAI(api_key=api_key)
                                # Make a minimal test call
                                response = client.models.list()
                                print("✅ OpenAI API connection successful")
                            except Exception as e:
                                print(f"❌ OpenAI API test failed: {e}")
                        else:
                            print("❌ API key is empty or too short")
                    else:
                        print("❌ OPENAI_API_KEY not found in .env")
                else:
                    print("❌ OPENAI_API_KEY not in .env file")
        else:
            print("❌ .env file not found")
    except Exception as e:
        print(f"❌ Environment check failed: {e}")
    
    # Test 4: Create test video and try audio extraction
    print("\n4. 🎥 Testing video processing pipeline...")
    try:
        # Create a test video inside the worker container
        create_test_cmd = [
            'docker', 'exec', 'alchemize_worker', 'ffmpeg', '-y',
            '-f', 'lavfi', '-i', 'testsrc=duration=10:size=640x480:rate=1',
            '-f', 'lavfi', '-i', 'sine=frequency=440:duration=10',
            '-c:v', 'libx264', '-c:a', 'aac', '-t', '10',
            '/app/data/static/generated/test_video.mp4'
        ]
        
        print("🔧 Creating test video...")
        result = subprocess.run(create_test_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Test video created")
            
            # Test audio extraction
            extract_audio_cmd = [
                'docker', 'exec', 'alchemize_worker', 'ffmpeg', '-y',
                '-i', '/app/data/static/generated/test_video.mp4',
                '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
                '/app/data/static/generated/test_audio.wav'
            ]
            
            print("🔧 Testing audio extraction...")
            result = subprocess.run(extract_audio_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Audio extraction successful")
                
                # Check if audio file exists and has content
                check_audio_cmd = [
                    'docker', 'exec', 'alchemize_worker', 'ls', '-la', 
                    '/app/data/static/generated/test_audio.wav'
                ]
                result = subprocess.run(check_audio_cmd, capture_output=True, text=True)
                print(f"📁 Audio file: {result.stdout.strip()}")
                
            else:
                print(f"❌ Audio extraction failed: {result.stderr}")
        else:
            print(f"❌ Test video creation failed: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Video pipeline test failed: {e}")
    
    # Test 5: Check file permissions and directories
    print("\n5. 📁 Checking file system...")
    try:
        check_dirs_cmd = [
            'docker', 'exec', 'alchemize_worker', 'ls', '-la', 
            '/app/data/static/generated/'
        ]
        result = subprocess.run(check_dirs_cmd, capture_output=True, text=True)
        print("📂 Static directory contents:")
        print(result.stdout)
        
        # Check uploads directory
        check_uploads_cmd = [
            'docker', 'exec', 'alchemize_worker', 'ls', '-la', 
            '/app/data/static/generated/uploads/'
        ]
        result = subprocess.run(check_uploads_cmd, capture_output=True, text=True)
        print("📂 Uploads directory:")
        print(result.stdout)
        
    except Exception as e:
        print(f"❌ Directory check failed: {e}")
    
    # Test 6: Check worker logs for recent errors
    print("\n6. 📝 Checking recent worker logs...")
    try:
        logs_cmd = ['docker', 'logs', '--tail', '20', 'alchemize_worker']
        result = subprocess.run(logs_cmd, capture_output=True, text=True)
        print("📋 Recent worker logs:")
        print(result.stdout[-1000:])  # Last 1000 chars
        if result.stderr:
            print("⚠️ Error logs:")
            print(result.stderr[-500:])  # Last 500 chars
    except Exception as e:
        print(f"❌ Log check failed: {e}")
    
    # Test 7: Database connection test
    print("\n7. 🗄️ Testing database connection...")
    try:
        db_test_cmd = [
            'docker', 'exec', 'alchemize_worker', 'python', '-c',
            '''
import os
from sqlalchemy import create_engine, text
try:
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
    else:
        print("❌ DATABASE_URL not found")
except Exception as e:
    print(f"❌ Database connection failed: {e}")
'''
        ]
        result = subprocess.run(db_test_cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(f"Database error: {result.stderr}")
    except Exception as e:
        print(f"❌ Database test failed: {e}")
    
    print("\n" + "=" * 50)
    print("🔍 DIAGNOSIS COMPLETE!")
    print("\nNext steps:")
    print("1. Check any ❌ failures above")
    print("2. If OpenAI API fails, verify your API key and credits")
    print("3. If FFmpeg fails, rebuild worker container")
    print("4. If audio extraction fails, check video format support")
    print("5. Run docker-compose logs worker to see detailed errors")

if __name__ == "__main__":
    test_caption_pipeline()