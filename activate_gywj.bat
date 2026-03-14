@echo off
echo 正在激活 gywj 环境...
call conda activate gywj

if %ERRORLEVEL% NEQ 0 (
    echo 环境激活失败！
    echo 请确保已创建 gywj 环境：conda create -n gywj python=3.10 -y
    pause
    exit /b 1
)

echo 环境激活成功！
echo 当前Python版本：
python --version
echo.
echo 当前工作目录：%cd%
echo.
echo 可用命令：
echo - python -m pytest tests/     : 运行测试
echo - python backend/main.py      : 启动后端服务
echo - cd frontend && npm run dev  : 启动前端开发服务器
echo.
echo 项目功能验证：
echo.
echo 1. 验证PDF提取功能...
python -c "from app.agents.tools.pdf_table_extractor import PDFTableExtractor; print('PDF提取模块: OK')" 2>nul && echo    ✅ PDF提取模块正常 || echo    ❌ PDF提取模块异常
echo.
echo 2. 验证文件系统服务...
python -c "from app.services.file_system_service import file_system_service; print('文件系统服务: OK')" 2>nul && echo    ✅ 文件系统服务正常 || echo    ❌ 文件系统服务异常
echo.
echo 3. 验证工艺文档服务...
python -c "from app.services.process_document_service import process_document_service; print('工艺文档服务: OK')" 2>nul && echo    ✅ 工艺文档服务正常 || echo    ❌ 工艺文档服务异常
echo.
echo 环境已就绪，可以开始开发工作！
echo.
cmd /k