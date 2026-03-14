#!/bin/bash

# 工艺文件辅助编辑系统 - 麒麟系统兼容性安装脚本

set -e

echo "========================================================"
echo "工艺文件辅助编辑系统 - 麒麟系统兼容性安装脚本"
echo "========================================================"
echo ""

# 检测麒麟系统
if [ -f /etc/kylin-release ]; then
    echo "检测到麒麟操作系统"
    KYLIN_VERSION=$(cat /etc/kylin-release | head -n1)
    echo "麒麟版本: $KYLIN_VERSION"
elif [ -f /etc/os-release ]; then
    source /etc/os-release
    if [[ "$NAME" == *"Kylin"* ]]; then
        echo "检测到麒麟操作系统"
        echo "系统版本: $VERSION"
    else
        echo "警告: 未检测到麒麟系统，但将继续执行兼容性设置..."
    fi
else
    echo "警告: 无法确定系统类型，但将继续执行兼容性设置..."
fi

# 设置环境变量
PYTHON_VERSION="3.9.16"
CONDA_ENV_NAME="craft-document-assistant-kylin"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "项目目录: $PROJECT_DIR"
echo "Python版本: $PYTHON_VERSION"
echo "Conda环境: $CONDA_ENV_NAME"
echo ""

# 检查Conda是否已安装
if ! command -v conda &> /dev/null; then
    echo "错误: 未找到Conda。请先安装Anaconda或Miniconda。"
    echo "下载地址: https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    exit 1
fi

# 检查Python版本
CURRENT_PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
if [[ "$CURRENT_PYTHON_VERSION" != 3.9* ]]; then
    echo "安装Python $PYTHON_VERSION..."
    conda install -y python=$PYTHON_VERSION
    if [ $? -ne 0 ]; then
        echo "错误: Python $PYTHON_VERSION安装失败"
        exit 1
    fi
fi

# 创建Conda环境
echo "创建Conda环境: $CONDA_ENV_NAME"
conda env create -f "$PROJECT_DIR/environment_kylin.yml" --name $CONDA_ENV_NAME
if [ $? -ne 0 ]; then
    echo "警告: Conda环境创建失败，尝试更新现有环境..."
    conda env update -f "$PROJECT_DIR/environment_kylin.yml" --name $CONDA_ENV_NAME
    if [ $? -ne 0 ]; then
        echo "错误: Conda环境更新失败"
        exit 1
    fi
fi

# 激活环境
echo "激活Conda环境..."
eval "$(conda shell.bash hook)"
conda activate $CONDA_ENV_NAME

# 安装Node.js依赖（国产化适配）
echo "安装Node.js依赖..."
cd "$PROJECT_DIR/frontend"
if [ -f package-kylin.json ]; then
    cp package-kylin.json package.json
fi
npm config set registry https://registry.npmmirror.com
npm install --legacy-peer-deps
if [ $? -ne 0 ]; then
    echo "警告: npm install失败，尝试使用cnpm..."
    npm install -g cnpm --registry=https://registry.npmmirror.com
    cnpm install --legacy-peer-deps
fi

# 配置麒麟系统特定设置
echo "配置麒麟系统特定设置..."
cd "$PROJECT_DIR/backend"

# 创建麒麟系统兼容性配置文件
cat > app/compatibility/kylin_config.json << EOF
{
    "system": "kylin",
    "compatibility_mode": true,
    "use_optimized_libraries": true,
    "enable_system_tray": true,
    "support_kylin_notifications": true,
    "use_domestic_cdn": true,
    "max_memory_mb": 4096
}
EOF

# 复制兼容性模块
mkdir -p app/compatibility
cp "$PROJECT_DIR/scripts/kylin_compat.py" "$PROJECT_DIR/backend/app/compatibility/kylin_compat.py"

# 安装后端依赖
echo "安装后端依赖..."
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
pip install -r requirements-kylin.txt
if [ $? -ne 0 ]; then
    echo "警告: pip install失败，继续执行..."
fi

# 创建启动脚本
cat > "$PROJECT_DIR/start_kylin.sh" << EOF
#!/bin/bash
source \$(conda info --base)/etc/profile.d/conda.sh
conda activate $CONDA_ENV_NAME
cd "$PROJECT_DIR/backend"
python main.py --compatibility-mode kylin
EOF

chmod +x "$PROJECT_DIR/start_kylin.sh"

echo ""
echo "========================================================"
echo "麒麟系统兼容性安装完成！"
echo "========================================================"
echo ""
echo "启动应用: ./start_kylin.sh"
echo ""
echo "注意事项:"
echo "1. 确保系统已安装必要的开发工具包"
echo "2. 如果使用国产CPU（龙芯、飞腾等），请确保已安装对应的优化库"
echo "3. 内存限制为4GB，请确保系统有足够内存"
echo "4. 所有依赖都从国内镜像源下载，确保网络连接正常"
echo ""