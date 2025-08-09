@echo off
echo.
echo ========================================
echo 🚀 ALCHEMIZE PRODUCTION DEPLOYMENT 🚀
echo ========================================
echo.

echo 🔍 Checking current status...
python test_simple.py

echo.
echo 📋 Production deployment options:
echo 1. Quick Production Setup (Recommended)
echo 2. Full Production Deployment with Docker
echo 3. Exit
echo.

set /p choice="Choose an option (1-3): "

if "%choice%"=="1" (
    echo.
    echo 🚀 Running Quick Production Setup...
    python production_setup.py
    echo.
    echo ✅ Quick setup complete! Check the created files.
    echo 📖 Read PRODUCTION_DEPLOYMENT.md for next steps.
    pause
) else if "%choice%"=="2" (
    echo.
    echo 🐳 Starting Full Production Deployment...
    echo ⚠️  This requires Docker and Docker Compose to be installed.
    echo.
    python deploy_to_production.py
    pause
) else if "%choice%"=="3" (
    echo.
    echo 👋 Exiting...
    exit /b 0
) else (
    echo.
    echo ❌ Invalid option. Please choose 1, 2, or 3.
    pause
    goto :eof
)

echo.
echo 🎉 Deployment process completed!
echo.
echo 📖 For detailed instructions, see:
echo    - PRODUCTION_DEPLOYMENT.md
echo    - README_ENHANCED.md
echo.
pause
