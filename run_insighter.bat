@echo off
if not exist venv (
  echo Please run install_insighter.bat first.
  exit /b 1
)
call venv\Scripts\activate
insighter %*
