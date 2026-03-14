@echo off
chcp 65001 >nul
echo ========================================
echo   停止智能工艺文件辅助编辑系统
echo ========================================
echo.

echo 正在关闭所有服务...
echo.

echo [1/4] 关闭前端服务...
taskkill /FI "WINDOWTITLE eq 前端服务 - React*" /T /F >nul 2>&1
if errorlevel 1 (
    echo ⚠️  未找到前端服务进程
) else (
    echo ✅ 前端服务已关闭
)

echo [2/4] 关闭Celery Worker...
taskkill /FI "WINDOWTITLE eq Celery Worker*" /T /F >nul 2>&1
if errorlevel 1 (
    echo ⚠️  未找到Celery Worker进程
) else (
    echo ✅ Celery Worker已关闭
)

echo [3/4] 关闭后端服务...
taskkill /FI "WINDOWTITLE eq 后端服务*" /T /F >nul 2>&1
if errorlevel 1 (
    echo ⚠️  未找到后端服务进程
) else (
    echo ✅ 后端服务已关闭
)

echo [4/4] 检查残留进程...
REM 关闭可能的残留Python进程（谨慎使用）
REM taskkill /IM python.exe /F >nul 2>&1
REM 关闭可能的残留Node进程（谨慎使用）
REM taskkill /IM node.exe /F >nul 2>&1
echo ✅ 检查完成

echo.
echo ========================================
echo   ✅ 所有服务已关闭
echo ========================================
echo.
echo 💡 提示:
echo    - Redis服务未关闭（作为系统服务运行）
echo    - 如需关闭Redis: net stop Redis
echo    - 重新启动请运行 start.bat
echo.
pause

