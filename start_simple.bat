@echo off
echo Starting Alchemize...
echo.
echo 1. Make sure you have Python 3.8+ installed
echo 2. Install dependencies: pip install -r requirements.txt
echo 3. Set your OPENAI_API_KEY in .env file
echo 4. Run: python -m uvicorn app.main:app --reload --port 8001
echo.
pause
