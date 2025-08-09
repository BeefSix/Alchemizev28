import subprocess
import sys

def run_docker_command(command):
    """Run a command inside the worker container"""
    full_command = f'docker exec alchemize_worker {command}'
    try:
        result = subprocess.run(full_command, shell=True, capture_output=True, text=True)
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), -1

def main():
    print("🔍 Alchemize Upload Diagnostics (Windows)")
    print("=" * 50)
    
    # Test 1: Check upload directory
    print("\n📁 Checking upload directory:")
    stdout, stderr, code = run_docker_command('ls -la /app/static/generated/uploads/')
    if code == 0:
        print(stdout)
    else:
        print(f"Error: {stderr}")
    
    # Test 2: Check FFmpeg
    print("\n🎬 Checking FFmpeg installation:")
    stdout, stderr, code = run_docker_command('ffmpeg -version')
    if code == 0:
        # Just print first few lines
        lines = stdout.split('\n')
        for line in lines[:3]:
            print(line)
    else:
        print(f"FFmpeg not found! Error: {stderr}")
    
    # Test 3: Check Python and imports
    print("\n🐍 Testing Python environment:")
    python_test = '''python -c "
import os
import subprocess
from pydub import AudioSegment
print(f'Working directory: {os.getcwd()}')
print(f'Static dir exists: {os.path.exists(\'/app/static/generated/uploads\')}')
# Test FFmpeg from Python
result = subprocess.run([\'ffmpeg\', \'-version\'], capture_output=True)
print(f'FFmpeg from Python: {result.returncode == 0}')
"'''
    stdout, stderr, code = run_docker_command(python_test)
    print(stdout)
    if stderr:
        print(f"Errors: {stderr}")
    
    # Test 4: Find recent uploads
    print("\n📂 Looking for uploaded files:")
    stdout, stderr, code = run_docker_command('find /app/static/generated/uploads -type f -name "*.*" | head -10')
    if stdout.strip():
        print("Found files:")
        print(stdout)
    else:
        print("No files found in uploads directory")
    
    # Test 5: Check permissions
    print("\n🔑 Checking permissions:")
    stdout, stderr, code = run_docker_command('stat -c "%a %U:%G %n" /app/static/generated/uploads')
    print(stdout)
    
    # Test 6: Test creating a file
    print("\n✍️ Testing file creation:")
    test_file_cmd = 'touch /app/static/generated/uploads/test_write.tmp && echo "Write test: SUCCESS" && rm /app/static/generated/uploads/test_write.tmp'
    stdout, stderr, code = run_docker_command(test_file_cmd)
    if code == 0:
        print(stdout)
    else:
        print(f"Write test: FAILED - {stderr}")
    
    print("\n" + "=" * 50)
    print("Diagnostic complete!")
    
    # Quick check if worker is running
    check_worker = subprocess.run('docker ps --filter "name=alchemize_worker" --format "table {{.Names}}\t{{.Status}}"', 
                                  shell=True, capture_output=True, text=True)
    print("\n🐳 Container status:")
    print(check_worker.stdout)

if __name__ == "__main__":
    main()