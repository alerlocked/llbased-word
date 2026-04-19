#!/bin/bash
# ============================================
# Step 2: 在离线服务器上加载 MindIE 镜像
# ============================================
# 在麒麟服务器上执行（需要 root）
# ============================================

set -e

IMAGE_FILE="mindie-2.3.0-300I-Duo.tar.gz"

if [ ! -f "$IMAGE_FILE" ]; then
    echo "[ERROR] 找不到镜像文件: ${IMAGE_FILE}"
    echo "请将 step1 导出的 tar.gz 放到当前目录"
    exit 1
fi

echo "[1/3] 加载镜像..."
docker load -i "${IMAGE_FILE}"

echo "[2/3] 验证镜像..."
docker images | grep mindie

echo "[3/3] 完成!"
echo ""
echo "MindIE 镜像已就绪，下一步执行 step3_start_service.sh"
