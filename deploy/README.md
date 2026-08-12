# Local Deployment Guide (Kylin V10 + Ascend NPU)

Target: 192.168.1.223, Kylin V10 laptop with Ascend NPU

## Transfer Checklist

### 1. Model Files (~85GB total)

```
C:\models\Qwen3-14B\      (28GB)  -> /data/models/Qwen3-14B/
C:\models\Qwen3-30B-A3B\  (57GB)  -> /data/models/Qwen3-30B-A3B/
```

Transfer method options:
- SCP: `scp -r C:\models\Qwen3-14B user@192.168.1.223:/data/models/`
- rsync: `rsync -avP --progress C:\models\Qwen3-14B/ user@192.168.1.223:/data/models/Qwen3-14B/`
- USB drive: copy directly if in the same location

### 2. Project Code

```bash
# On the target machine
cd /data
git clone https://github.com/alerlocked/llbased-word.git localknowledgebase-word
cd localknowledgebase-word
git checkout feature/v1-cleanup
```

Or copy the entire project directory via SCP/rsync.

### 3. Deploy Directory

```
deploy/              -> Copy to /data/localknowledgebase-word/deploy/
  mindie/
    config-qwen3-14b.json
    config-qwen3-30b-a3b.json
    start-mindie.sh
  env-local.template
```

## Deployment Steps

### Step 1: Verify Ascend NPU

```bash
npu-smi info
# Should show NPU card(s) with driver version >= 24.1.0
```

### Step 2: Load MindIE Docker Image

Option A: From SWR mirror (needs internet):
```bash
docker login swr.cn-south-1.myhuaweicloud.com
docker pull --platform=arm64 swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:2.2.RC1-800I-A2-py311-openeuler24.03-lts
# Tag for convenience:
docker tag swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:2.2.RC1-800I-A2-py311-openeuler24.03-lts mindie:2.2.RC1-800I-A2-py311-openeuler24.03-lts
```

Option B: From offline tar file (if pre-downloaded):
```bash
docker load -i mindie-2.2.RC1-800I-A2-py311-openeuler24.03-lts.tar.gz
```

### Step 3: Set Model Permissions

```bash
chmod -R 750 /data/models/Qwen3-14B
chmod -R 750 /data/models/Qwen3-30B-A3B
```

### Step 4: Start MindIE

```bash
cd /data/localknowledgebase-word/deploy/mindie
chmod +x start-mindie.sh

# Start Qwen3-14B only (2 NPUs needed)
./start-mindie.sh 14b

# OR start Qwen3-30B-A3B only (2 NPUs needed)
./start-mindie.sh 30b

# OR start both (4+ NPUs needed)
./start-mindie.sh both
```

### Step 5: Start Inference Service Inside Container

```bash
# Enter the container
docker exec -it mindie-qwen3-14b bash   # or mindie-qwen3-30b-a3b

# Set environment
export ASCEND_RT_VISIBLE_DEVICES=0,1
export OMP_NUM_THREADS=1
export NPU_MEMORY_FRACTION=0.95

# Start the service
cd /usr/local/Ascend/mindie/latest/mindie-service
./bin/mindieservice_daemon
```

Wait for `Daemon start success!` message.

### Step 6: Test MindIE API

```bash
# Check available models
curl http://localhost:1025/v1/models

# Test chat completion
curl -X POST http://localhost:1025/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-14b",
    "messages": [{"role": "user", "content": "hello"}],
    "max_tokens": 64
  }'
```

### Step 7: Configure Project for Local LLM

```bash
cd /data/localknowledgebase-word

# Use the local .env template
cp deploy/env-local.template backend/.env

# Edit if needed (e.g., change model names, port)
vim backend/.env
```

### Step 8: Start Project Backend

```bash
cd /data/localknowledgebase-word/backend

# Install dependencies
pip install -r requirements.txt

# Start the backend
python main.py
# Accessible at http://192.168.1.223:8000
```

### Step 9: Start Frontend

```bash
cd /data/localknowledgebase-word/frontend

# Install dependencies
npm install

# Start dev server
npm run dev
# Accessible at http://192.168.1.223:3000
```

## Architecture

```
[Frontend :3000] -> [Backend :8000] -> [MindIE :1025] -> [Ascend NPU]
                                       (OpenAI-compatible API)
                                       Model: Qwen3-14B / Qwen3-30B-A3B
```

## Model Selection Strategy

| Task Type | Model | Reason |
|-----------|-------|--------|
| QA / Term lookup / Format check | Qwen3-14B (28GB) | Fast, sufficient for simple tasks |
| Document generation / Compliance review / Deep analysis | Qwen3-30B-A3B (57GB) | MoE, only 3B activated params, good balance |

## Troubleshooting

### NPU not detected
```bash
# Check driver
cat /usr/local/Ascend/driver/version.info
# Reinstall driver if needed from hiascend.com
```

### Docker can't access NPU
```bash
# Check device files
ls -la /dev/davinci*
# Should see davinci0, davinci_manager, devmm_svm, hisi_hdc
```

### MindIE startup fails
```bash
# Check logs
docker exec mindie-qwen3-14b cat /usr/local/Ascend/mindie/latest/mindie-service/logs/mindie-server.log
# Common issues:
#   - worldSize mismatch with actual NPU count
#   - Model path incorrect (check /model/ inside container)
#   - Permission issues (chmod 750 on model dir)
```

### Out of NPU memory
- Reduce `maxSeqLen` in config (try 4096)
- Reduce `maxBatchSize` in ScheduleConfig (try 32)
- Reduce `NPU_MEMORY_FRACTION` (try 0.90)
