#!/bin/bash

# 工艺文件辅助编辑系统 - 模型设置脚本
# 用于下载和配置DeepSeek-R1、BGE-Embedding、BGE-Rerank模型

set -e

echo "🔄 开始设置AI模型..."

# 配置变量
MODELS_DIR="./models"
DEEPSEEK_R1_DIR="$MODELS_DIR/deepseek-r1"
BGE_EMBEDDING_DIR="$MODELS_DIR/bge-large-zh-v1.5"
BGE_RERANK_DIR="$MODELS_DIR/bge-reranker-large"

# 创建模型目录
mkdir -p "$MODELS_DIR"
mkdir -p "$DEEPSEEK_R1_DIR"
mkdir -p "$BGE_EMBEDDING_DIR"
mkdir -p "$BGE_RERANK_DIR"

echo "📁 模型目录已创建: $MODELS_DIR"

# 检查是否需要下载模型
if [ ! -f "$DEEPSEEK_R1_DIR/README.md" ]; then
    echo "⚠️  DeepSeek-R1模型未找到"
    echo "📝 请手动下载DeepSeek-R1模型到: $DEEPSEEK_R1_DIR"
    echo "🔗  下载地址: https://huggingface.co/deepseek-ai/deepseek-r1"
    echo ""
    echo "💡 建议下载14B版本以节省内存 (需要24GB GPU内存)"
    echo "💡 32B版本需要64GB GPU内存"
else
    echo "✅ DeepSeek-R1模型已存在"
fi

if [ ! -f "$BGE_EMBEDDING_DIR/README.md" ]; then
    echo "⚠️  BGE-Embedding模型未找到"
    echo "📝 请手动下载BGE-Embedding模型到: $BGE_EMBEDDING_DIR"
    echo "🔗  下载地址: https://huggingface.co/BAAI/bge-large-zh-v1.5"
else
    echo "✅ BGE-Embedding模型已存在"
fi

if [ ! -f "$BGE_RERANK_DIR/README.md" ]; then
    echo "⚠️  BGE-Rerank模型未找到"
    echo "📝 请手动下载BGE-Rerank模型到: $BGE_RERANK_DIR"
    echo "🔗  下载地址: https://huggingface.co/BAAI/bge-reranker-large"
else
    echo "✅ BGE-Rerank模型已存在"
fi

# 创建模型配置文件
cat > "$MODELS_DIR/model_paths.json" << EOF
{
  "deepseek_r1": {
    "14b": "$DEEPSEEK_R1_DIR",
    "32b": "$DEEPSEEK_R1_DIR"
  },
  "bge_embedding": "$BGE_EMBEDDING_DIR",
  "bge_rerank": "$BGE_RERANK_DIR"
}
EOF

echo "✅ 模型路径配置已创建: $MODELS_DIR/model_paths.json"

# 安装Python依赖
echo "📦 安装Python依赖..."
pip install -r requirements-models.txt

echo ""
echo "🎉 模型设置完成！"
echo ""
echo "📋 下一步操作:"
echo "1. 确保已下载所有模型文件到对应目录"
echo "2. 运行 'python backend/app/models/test_models.py' 测试模型加载"
echo "3. 启动应用: 'python backend/main.py'"
echo ""
echo "💡 注意: 模型文件较大，请确保有足够的磁盘空间和GPU内存"