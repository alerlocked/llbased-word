#!/bin/bash
# ============================================
# Step 3: 配置并启动 MindIE 推理服务
# ============================================
# 在麒麟服务器上执行（需要 root）
# 前置：step2 已加载镜像，CANN 驱动已安装，模型已就位
# ============================================

set -e

# ---- 配置区（按实际修改） ----
MODEL_DIR="/root/Models"                   # 模型存放目录（按实际路径改）
MODEL_NAME="Qwen3.5-32B-Instruct"          # 模型目录名
CONTAINER_NAME="mindie-qwen35"
SERVICE_PORT=1025
TP_SIZE=4                                  # 张量并行度
DEVICE_IDS="0,1,2,3"                       # NPU 设备 ID
MINDIE_IMAGE="swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:2.3.0-300I-Duo-py311-openeuler24.03-lts"
# ---- 配置区结束 ----

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }

# ---- 1. 检查环境 ----
log "检查 NPU..."
npu-smi info | head -20

log "检查模型..."
MODEL_PATH="${MODEL_DIR}/${MODEL_NAME}"
if [ ! -f "${MODEL_PATH}/config.json" ]; then
    err "找不到模型配置: ${MODEL_PATH}/config.json"
    err "请修改脚本顶部的 MODEL_DIR / MODEL_NAME"
    exit 1
fi
log "模型目录: ${MODEL_PATH}"

# ---- 2. 确保模型为 FP16 ----
log "检查模型精度..."
python3 -c "
import json, sys
with open('${MODEL_PATH}/config.json') as f:
    cfg = json.load(f)
dtype = cfg.get('torch_dtype', 'NOT_SET')
if dtype != 'float16':
    print(f'当前精度: {dtype}，正在改为 float16...')
    cfg['torch_dtype'] = 'float16'
    if 'bf16' in cfg:
        cfg['bf16'] = False
    with open('${MODEL_PATH}/config.json', 'w') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    print('已修改')
else:
    print('精度已是 float16')
"

# ---- 3. 检查镜像 ----
if ! docker images | grep -q "mindie"; then
    err "MindIE 镜像未找到，请先执行 step2_load_image.sh"
    exit 1
fi

# ---- 4. 清理旧容器 ----
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log "清理旧容器..."
    docker rm -f "${CONTAINER_NAME}" > /dev/null
fi

# ---- 5. 启动容器 ----
log "启动容器..."
DEVICE_ARGS=""
IFS=',' read -ra IDS <<< "$DEVICE_IDS"
for id in "${IDS[@]}"; do
    DEVICE_ARGS="${DEVICE_ARGS} --device /dev/davinci${id}"
done

docker run -it -d \
    --net=host \
    --shm-size=1g \
    --privileged \
    --name "${CONTAINER_NAME}" \
    ${DEVICE_ARGS} \
    --device=/dev/davinci_manager \
    --device=/dev/hisi_hdc \
    --device=/dev/devmm_svm \
    -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
    -v /usr/local/sbin:/usr/local/sbin:ro \
    -v "${MODEL_DIR}:/mnt" \
    "${MINDIE_IMAGE}" \
    bash

log "容器已启动"

# ---- 6. 写入 MindIE 配置 ----
log "写入 MindIE 配置..."

# Build npuDeviceIds JSON array
IFS=',' read -ra IDS <<< "$DEVICE_IDS"
DEVICE_JSON="["
for i in "${!IDS[@]}"; do
    if [ $i -gt 0 ]; then DEVICE_JSON+=","; fi
    DEVICE_JSON+="${IDS[$i]}"
done
DEVICE_JSON+="]"

docker exec "${CONTAINER_NAME}" bash -c "cat > /usr/local/Ascend/mindie/latest/mindie-service/conf/config.json <<'EOFCFG'
{
  \"ServerConfig\": {
    \"ipAddress\": \"0.0.0.0\",
    \"port\": ${SERVICE_PORT},
    \"managementPort\": 1041,
    \"metricsPort\": 1042,
    \"httpsEnabled\": false
  },
  \"BackendConfig\": {
    \"npuDeviceIds\": [${DEVICE_JSON}],
    \"ModelDeployConfig\": {
      \"truncation\": false,
      \"ModelConfig\": [
        {
          \"modelName\": \"qwen35\",
          \"modelWeightPath\": \"/mnt/${MODEL_NAME}\",
          \"worldSize\": ${TP_SIZE},
          \"torch_dtype\": \"float16\"
        }
      ]
    }
  }
}
EOFCFG"

log "配置完成"

# ---- 7. 启动推理服务 ----
log "启动推理服务..."
docker exec -d "${CONTAINER_NAME}" bash -c \
    "cd /usr/local/Ascend/mindie/latest/mindie-service/bin && ./mindieservice_daemon"

log "等待服务就绪 (最多等 180 秒)..."
WAITED=0
while [ $WAITED -lt 180 ]; do
    if curl -s "http://localhost:${SERVICE_PORT}/v1/models" > /dev/null 2>&1; then
        log "服务已就绪!"
        break
    fi
    sleep 5
    WAITED=$((WAITED + 5))
    printf "."
done
echo ""

if [ $WAITED -ge 180 ]; then
    warn "启动超时，查看日志:"
    echo "  docker logs ${CONTAINER_NAME}"
    exit 1
fi

# ---- 8. 测试 ----
log "测试推理..."
RESULT=$(curl -s -X POST "http://localhost:${SERVICE_PORT}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{
        "model": "qwen35",
        "messages": [{"role": "user", "content": "你好，用一句话介绍你自己"}],
        "max_tokens": 64,
        "temperature": 0.7,
        "stream": false
    }')

echo "$RESULT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('响应:', d['choices'][0]['message']['content'])
except:
    print('原始响应:', sys.stdin.read())
"

echo ""
echo "============================================"
log "部署完成!"
echo "============================================"
echo ""
echo "  API 地址:  http://<服务器IP>:${SERVICE_PORT}/v1/chat/completions"
echo "  模型名称:  qwen35"
echo "  格式:      OpenAI API 兼容"
echo ""
echo "  常用命令:"
echo "    docker logs ${CONTAINER_NAME}        # 查看日志"
echo "    docker exec -it ${CONTAINER_NAME} bash  # 进入容器"
echo "    docker stop ${CONTAINER_NAME}        # 停止"
echo "    docker restart ${CONTAINER_NAME}     # 重启"
echo ""
