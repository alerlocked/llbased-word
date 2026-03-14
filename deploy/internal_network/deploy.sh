#!/bin/bash

# 工艺文件辅助编辑系统 - 内网部署脚本
# 支持完全离线环境部署

set -e

echo "========================================================"
echo "工艺文件辅助编辑系统 - 内网部署脚本"
echo "========================================================"
echo ""

# 配置变量
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$DEPLOY_DIR/../../"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
MODELS_DIR="$PROJECT_ROOT/models"
DATA_DIR="$PROJECT_ROOT/data"

# 部署配置
DEPLOY_MODE="offline"  # offline 或 online
PYTHON_VERSION="3.10.12"
NODE_VERSION="16.18.0"
USE_GPU=false
MAX_MEMORY_MB=4096

echo "部署目录: $DEPLOY_DIR"
echo "项目根目录: $PROJECT_ROOT"
echo "部署模式: $DEPLOY_MODE"
echo "Python版本: $PYTHON_VERSION"
echo "Node.js版本: $NODE_VERSION"
echo "GPU支持: $USE_GPU"
echo "内存限制: ${MAX_MEMORY_MB}MB"
echo ""

# 检查必要条件
check_prerequisites() {
    echo "检查部署前提条件..."

    # 检查磁盘空间 (至少需要10GB)
    AVAILABLE_SPACE=$(df -BG "$PROJECT_ROOT" | tail -1 | awk '{print $4}' | sed 's/G//')
    if [ "$AVAILABLE_SPACE" -lt 10 ]; then
        echo "错误: 可用磁盘空间不足 (需要至少10GB，当前可用: ${AVAILABLE_SPACE}GB)"
        exit 1
    fi

    # 检查内存 (至少需要4GB)
    AVAILABLE_MEMORY=$(free -m | awk 'NR==2{printf "%.0f", $2/1024}')
    if [ "$AVAILABLE_MEMORY" -lt 4 ]; then
        echo "警告: 可用内存较少 (当前可用: ${AVAILABLE_MEMORY}GB)，可能影响性能"
    fi

    # 检查端口占用
    check_port 8000 "后端API"
    check_port 3000 "前端应用"
    check_port 6379 "Redis (可选)"

    echo "✓ 前提条件检查通过"
    echo ""
}

check_port() {
    local port=$1
    local service=$2
    if lsof -i :$port > /dev/null 2>&1; then
        echo "警告: 端口 $port ($service) 已被占用"
    fi
}

# 准备离线包
prepare_offline_package() {
    if [ "$DEPLOY_MODE" = "offline" ]; then
        echo "准备离线部署包..."

        # 检查离线依赖包是否存在
        if [ ! -d "$PROJECT_ROOT/offline_deps" ]; then
            echo "错误: 离线依赖包目录不存在: $PROJECT_ROOT/offline_deps"
            echo "请先运行 'scripts/create_offline_package.sh' 创建离线包"
            exit 1
        fi

        # 检查模型文件是否存在
        if [ ! -d "$MODELS_DIR" ] || [ -z "$(ls -A $MODELS_DIR)" ]; then
            echo "警告: 模型目录为空或不存在: $MODELS_DIR"
            echo "请手动下载模型文件到该目录"
        fi

        echo "✓ 离线部署包准备完成"
        echo ""
    fi
}

# 安装Python环境
install_python_environment() {
    echo "安装Python环境..."

    # 检查Python版本
    if command -v python3 &> /dev/null; then
        CURRENT_PYTHON=$(python3 --version 2>&1 | cut -d' ' -f2)
        if [[ "$CURRENT_PYTHON" == "$PYTHON_VERSION"* ]]; then
            echo "✓ Python $CURRENT_PYTHON 已安装"
        else
            echo "警告: 检测到Python $CURRENT_PYTHON，建议使用 $PYTHON_VERSION"
        fi
    else
        echo "错误: 未找到Python 3，请先安装Python $PYTHON_VERSION"
        exit 1
    fi

    # 安装pip
    if ! command -v pip &> /dev/null; then
        echo "安装pip..."
        curl -s https://bootstrap.pypa.io/get-pip.py | python3
    fi

    # 安装虚拟环境
    if [ ! -d "$BACKEND_DIR/venv" ]; then
        echo "创建Python虚拟环境..."
        python3 -m venv "$BACKEND_DIR/venv"
    fi

    # 激活虚拟环境
    source "$BACKEND_DIR/venv/bin/activate"

    # 安装依赖
    if [ "$DEPLOY_MODE" = "offline" ]; then
        echo "从离线包安装Python依赖..."
        pip install --no-index --find-links "$PROJECT_ROOT/offline_deps/python" -r "$BACKEND_DIR/requirements.txt"
    else
        echo "从网络安装Python依赖..."
        pip install -r "$BACKEND_DIR/requirements.txt"
    fi

    echo "✓ Python环境安装完成"
    echo ""
}

