# MindIE Docker 内启动小模型（Qwen3.5-9B / 2B）

> 适用于单张 300I Duo 卡（2 颗 310P3，每颗 44GB）
> 9B 模型 FP16 约 18GB，2B 模型约 4GB，单卡完全够用

## 配置文件

进入容器后编辑：

```bash
vim /usr/local/Ascend/mindie/latest/mindie-service/conf/config.json
```

### Qwen3.5-9B（推荐，单卡 TP=2）

```json
{
  "ServerConfig": {
    "ipAddress": "0.0.0.0",
    "port": 1025,
    "managementPort": 1041,
    "metricsPort": 1042,
    "httpsEnabled": false
  },
  "BackendConfig": {
    "npuDeviceIds": [[0, 1]],
    "ModelDeployConfig": {
      "truncation": false,
      "ModelConfig": [
        {
          "modelName": "qwen35-9b",
          "modelWeightPath": "/mnt/Qwen3.5-9B-Instruct",
          "worldSize": 2,
          "torch_dtype": "float16"
        }
      ]
    }
  }
}
```

### Qwen3.5-2B（极致轻量，单芯片 TP=1 就行）

```json
{
  "ServerConfig": {
    "ipAddress": "0.0.0.0",
    "port": 1025,
    "managementPort": 1041,
    "metricsPort": 1042,
    "httpsEnabled": false
  },
  "BackendConfig": {
    "npuDeviceIds": [[0]],
    "ModelDeployConfig": {
      "truncation": false,
      "ModelConfig": [
        {
          "modelName": "qwen35-2b",
          "modelWeightPath": "/mnt/Qwen3.5-2B-Instruct",
          "worldSize": 1,
          "torch_dtype": "float16"
        }
      ]
    }
  }
}
```

### 多实例并行（44 张卡的玩法）

一张 300I Duo 跑一个 9B，44 张卡 = 44 个独立实例：

```json
{
  "ServerConfig": {
    "ipAddress": "0.0.0.0",
    "port": 1025,
    "managementPort": 1041,
    "metricsPort": 1042,
    "httpsEnabled": false
  },
  "BackendConfig": {
    "npuDeviceIds": [[0,1],[2,3],[4,5],[6,7],[8,9],[10,11],[12,13],[14,15],[16,17],[18,19],[20,21],[22,23],[24,25],[26,27],[28,29],[30,31],[32,33],[34,35],[36,37],[38,39],[40,41],[42,43],[44,45],[46,47],[48,49],[50,51],[52,53],[54,55],[56,57],[58,59],[60,61],[62,63],[64,65],[66,67],[68,69],[70,71],[72,73],[74,75],[76,77],[78,79],[80,81],[82,83],[84,85],[86,87]],
    "ModelDeployConfig": {
      "truncation": false,
      "ModelConfig": [
        {
          "modelName": "qwen35-9b",
          "modelWeightPath": "/mnt/Qwen3.5-9B-Instruct",
          "worldSize": 2,
          "torch_dtype": "float16"
        }
      ]
    }
  }
}
```

## 启动命令

```bash
# 进入容器
docker exec -it mindie-qwen35 bash

# 修改模型精度为 FP16（如果还没改）
python3 -c "
import json
path = '/mnt/Qwen3.5-9B-Instruct/config.json'
with open(path) as f: cfg = json.load(f)
cfg['torch_dtype'] = 'float16'
if 'bf16' in cfg: cfg['bf16'] = False
with open(path, 'w') as f: json.dump(cfg, f, indent=2)
print('done')
"

# 写完 config.json 后，启动服务
cd /usr/local/Ascend/mindie/latest/mindie-service/bin
./mindieservice_daemon
```

## 测试

```bash
# 9B
curl -X POST http://localhost:1025/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen35-9b",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 64,
    "stream": false
  }'

# 2B
curl -X POST http://localhost:1025/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen35-2b",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 64,
    "stream": false
  }'
```

## 快速参考

| 模型 | FP16 大小 | 最小 TP | 单张 300I Duo | 显存占用 |
|------|----------|---------|---------------|---------|
| Qwen3.5-2B | ~4 GB | 1 | 可跑 2 个实例 | ~3 GB/芯片 |
| Qwen3.5-9B | ~18 GB | 2 | 刚好 1 个实例 | ~10-15 GB/芯片 |
| Qwen3.5-32B | ~64 GB | 4 | 需 2 张卡 | ~20-35 GB/芯片 |
| Qwen3.5-72B | ~144 GB | 8 | 需 4 张卡 | ~20-35 GB/芯片 |
