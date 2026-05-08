#!/bin/bash
# ============================================================================
# MinerU2.5-Pro-2604-1.2B (VLM for PDF Parsing) - MindIE 2.2 RC1 on Atlas 300I Duo
#
# Chips: 0-1 (physical) | Port: 1040 | worldSize: 2
# Container: mindie-mineru-vlm
#
# This model is MinerU's dedicated VLM (Qwen2VL architecture, fine-tuned for
# document layout detection). MinerU pipeline on Kylin connects to it via
# http-client backend (OpenAI-compatible API).
#
# Architecture (coexist with Qwen3-30B-A3B):
#   Chips 0-1: MinerU2.5-Pro-1.2B  (VLM)          port 1040
#   Chips 4-7: Qwen3-30B-A3B       (all LLM tasks) port 1025
#   Chips 2-3: free (backup)
#
# Strategy: Start container with DEFAULT config, then PATCH only the fields
# we need. This avoids missing any required fields that the default config
# already has.
#
# Prerequisites:
#   - Model at /home/data/MinerU2.5-Pro-2604-1.2B
#   - MindIE image loaded
#   - NPU driver/firmware installed on host
#
# Usage:
#   chmod +x run-mineru-vlm.sh
#   ./run-mineru-vlm.sh          # start
#   ./run-mineru-vlm.sh stop     # stop
#   ./run-mineru-vlm.sh test     # test endpoint
#   ./run-mineru-vlm.sh logs     # view daemon logs
# ============================================================================

IMAGE_NAME="swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:2.2.RC1-300I-Duo-py311-openeuler24.03-lts"
MODEL_DIR="/home/data"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_PATH="/usr/local/Ascend/mindie/latest/mindie-service/conf/config.json"
CONTAINER_NAME="mindie-mineru-vlm"

case "${1:-start}" in
    start)
        echo "[INFO] Starting MinerU2.5-Pro-1.2B VLM (chips 0-1, port 1040)..."
        echo "[INFO] This model coexists with Qwen3-30B-A3B on chips 4-7."

        # Remove old container if exists
        docker rm -f $CONTAINER_NAME 2>/dev/null || true

        # Fix model dtype to float16 (required by 300I Duo, no BF16 support)
        python3 -c "
import json, sys
path = '$MODEL_DIR/MinerU2.5-Pro-2604-1.2B/config.json'
try:
    with open(path) as f: cfg = json.load(f)
    changed = False
    # Root-level dtype
    if cfg.get('dtype') == 'bfloat16':
        cfg['dtype'] = 'float16'
        changed = True
    if cfg.get('torch_dtype') not in ('float16', None):
        cfg['torch_dtype'] = 'float16'
        changed = True
    if cfg.get('bf16'):
        cfg['bf16'] = False
        changed = True
    # text_config dtype
    tc = cfg.get('text_config', {})
    if tc.get('dtype') == 'bfloat16':
        tc['dtype'] = 'float16'
        changed = True
    # vision_config dtype
    vc = cfg.get('vision_config', {})
    if vc.get('dtype') == 'bfloat16':
        vc['dtype'] = 'float16'
        changed = True
    if changed:
        with open(path, 'w') as f: json.dump(cfg, f, indent=2, ensure_ascii=False)
        print('Fixed dtype -> float16 (root, text_config, vision_config)')
    else:
        print('dtype OK')
except Exception as e:
    print(f'Warning: {e}', file=sys.stderr)
"

        # Run container: use --net=host --privileged (same as qwen3-30b-a3b)
        # NPU IPC requires full host access; device-by-device mapping is insufficient.
        # Isolation is done by ASCEND_RT_VISIBLE_DEVICES=0,1 in daemon.
        docker run -d \
            --name $CONTAINER_NAME \
            --restart=unless-stopped \
            --net=host \
            --privileged \
            --shm-size=500g \
            -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
            -v /usr/local/Ascend/add-ons:/usr/local/Ascend/add-ons:ro \
            -v /usr/local/sbin:/usr/local/sbin:ro \
            -v $MODEL_DIR:/models:ro \
            --ipc=host \
            $IMAGE_NAME \
            tail -f /dev/null

        echo "[INFO] Container started. Patching config (keep defaults, override only what we need)..."

        # Patch the DEFAULT config instead of replacing it entirely.
        docker exec $CONTAINER_NAME python3 -c '
import json

path = "/usr/local/Ascend/mindie/latest/mindie-service/conf/config.json"

with open(path) as f:
    cfg = json.load(f)

# --- ServerConfig overrides ---
sc = cfg.setdefault("ServerConfig", {})
sc["ipAddress"] = "0.0.0.0"
sc["port"] = 1040
sc["managementPort"] = 1041
sc["metricsPort"] = 1042
sc["maxLinkNum"] = 1000
sc["httpsEnabled"] = False
sc["allowAllZeroIpListening"] = True
sc["openAiSupport"] = "vllm"
sc["inferMode"] = "standard"
sc["tokenTimeout"] = 600
sc["e2eTimeout"] = 600

# --- LogConfig (keep existing, add missing) ---
lc = cfg.setdefault("LogConfig", {})
if "dynamicLogLevelValidHours" not in lc:
    lc["dynamicLogLevelValidHours"] = 2
if "dynamicLogLevelValidTime" not in lc:
    lc["dynamicLogLevelValidTime"] = ""

# --- BackendConfig overrides ---
bc = cfg.setdefault("BackendConfig", {})
bc["backendName"] = "mindieservice_llm_engine"
bc["modelInstanceNumber"] = 1
bc["npuDeviceIds"] = [[0,1]]
bc["tokenizerProcessNumber"] = 8

# ModelDeployConfig
mdc = bc.setdefault("ModelDeployConfig", {})
mdc["maxSeqLen"] = 4096
mdc["maxInputTokenLen"] = 3072
mdc["truncation"] = False

mc = {
    "modelInstanceType": "Standard",
    "modelName": "MinerU2.5-Pro-2604-1.2B",
    "modelWeightPath": "/models/MinerU2.5-Pro-2604-1.2B",
    "worldSize": 2,
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
sch["maxPrefillBatchSize"] = 4
sch["maxPrefillTokens"] = 3072
sch["maxBatchSize"] = 32
sch["maxIterTimes"] = 2048

with open(path, "w") as f:
    json.dump(cfg, f, indent=4)

print("Config patched successfully.")
'

        echo "[INFO] Starting MindIE daemon (chips 0-1, port 1040)..."
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
export ASCEND_RT_VISIBLE_DEVICES=0,1
export OMP_NUM_THREADS=1
export NPU_MEMORY_FRACTION=0.95

echo "--- Checking model files ---" >> $LOG
ls -la /models/MinerU2.5-Pro-2604-1.2B/config.json >> $LOG 2>&1

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
        echo "[INFO] Testing MinerU VLM on port 1040..."
        echo ""
        echo "=== /v1/models ==="
        curl -s --max-time 5 http://localhost:1040/v1/models 2>/dev/null || echo "Not responding (may still be loading)"
        echo ""
        echo ""
        echo "=== Inference test ==="
        curl -s --max-time 60 -X POST http://localhost:1040/v1/chat/completions \
            -H "Content-Type: application/json" \
            -d '{
                "model": "MinerU2.5-Pro-2604-1.2B",
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
