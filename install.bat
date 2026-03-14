@echo off
REM Set UTF-8 encoding for Windows
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
chcp 65001 >nul
echo ========================================
echo   智能工艺文件辅助编辑系统 - 安装脚本
echo ========================================
echo.

echo [1/3] 安装后端依赖...
echo 激活conda环境: craft-doc
call conda activate craft-doc
if errorlevel 1 (
    echo ❌ 无法激活conda环境craft-doc，请确保已创建该环境
    pause
    exit /b 1
)
cd backend
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ 后端依赖安装失败
    pause
    exit /b 1
)
echo ✅ 后端依赖安装完成
cd ..

echo.
echo [2/3] 安装前端依赖...
cd frontend
call npm install
if errorlevel 1 (
    echo ❌ 前端依赖安装失败
    pause
    exit /b 1
)
echo ✅ 前端依赖安装完成
cd ..

echo.
echo [3/3] 初始化数据库...
echo 使用conda环境: craft-doc
call conda activate craft-doc
cd backend
python init_db.py
if errorlevel 1 (
    echo ❌ 数据库初始化失败
    pause
    exit /b 1
)
echo ✅ 数据库初始化完成
cd ..

echo.
echo ========================================
echo   安装完成！
echo ========================================
echo.
echo 下一步: 配置API密钥
echo 1. 复制 backend\.env.example 为 backend\.env
echo 2. 填入您的阿里云通义千问API密钥
echo 3. 运行 start.bat 启动应用
echo.
pause




