@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo 工艺文件辅助编辑系统 - Windows 7 兼容性安装脚本
echo ========================================================
echo.

REM 检查系统版本
ver | findstr /i "6.1." >nul
if %errorlevel% neq 0 (
    echo 警告: 检测到非Windows 7系统，但将继续执行兼容性设置...
)

REM 设置环境变量
set PYTHON_VERSION=3.8.10
set CONDA_ENV_NAME=craft-document-assistant-win7
set PROJECT_DIR=%~dp0..

echo 项目目录: %PROJECT_DIR%
echo Python版本: %PYTHON_VERSION%
echo Conda环境: %CONDA_ENV_NAME%
echo.

REM 检查Conda是否已安装
conda --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到Conda。请先安装Anaconda或Miniconda。
    echo 下载地址: https://repo.anaconda.com/miniconda/Miniconda3-py38_4.10.3-Windows-x86_64.exe
    pause
    exit /b 1
)

REM 检查Python 3.8是否已安装
python --version 2>&1 | findstr /i "3.8" >nul
if %errorlevel% neq 0 (
    echo 安装Python 3.8.10...
    conda install -y python=%PYTHON_VERSION%
    if %errorlevel% neq 0 (
        echo 错误: Python 3.8.10安装失败
        pause
        exit /b 1
    )
)

REM 创建Conda环境
echo 创建Conda环境: %CONDA_ENV_NAME%
conda env create -f "%PROJECT_DIR%\environment_win7.yml" --name %CONDA_ENV_NAME%
if %errorlevel% neq 0 (
    echo 警告: Conda环境创建失败，尝试更新现有环境...
    conda env update -f "%PROJECT_DIR%\environment_win7.yml" --name %CONDA_ENV_NAME%
    if %errorlevel% neq 0 (
        echo 错误: Conda环境更新失败
        pause
        exit /b 1
    )
)

REM 激活环境
echo 激活Conda环境...
call conda activate %CONDA_ENV_NAME%

REM 安装Node.js依赖（降级版本）
echo 安装Node.js依赖...
cd "%PROJECT_DIR%\frontend"
if exist package-win7.json (
    copy /Y package-win7.json package.json
)
npm install --legacy-peer-deps
if %errorlevel% neq 0 (
    echo 警告: npm install失败，尝试使用cnpm...
    npm install -g cnpm --registry=https://registry.npmmirror.com
    cnpm install --legacy-peer-deps
)

REM 配置Windows 7特定设置
echo 配置Windows 7特定设置...
cd "%PROJECT_DIR%\backend"

REM 创建Windows 7兼容性配置文件
echo {
    "system": "windows7",
    "compatibility_mode": true,
    "disable_http2": true,
    "disable_websocket_compression": true,
    "use_legacy_ssl": true,
    "max_memory_mb": 2048,
    "use_short_paths": true
} > app\compatibility\win7_config.json

REM 复制兼容性模块
if not exist app\compatibility mkdir app\compatibility
copy /Y "%PROJECT_DIR%\scripts\win7_compat.py" "%PROJECT_DIR%\backend\app\compatibility\win7_compat.py"

REM 安装后端依赖
echo 安装后端依赖...
pip install -r requirements-win7.txt
if %errorlevel% neq 0 (
    echo 警告: pip install失败，继续执行...
)

REM 创建启动脚本
echo @echo off > "%PROJECT_DIR%\start_win7.bat"
echo call conda activate %CONDA_ENV_NAME% >> "%PROJECT_DIR%\start_win7.bat"
echo cd "%PROJECT_DIR%\backend" >> "%PROJECT_DIR%\start_win7.bat"
echo python main.py --compatibility-mode win7 >> "%PROJECT_DIR%\start_win7.bat"
echo pause >> "%PROJECT_DIR%\start_win7.bat"

echo.
echo ========================================================
echo Windows 7 兼容性安装完成！
echo ========================================================
echo.
echo 启动应用: 双击 start_win7.bat
echo.
echo 注意事项:
echo 1. 确保已安装Visual C++ Redistributable for Visual Studio 2015-2019
echo 2. 如果遇到SSL证书问题，请运行: pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org
echo 3. 内存限制为2GB，请确保系统有足够内存
echo.
pause