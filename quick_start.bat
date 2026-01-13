@echo off
REM Quick start script for Teams-Notion middleware local development (Windows)
REM This script helps set up and run the middleware with ngrok

echo ==========================================
echo Teams-Notion Middleware Quick Start
echo ==========================================
echo.

REM Check if .env file exists
if not exist .env (
    echo [X] .env file not found!
    echo [i] Please create .env file from ".env example":
    echo     copy ".env example" .env
    echo [i] Then edit .env with your credentials
    exit /b 1
)

echo [OK] Found .env file

REM Check if venv exists
if not exist venv (
    echo [!] Virtual environment not found. Creating one...
    python -m venv venv
    echo [OK] Virtual environment created
)

REM Activate virtual environment
echo [i] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if dependencies are installed
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo [!] Dependencies not installed. Installing...
    pip install -r requirements.txt
    echo [OK] Dependencies installed
) else (
    echo [OK] Dependencies already installed
)

REM Check if ngrok is installed
where ngrok >nul 2>nul
if errorlevel 1 (
    echo [X] ngrok not found!
    echo [i] Please install ngrok from https://ngrok.com/download
    exit /b 1
)

echo [OK] ngrok found
echo.

echo ==========================================
set /p START_NGROK="Do you want to start ngrok now? (y/n): "

if /i "%START_NGROK%"=="y" (
    echo [i] Starting ngrok on port 8000...
    echo [!] Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
    echo [i] Then update WEBHOOK_NOTIFICATION_URL in .env and restart the server
    echo.
    
    REM Start ngrok
    ngrok http 8000
) else (
    echo [i] Skipping ngrok. Please start it manually if needed:
    echo     ngrok http 8000
)

echo.
echo ==========================================
echo [i] To start the server:
echo     venv\Scripts\activate
echo     uvicorn main:app --reload --host 0.0.0.0 --port 8000
echo.
echo [i] To test the endpoints:
echo     python test_local.py
echo.
echo [i] To create a subscription:
echo     curl -X POST "http://localhost:8000/subscription/create" ^
echo       -H "Content-Type: application/json" ^
echo       -d "{\"resource\": \"teams/{teamId}/channels/{channelId}/messages\", \"change_types\": [\"created\"], \"expiration_days\": 1}"
echo ==========================================
