@echo off
REM Set UTF-8 encoding for Python on Windows
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
chcp 65001 >nul 2>&1
cd /d "%~dp0backend"
python main.py
