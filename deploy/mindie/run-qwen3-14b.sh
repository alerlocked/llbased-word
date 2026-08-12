#!/usr/bash
# ============================================================================
# Qwen3-14B (Complex Tier) - MindIE 2.2 RC1 on Atlas 300I Duo
#
# Chips: 0-3 (physical) | Port: 1025 | worldSize: 4
# Container: mindie-qwen3-14b
#
# Strategy: Start container with DEFAULT config, then PATCH only the fields
# we need. This avoids missing any required fields that the default config
# already has.
#
# Prerequisites:
#   - Model at /home/data/Qwen3-14B
#   - MindIE image loaded
#   - NPU driver/firmware installed on host
#
# Usage:
#   chmod +x run-qwen3-14b.sh
#   ./run-qwen3-14b.sh          # start
#   ./run-qwen3-14b.sh stop     # stop
#   ./run-qwen3-14b.sh test     # test endpoint
#   ./run-qwen3-14b.sh logs     # view daemon logs
# ============================================================================

IMAGE_NAME="swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:2.2.RC1-300I-Duo-py311-openeuler24.03-lts"
MODEL_DIR="/home/data"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_PATH="/usr/local/Ascend/mindie/latest/mindie-service/conf/config.json"
CONTAINER_NAME="mindie-qwen3-14b"

case "${1:-start}" in
    start)
        echo "[INFO] Starting Qwen3-14B (chips 0-3, port 1025)..."

        # Remove old container if exists
        docker rm -f $CONTAINER_NAME 2>/dev/null || true

        # Fix model dtype to float16 (required by 300I Duo)
        python3 -c "
import json, sys
path = '$MODEL_DIR/Qwen3-14B/config.json'
try:
    with open(path) as f: cfg = json.load(f)
    changed = False
    if cfg.get('torch_dtype') != 'float16':
        cfg['torch_dtype'] = 'float16'
        changed = True
    if cfg.get('bf16'):
        cfg['bf16'] = False
        changed = True
    if changed:
        with open(path, 'w') as f: json.dump(cfg, f, indent=2)
        print('Fixed dtype -> float16')
    else:
        print('dtype OK')
except Exception as e:
    print(f'Warning: {e}', file=sys.stderr)
"

        # Run container
        docker run -d \
            --name $CONTAINER_NAME \
            --restart=unless-stopped \
            -p 1025:1025 \
            -p 1026:1026 \
            -p 1027:1027 \
            --device /dev/davinci0 \
            --device /dev/davinci1 \
            --device /dev/davinci2 \
            --device /dev/davinci3 \
            --device /dev/davinci_manager \
            --device /dev/devmm_svm \
            --device /dev/hisi_hdc \
            -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
            -v /usr/local/Ascend/add-ons:/usr/local/Ascend/add-ons:ro \
            -v /usr/local/sbin:/usr/local/sbin:ro \
            -v $MODEL_DIR:/models:ro \
            --ipc=host \
            $IMAGE_NAME \
            tail -f /dev/null

        echo "[INFO] Container started. Patching config (keep defaults, override only what we need)..."

        # Patch the DEFAULT config instead of replacing it entirely.
        # This preserves all required boolean/string fields that MindIE expects.
        docker exec $CONTAINER_NAME python3 -c '
import json

path = "/usr/local/Ascend/mindie/latest/mindie-service/conf/config.json"

with open(path) as f:
    cfg = json.load(f)

# --- ServerConfig overrides ---
sc = cfg.setdefault("ServerConfig", {})
sc["ipAddress"] = "0.0.0.0"
sc["port"] = 1025
sc["managementPort"] = 1026
sc["metricsPort"] = 1027
sc["maxLinkNum"] = 1000
sc["httpsEnabled"] = False
sc["allowAllZeroIpListening"] = True
sc["inferMode"] = "standard"
sc["tokenTimeout"] = 600
sc["e2eTimeout"] = 600

# --- LogConfig overrides (keep existing fields, add missing) ---
lc = cfg.setdefault("LogConfig", {})
if "dynamicLogLevelValidHours" not in lc:
    lc["dynamicLogLevelValidHours"] = 2
if "dynamicLogLevelValidTime" not in lc:
    lc["dynamicLogLevelValidTime"] = ""

