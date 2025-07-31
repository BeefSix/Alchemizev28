#!/bin/bash
# diagnostic.sh - Run this to diagnose upload issues

echo "🔍 Alchemize Upload Diagnostics"
echo "==============================="

echo -e "\n📁 Checking upload directory:"
docker exec alchemize_worker ls -la /app/static/generated/uploads/

echo -e "\n🎬 Checking FFmpeg installation:"
docker exec alchemize_worker ffmpeg -version | head -n 1

echo -e "\n🐍 Testing FFmpeg with Python:"
docker exec alchemize_worker python -c "
import subprocess
result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
print(f'FFmpeg exit code: {result.returncode}')
print(f'FFmpeg output: {result.stdout[:200]}...')
"

echo -e "\n📂 Current working directory in worker:"
docker exec alchemize_worker pwd

echo -e "\n🔍 Looking for recent upload files:"
docker exec alchemize_worker find /app/static/generated/uploads -name "*.mkv" -o -name "*.mp4" -o -name "*.mov" | head -10

echo -e "\n💾 Checking disk space:"
docker exec alchemize_worker df -h /app

echo -e "\n🔑 Checking file permissions:"
docker exec alchemize_worker stat -c "%a %U:%G %n" /app/static/generated/uploads