# 安装Node.js环境
install_nodejs_environment() {
    echo "安装Node.js环境..."

    # 检查Node.js版本
    if command -v node &> /dev/null; then
        CURRENT_NODE=$(node --version 2>&1 | cut -d'v' -f2)
        if [[ "$CURRENT_NODE" == "$NODE_VERSION"* ]]; then
            echo "✓ Node.js $CURRENT_NODE 已安装"
        else
            echo "警告: 检测到Node.js $CURRENT_NODE，建议使用 $NODE_VERSION"
        fi
    else
        echo "错误: 未找到Node.js，请先安装Node.js $NODE_VERSION"
        exit 1
    fi

    # 安装前端依赖
    cd "$FRONTEND_DIR"
    if [ "$DEPLOY_MODE" = "offline" ]; then
        echo "从离线包安装Node.js依赖..."
        npm ci --offline --prefer-offline
    else
        echo "从网络安装Node.js依赖..."
        npm install
    fi

    # 构建前端
    echo "构建前端应用..."
    npm run build

    echo "✓ Node.js环境安装完成"
    echo ""
}

# 配置应用
configure_application() {
    echo "配置应用程序..."

    # 创建数据目录
    mkdir -p "$DATA_DIR/vector_store"
    mkdir -p "$DATA_DIR/generated_documents"
    mkdir -p "$DATA_DIR/process_docs"

    # 复制配置文件模板
    if [ ! -f "$BACKEND_DIR/.env" ]; then
        cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
        echo "请编辑 $BACKEND_DIR/.env 文件配置API密钥"
    fi

    # 创建内网部署配置
    cat > "$BACKEND_DIR/config/internal_network.json" << EOF
{
    "deployment_mode": "internal_network",
    "offline_mode": true,
    "use_gpu": $USE_GPU,
    "max_memory_mb": $MAX_MEMORY_MB,
    "allowed_origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
    "database_url": "sqlite:///./data/app.db",
    "redis_url": "redis://localhost:6379/0",
    "model_paths": {
        "deepseek_r1": "./models/deepseek-r1",
        "bge_embedding": "./models/bge-large-zh-v1.5",
        "bge_rerank": "./models/bge-reranker-large"
    }
}
EOF

    echo "✓ 应用程序配置完成"
    echo ""
}

# 创建启动脚本
create_startup_scripts() {
    echo "创建启动脚本..."

    # 后端启动脚本
    cat > "$PROJECT_ROOT/start_backend.sh" << EOF
#!/bin/bash
cd "$(dirname "\$0")/backend"
source venv/bin/activate
python main.py --config config/internal_network.json
EOF
    chmod +x "$PROJECT_ROOT/start_backend.sh"

    # 前端启动脚本
    cat > "$PROJECT_ROOT/start_frontend.sh" << EOF
#!/bin/bash
cd "$(dirname "\$0")/frontend"
npm start
EOF
    chmod +x "$PROJECT_ROOT/start_frontend.sh"

    # 完整启动脚本
    cat > "$PROJECT_ROOT/start_all.sh" << EOF
#!/bin/bash
echo "启动工艺文件辅助编辑系统..."
echo ""

# 启动后端
echo "启动后端服务..."
./start_backend.sh &
BACKEND_PID=\$!

# 等待后端启动
sleep 5

# 启动前端
echo "启动前端服务..."
./start_frontend.sh &
FRONTEND_PID=\$!

echo ""
echo "服务已启动!"
echo "后端: http://localhost:8000"
echo "前端: http://localhost:3000"
echo ""
echo "按 Ctrl+C 停止服务"

# 清理函数
cleanup() {
    echo "停止服务..."
    kill \$BACKEND_PID \$FRONTEND_PID 2>/dev/null
    wait \$BACKEND_PID \$FRONTEND_PID 2>/dev/null
    echo "服务已停止"
    exit 0
}

# 捕获中断信号
trap cleanup SIGINT SIGTERM

# 等待进程
wait \$BACKEND_PID \$FRONTEND_PID
EOF
    chmod +x "$PROJECT_ROOT/start_all.sh"

    echo "✓ 启动脚本创建完成"
    echo ""
}

# 验证部署
verify_deployment() {
    echo "验证部署..."

    # 检查关键文件
    REQUIRED_FILES=(
        "$BACKEND_DIR/venv/bin/python"
        "$FRONTEND_DIR/dist/index.html"
        "$BACKEND_DIR/main.py"
        "$PROJECT_ROOT/start_all.sh"
    )

    for file in "${REQUIRED_FILES[@]}"; do
        if [ ! -f "$file" ]; then
            echo "错误: 必需文件不存在: $file"
            exit 1
        fi
    done

    echo "✓ 部署验证通过"
    echo ""
}

# 主部署流程
main() {
    check_prerequisites
    prepare_offline_package
    install_python_environment
    install_nodejs_environment
    configure_application
    create_startup_scripts
    verify_deployment

    echo "========================================================"
    echo "内网部署完成！"
    echo "========================================================"
    echo ""
    echo "启动应用:"
    echo "  ./start_all.sh"
    echo ""
    echo "访问地址:"
    echo "  前端界面: http://localhost:3000"
    echo "  API文档: http://localhost:8000/docs"
    echo ""
    echo "注意事项:"
    echo "  1. 确保模型文件已放置在 ./models/ 目录"
    echo "  2. 编辑 ./backend/.env 配置API密钥"
    echo "  3. 如需GPU支持，请修改 internal_network.json 配置"
    echo "  4. 离线模式下所有依赖都从本地包安装"
    echo ""
}

# 执行主流程
main