# --- BackendConfig overrides ---
bc = cfg.setdefault("BackendConfig", {})
bc["backendName"] = "mindieservice_llm_engine"
bc["modelInstanceNumber"] = 1
bc["npuDeviceIds"] = [[0,1,2,3]]
bc["tokenizerProcessNumber"] = 8

# ModelDeployConfig
mdc = bc.setdefault("ModelDeployConfig", {})
mdc["maxSeqLen"] = 8192
mdc["maxInputTokenLen"] = 6144
mdc["truncation"] = False

mc = {
    "modelInstanceType": "Standard",
    "modelName": "qwen3-14b",
    "modelWeightPath": "/models/Qwen3-14B",
    "worldSize": 4,
    "cpuMemSize": 5,
    "npuMemSize": -1,
    "backendType": "atb",
    "trustRemoteCode": False
}
mdc["ModelConfig"] = [mc]

# ScheduleConfig
sch = bc.setdefault("ScheduleConfig", {})
sch["templateType"] = "Standard"
sch["templateName"] = "Standard_LLM"
sch["cacheBlockSize"] = 128
sch["maxPrefillBatchSize"] = 8
sch["maxPrefillTokens"] = 6144
sch["maxBatchSize"] = 200
sch["maxIterTimes"] = 2048

with open(path, "w") as f:
    json.dump(cfg, f, indent=4)

print("Config patched successfully.")
'

        echo "[INFO] Starting MindIE daemon (chips 0-3, port 1025)..."
        echo "[INFO] Wait for 'Daemon start success!' in logs..."

        # Write daemon startup script inside container
        docker exec $CONTAINER_NAME bash -c 'cat > /tmp/start_daemon.sh << '\''DAEMONSCRIPT'\''
#!/bin/bash
LOG=/tmp/mindie.log
echo "=== Daemon start at $(date) ===" > $LOG

echo "--- Sourcing environments ---" >> $LOG
source /usr/local/Ascend/ascend-toolkit/set_env.sh >> $LOG 2>&1
source /usr/local/Ascend/nnal/atb/set_env.sh >> $LOG 2>&1
source /usr/local/Ascend/atb-models/set_env.sh >> $LOG 2>&1
source /usr/local/Ascend/mindie/set_env.sh >> $LOG 2>&1

export PYTORCH_NPU_ALLOC_CONF=expandable_segments:True
export ASCEND_RT_VISIBLE_DEVICES=0,1,2,3
export OMP_NUM_THREADS=1
export NPU_MEMORY_FRACTION=0.95

echo "--- Checking model files ---" >> $LOG
ls -la /models/Qwen3-14B/config.json >> $LOG 2>&1

echo "--- Starting daemon ---" >> $LOG
cd /usr/local/Ascend/mindie/latest/mindie-service
./bin/mindieservice_daemon >> $LOG 2>&1
DAEMONSCRIPT
chmod +x /tmp/start_daemon.sh'

        # Execute daemon script in background
        docker exec -d $CONTAINER_NAME /tmp/start_daemon.sh

        echo "[INFO] Use '$0 logs' to check startup progress"
        echo "[INFO] Use '$0 test' to test endpoint"
        ;;

    stop)
        echo "[INFO] Stopping $CONTAINER_NAME..."
        docker rm -f $CONTAINER_NAME 2>/dev/null || true
        echo "[INFO] Stopped."
        ;;

    test)
        echo "[INFO] Testing Qwen3-14B on port 1025..."
        echo ""
        echo "=== /v1/models ==="
        curl -s --max-time 5 http://localhost:1025/v1/models 2>/dev/null || echo "Not responding (may still be loading)"
        echo ""
        echo ""
        echo "=== Inference test ==="
        curl -s --max-time 60 -X POST http://localhost:1025/v1/chat/completions \
            -H "Content-Type: application/json" \
            -d '{
                "model": "qwen3-14b",
                "messages": [{"role": "user", "content": "你好，请用一句话介绍你自己"}],
                "max_tokens": 64,
                "stream": false
            }' || echo "Inference failed or still loading"
        echo ""
        ;;

    logs)
        docker exec $CONTAINER_NAME cat /tmp/mindie.log 2>/dev/null || echo 'No daemon logs found'
        ;;

    *)
        echo "Usage: $0 {start|stop|test|logs}"
        ;;
esac
