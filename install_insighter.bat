@echo off

REM Check for Docker
docker --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
  echo Docker is required but was not found. Please install Docker Desktop and ensure it is running.
  goto end
)

REM Check for Node.js
node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
  echo Node.js is required but was not found. Please install Node.js and re-run this script.
  goto end
)

REM Install Yarn if missing
yarn --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
  echo Yarn not found. Installing...
  npm install -g yarn
)

REM Setup Python virtual environment
python -m venv venv
call venv\Scripts\activate
pip install --upgrade pip
pip install -e pypi

REM Install Node.js dependencies
if exist yarn.lock (
  yarn install
) else (
  echo Yarn lockfile not found. Please install Node dependencies manually.
)

:end
