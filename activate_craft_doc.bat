@echo off
REM Set UTF-8 encoding for Windows and Python
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
chcp 65001 >nul
echo ========================================
echo   激活智能工艺文件辅助编辑系统开发环境
echo ========================================
echo.

echo 正在激活 craft-doc 环境...
call conda activate craft-doc

if %ERRORLEVEL% NEQ 0 (
    echo ❌ 环境激活失败！
    echo.
    echo 请确保已创建 craft-doc 环境：
    echo   conda create -n craft-doc python=3.10 -y
    echo   conda activate craft-doc
    echo   cd backend
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo ✅ 环境激活成功！
echo.

echo 当前Python版本：
python --version
echo.

echo 当前工作目录：%cd%
echo.

echo 📋 项目信息：
echo   项目名称: 智能工艺文件辅助编辑系统
echo   项目类型: 面向工艺师的专业AI辅助编辑工具
echo   Archon项目ID: f9ecaf8b-ff17-467d-bf29-37aae558bb4e
echo.

echo 🚀 可用命令：
echo   - python -m pytest tests/     : 运行测试
echo   - python backend/main.py      : 启动后端服务
echo   - cd frontend && npm run dev  : 启动前端开发服务器
echo   - start.bat                   : 启动完整应用
echo   - start_archon.bat            : 启动Archon开发平台
echo.

echo 🔧 项目功能验证：
echo.

echo 1. 验证PDF提取功能...
python -c "from app.agents.tools.pdf_table_extractor import PDFTableExtractor; print('PDF提取模块: OK')" 2>nul && echo    ✅ PDF提取模块正常 || echo    ❌ PDF提取模块异常
echo.

echo 2. 验证AI Agent系统...
python -c "from app.agents.orchestrator import OrchestratorAgent; print('主控Agent: OK')" 2>nul && echo    ✅ 主控Agent正常 || echo    ❌ 主控Agent异常
echo.

echo 3. 验证工艺文档服务...
python -c "from app.services.process_document_service import process_document_service; print('工艺文档服务: OK')" 2>nul && echo    ✅ 工艺文档服务正常 || echo    ❌ 工艺文档服务异常
echo.

echo 4. 验证向量数据库...
python -c "from app.services.vector_store_service import vector_store_service; print('向量数据库: OK')" 2>nul && echo    ✅ 向量数据库正常 || echo    ❌ 向量数据库异常
echo.

echo ========================================
echo   ✅ 开发环境已就绪，可以开始开发工作！
echo ========================================
echo.

echo 💡 开发提示：
echo   - 使用Archon进行任务管理: http://localhost:3737
echo   - 查看API文档: http://localhost:8000/docs
echo   - 前端开发服务器: http://localhost:3000
echo   - 使用结构化日志: from app.shared.logging import get_logger
echo.

cmd /k