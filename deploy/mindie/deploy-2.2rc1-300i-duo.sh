#!/bin/bash
# ============================================================================
# MindIE 2.2 RC1 Deployment Script for 300I Duo Server (96GB/card)
# Two-model text serving + MinerU on CPU for PDF parsing
#
#   Complex = Qwen3-14B     (chips 0-3, port 1025)  — generation/review
#   Simple  = Qwen3-30B-A3B (chips 4-7, port 1028)  — QA/lookup
#   PDF     = MinerU on CPU (no NPU needed)
#
# Image: mindie:2.2.RC1-300I-Duo-py311-openeuler24.03-lts
#
# Prerequisites:
#   - 4x Atlas 300I Duo cards (96GB, 8 chips, IDs 0-7)
#   - Docker installed and running
#   - Model files at /root/Models/{Qwen3-14B,Qwen3-30B-A3B}
#   - MindIE image tar at ~/mindie-image.tar (or already loaded)
#   - NPU driver/firmware installed on host
#
# Usage:
#   chmod +x deploy-2.2rc1-300i-duo.sh
#   ./deploy-2.2rc1-300i-duo.sh [load|14b|30b|both|test|stop|status|manual]
# ============================================================================

set -e

IMAGE_NAME="swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:2.2.RC1-300I-Duo-py311-openeuler24.03-lts"
MODEL_DIR="/root/Models"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Config file paths inside the container
MINDIE_SERVICE_DIR="/usr/local/Ascend/mindie/latest/mindie-service"
CONFIG_PATH="${MINDIE_SERVICE_DIR}/conf/config.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------------------------------------------------------------------------
# Load Docker image from tar
# ---------------------------------------------------------------------------
load_image() {
    if docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "2.2.RC1-300I-Duo"; then
        info "MindIE image already loaded"
        return 0
    fi

    if [ ! -f ~/mindie-image.tar ]; then
        error "mindie-image.tar not found in home directory"
        exit 1
    fi

    info "Loading MindIE Docker image (18GB, takes a few minutes)..."
    docker load -i ~/mindie-image.tar
    info "Image loaded: $(docker images | grep '2.2.RC1-300I-Duo' | head -1)"
}

# ---------------------------------------------------------------------------
# Fix model dtype to float16 (required by MindIE on 300I Duo)
# Must be done BEFORE entering container, on the host filesystem
# ---------------------------------------------------------------------------
fix_dtype() {
    local model_path="$1"
    local config_file="${model_path}/config.json"

    if [ ! -f "$config_file" ]; then
        error "config.json not found at $config_file"
        return 1
    fi

    python3 -c "
import json
path = '$config_file'
with open(path) as f: cfg = json.load(f)
changed = False
if cfg.get('torch_dtype') != 'float16':
    cfg['torch_dtype'] = 'float16'
    changed = True
if 'bf16' in cfg and cfg['bf16']:
    cfg['bf16'] = False
    changed = True
if changed:
    with open(path, 'w') as f: json.dump(cfg, f, indent=2)
    print('Fixed: dtype -> float16')
else:
    print('Already float16')
"
}

# ---------------------------------------------------------------------------
# Common container run args
# ---------------------------------------------------------------------------
container_args() {
    local name="$1"
    shift
    # $@ = device IDs (e.g. 0 1 2 3)
    local devs=""
    for d in "$@"; do
        devs="$devs --device /dev/davinci$d"
    done

    echo "
        --net=host \
        --shm-size=500g \
        --privileged \
        --name $name \
        $devs \
        --device /dev/davinci_manager \
        --device /dev/devmm_svm \
        --device /dev/hisi_hdc \
        -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
        -v /usr/local/Ascend/add-ons:/usr/local/Ascend/add-ons:ro \
        -v /usr/local/sbin:/usr/local/sbin:ro \
        -v /var/log/npu:/usr/slog \
        -v /etc/hccn.conf:/etc/hccn.conf \
        -v /usr/local/Ascend/firmware:/usr/local/Ascend/firmware:ro \
        -v $MODEL_DIR:/model \
    "
}

# ---------------------------------------------------------------------------
# Build the start command that runs INSIDE the container
# ---------------------------------------------------------------------------
start_cmd() {
    local chips="$1"  # e.g. "0,1,2,3"

    cat << 'INNEREOF'
# --- Source MindIE environment (REQUIRED before starting daemon) ---
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
source /usr/local/Ascend/nnal/atb/set_env.sh 2>/dev/null || true
source /usr/local/Ascend/atb-models/set_env.sh 2>/dev/null || true
source /usr/local/Ascend/mindie/set_env.sh 2>/dev/null || true
export PYTORCH_NPU_ALLOC_CONF=expandable_segments:True
INNEREOF

    echo "export ASCEND_RT_VISIBLE_DEVICES=$chips"
    echo "export OMP_NUM_THREADS=1"
    echo "export NPU_MEMORY_FRACTION=0.95"
    echo ""
    echo "cd ${MINDIE_SERVICE_DIR}"
    echo "./bin/mindieservice_daemon"
}

# ---------------------------------------------------------------------------
# Start Qwen3-14B container (complex tier)
# ---------------------------------------------------------------------------
start_14b() {
    info "=== Deploying Qwen3-14B (chips 0-3, port 1025) ==="

    docker rm -f mindie-qwen3-14b 2>/dev/null || true
    fix_dtype "$MODEL_DIR/Qwen3-14B"

    # Start container
    eval docker run -it -d $(container_args mindie-qwen3-14b 0 1 2 3) \
        "$IMAGE_NAME" bash
    info "Container mindie-qwen3-14b started"

    # Write config.json inside container
    docker exec mindie-qwen3-14b bash -c "cat > ${CONFIG_PATH} << 'CONFIGEOF'
$(cat "$SCRIPT_DIR/config-2.2rc1-qwen3-14b.json")
CONFIGEOF"
    info "Config written to container"

    # Start daemon inside container
    docker exec mindie-qwen3-14b bash -c "$(start_cmd "0,1,2,3")" &
    info "Daemon starting... wait for 'Daemon start success!'"
    info "Check: docker exec mindie-qwen3-14b ps aux | grep mindieservice"
}

