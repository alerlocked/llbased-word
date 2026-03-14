@echo off
REM 工艺文件项目启动脚本
REM 避免使用 PowerShell 管道，防止进程意外退出
REM Set UTF-8 encoding for Python on Windows
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
chcp 65001 >nul 2>&1

cd /d "D:\Project Nantianmen\projects\localknowledgebase-word\backend"
start "Backend - 工艺文件" cmd /c "set PYTHONIOENCODING=utf-8 && set PYTHONUTF8=1 && python main.py"

cd /d "D:\Project Nantianmen\projects\localknowledgebase-word\frontend"
start "Frontend - 工艺文件" cmd /c "npm run dev"

echo 前后端已启动
echo 后端: http://127.0.0.1:8000
echo 前端: http://localhost:3000 (或下一个可用端口)
pause
