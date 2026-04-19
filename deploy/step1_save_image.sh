#!/bin/bash
# ============================================
# Step 1: 在联网机器上保存 MindIE 镜像
# ============================================
# 在有网的 Linux 机器上执行（x86 或 ARM 都行）
#
# 前置：去昇腾社区申请镜像权限
#   https://www.hiascend.com/developer/ascendhub/detail/mindie
#   选 MindIE 2.3.0-300I-Duo，申请通过后拿到拉取命令
# ============================================

set -e

MINDIE_IMAGE="swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:2.3.0-300I-Duo-py311-openeuler24.03-lts"
OUTPUT_FILE="mindie-2.3.0-300I-Duo.tar.gz"

echo "[1/3] 拉取镜像..."
# 如果是 x86 机器上拉 ARM 镜像：
docker pull --platform=arm64 "${MINDIE_IMAGE}"
# 如果本身就是 ARM 机器，去掉 --platform 参数：
# docker pull "${MINDIE_IMAGE}"

echo "[2/3] 保存为 tar 文件..."
docker save "${MINDIE_IMAGE}" | gzip > "${OUTPUT_FILE}"

echo "[3/3] 完成!"
echo ""
echo "文件: ${OUTPUT_FILE}"
echo "大小: $(duh -h ${OUTPUT_FILE} | cut -f1)"
echo ""
echo "下一步: 将此文件拷贝到 U 盘，传到离线服务器"