# ---------------------------------------------------------------------------
# Start Qwen3-30B-A3B container (simple tier)
# ---------------------------------------------------------------------------
start_30b() {
    info "=== Deploying Qwen3-30B-A3B (chips 4-7, port 1028) ==="

    docker rm -f mindie-qwen3-30b-a3b 2>/dev/null || true
    fix_dtype "$MODEL_DIR/Qwen3-30B-A3B"

    # Start container
    eval docker run -it -d $(container_args mindie-qwen3-30b-a3b 4 5 6 7) \
        "$IMAGE_NAME" bash
    info "Container mindie-qwen3-30b-a3b started"

    # Write config.json inside container
    docker exec mindie-qwen3-30b-a3b bash -c "cat > ${CONFIG_PATH} << 'CONFIGEOF'
$(cat "$SCRIPT_DIR/config-2.2rc1-qwen3-30b-a3b.json")
CONFIGEOF"
    info "Config written to container"

    # Start daemon inside container
    docker exec mindie-qwen3-30b-a3b bash -c "$(start_cmd "4,5,6,7")" &
    info "Daemon starting... wait for 'Daemon start success!'"
    info "Check: docker exec mindie-qwen3-30b-a3b ps aux | grep mindieservice"
}

# ---------------------------------------------------------------------------
# Test endpoints
# ---------------------------------------------------------------------------
test_models() {
    echo ""
    info "=== Testing Qwen3-14B (port 1025) ==="
    if curl -s --max-time 5 http://localhost:1025/v1/models 2>/dev/null; then
        echo ""
        info "Qwen3-14B: OK"
    else
        warn "Qwen3-14B: not responding (may still be loading weights)"
    fi

    echo ""
    info "=== Testing Qwen3-30B-A3B (port 1028) ==="
    if curl -s --max-time 5 http://localhost:1028/v1/models 2>/dev/null; then
        echo ""
        info "Qwen3-30B-A3B: OK"
    else
        warn "Qwen3-30B-A3B: not responding (may still be loading weights)"
    fi

    echo ""
    info "=== Inference test (Qwen3-14B) ==="
    curl -s --max-time 60 -X POST http://localhost:1025/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d '{
            "model": "qwen3-14b",
            "messages": [{"role": "user", "content": "你好，请用一句话介绍你自己"}],
            "max_tokens": 64,
            "stream": false
        }' 2>/dev/null || warn "Inference test failed or still loading"

    echo ""
    info "=== Inference test (Qwen3-30B-A3B) ==="
    curl -s --max-time 60 -X POST http://localhost:1028/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d '{
            "model": "qwen3-30b-a3b",
            "messages": [{"role": "user", "content": "你好，请用一句话介绍你自己"}],
            "max_tokens": 64,
            "stream": false
        }' 2>/dev/null || warn "Inference test failed or still loading"
}

# ---------------------------------------------------------------------------
# Stop containers
# ---------------------------------------------------------------------------
stop_all() {
    info "Stopping containers..."
    docker rm -f mindie-qwen3-14b 2>/dev/null || true
    docker rm -f mindie-qwen3-30b-a3b 2>/dev/null || true
    info "All containers stopped and removed"
}

# ---------------------------------------------------------------------------
# Status check
# ---------------------------------------------------------------------------
show_status() {
    echo ""
    info "=== Container Status ==="
    docker ps -a --filter "name=mindie-" --format "table {{.Names}}\t{{.Status}}" 2>/dev/null || echo "No mindie containers"

    echo ""
    info "=== NPU Status ==="
    npu-smi info 2>/dev/null || warn "npu-smi not available"

    echo ""
    info "=== Port Check ==="
    for port in 1025 1028; do
        if curl -s --max-time 2 http://localhost:$port/v1/models >/dev/null 2>&1; then
            info "Port $port: ACTIVE"
        else
            warn "Port $port: not responding"
        fi
    done
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
case "${1:-help}" in
    load)
        load_image
        ;;
    14b)
        load_image
        start_14b
        ;;
    30b)
        load_image
        start_30b
        ;;
    both)
        load_image
        start_14b
        start_30b
        ;;
    test)
        test_models
        ;;
    stop)
        stop_all
        ;;
    status)
        show_status
        ;;
    manual)
        echo "Manual steps: see deploy-2.2rc1-300i-duo.sh source code"
        ;;
    help|*)
        echo "Usage: $0 {load|14b|30b|both|test|stop|status}"
        echo ""
        echo "  load    - Load MindIE Docker image from tar"
        echo "  14b     - Deploy Qwen3-14B (chips 0-3, port 1025)"
        echo "  30b     - Deploy Qwen3-30B-A3B (chips 4-7, port 1028)"
        echo "  both    - Deploy both models"
        echo "  test    - Test both model endpoints"
        echo "  stop    - Stop and remove all MindIE containers"
        echo "  status  - Show container, NPU, and port status"
        echo ""
        echo "Chip allocation (96GB/card, 48GB/chip):"
        echo "  Complex (chips 0-3) port 1025  → Qwen3-14B"
        echo "  Simple  (chips 4-7) port 1028  → Qwen3-30B-A3B"
        echo "  PDF parsing: MinerU on CPU (no NPU)"
        ;;
esac
