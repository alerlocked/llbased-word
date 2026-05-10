# VLM 部署 Checklist — MinerU2.5-Pro-1.2B on Atlas 300I Duo

> 明天去机房操作的完整步骤。按顺序执行，每步确认 OK 再往下走。

## 基本信息

| 项目 | 值 |
|------|-----|
| 模型 | MinerU2.5-Pro-2604-1.2B (Qwen2VL 架构，文档版面检测微调) |
| 推理引擎 | MindIE 2.2 RC1 |
| 芯片 | NPU chips 0-1 (physical card 0) |
| 端口 | 1040 (服务) / 1041 (管理) / 1042 (监控) |
| 服务器 IP | 192.168.13.153 |
| Docker 镜像 | `swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:2.2.RC1-300I-Duo-py311-openeuler24.03-lts` |
| 模型权重路径 | `/home/data/MinerU2.5-Pro-2604-1.2B/` |
| 部署脚本 | `/root/mindie-deploy/run-mineru-vlm.sh` |

---

## 前置条件确认

在操作之前先确认以下内容：

### 1. 网络连通

```bash
# 在麒麟笔记本上执行
ping 192.168.13.153
```

- [ ] ping 通 → 继续
- [ ] ping 不通 → 检查网线、IP 配置（麒麟应为 192.168.13.101/24 同网段）

### 2. SSH 能登录服务器

```bash
ssh root@192.168.13.153
```

- [ ] 能登录 → 继续
- [ ] 不能登录 → 检查 SSH 服务、密码

### 3. NPU 驱动正常

```bash
# 在 300I Duo 服务器上执行
npu-smi info
```

应该看到 4 张卡、8 个芯片，驱动版本 >= 24.1。

- [ ] NPU 正常 → 继续
- [ ] 异常 → 联系管理员检查驱动

### 4. 模型文件存在

```bash
ls -la /home/data/MinerU2.5-Pro-2604-1.2B/config.json
ls -la /home/data/MinerU2.5-Pro-2604-1.2B/*.safetensors | wc -l
```

应有 `config.json` 和多个 safetensors 文件（总共约 2.5GB）。

- [ ] 文件存在 → 继续
- [ ] 不存在 → 从麒麟笔记本传输：
  ```bash
  scp -r ~/models/MinerU2.5-Pro-2604-1.2B root@192.168.13.153:/home/data/
  ```

### 5. Docker 镜像已加载

```bash
docker images | grep mindie
```

应看到 `mindie:2.2.RC1-300I-Duo-py311-openeuler24.03-lts`。

- [ ] 镜像存在 → 继续
- [ ] 不存在 → 加载镜像：
  ```bash
  docker load -i ~/mindie-image.tar    # 约 18GB，需要几分钟
  ```

---

## 核心操作步骤

### Step 1: 修复模型 dtype（300I Duo 不支持 BF16）

**这是上次失败的原因之一。** 模型原始 config.json 里 dtype 是 `bfloat16`，300I Duo 不支持 BF16，必须改成 `float16`。

```bash
# 在服务器上执行
python3 -c "
import json
path = '/home/data/MinerU2.5-Pro-2604-1.2B/config.json'
with open(path) as f:
    cfg = json.load(f)

changed = False

# Root-level
if cfg.get('dtype') == 'bfloat16':
    cfg['dtype'] = 'float16'
    changed = True
if cfg.get('torch_dtype') not in ('float16', None):
    cfg['torch_dtype'] = 'float16'
    changed = True
if cfg.get('bf16'):
    cfg['bf16'] = False
    changed = True

# text_config
tc = cfg.get('text_config', {})
if tc.get('dtype') == 'bfloat16':
    tc['dtype'] = 'float16'
    changed = True

# vision_config
vc = cfg.get('vision_config', {})
if vc.get('dtype') == 'bfloat16':
    vc['dtype'] = 'float16'
    changed = True

if changed:
    with open(path, 'w') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    print('DONE: dtype -> float16')
else:
    print('OK: dtype already correct')
"
```

验证：
```bash
python3 -c "import json; cfg=json.load(open('/home/data/MinerU2.5-Pro-2604-1.2B/config.json')); print('dtype:', cfg.get('dtype'), 'torch_dtype:', cfg.get('torch_dtype'))"
```

应输出 `dtype: float16 torch_dtype: float16`。

- [ ] dtype 已修复

> **注意**：`run-mineru-vlm.sh` 脚本也会自动执行这一步，但建议手动确认一次，确保万无一失。

### Step 2: 开放防火墙端口 1040

**这是上次失败的主要原因。** MindIE 容器用 `--net=host` 绑定 `0.0.0.0:1040`，但服务器 firewalld 默认拦截外部访问。从麒麟笔记本 curl 不通 1040 端口，后端连接 VLM 失败。

```bash
# 在 300I Duo 服务器上执行

# 先看防火墙状态
firewall-cmd --state

# 如果显示 "running"，必须开放端口
firewall-cmd --add-port=1040/tcp --permanent
firewall-cmd --add-port=1041/tcp --permanent   # 管理端口（可选）
firewall-cmd --add-port=1042/tcp --permanent   # 监控端口（可选）
firewall-cmd --reload

# 验证
firewall-cmd --list-ports
```

应看到 `1040/tcp`。

- [ ] 端口已开放

**如果 firewalld 没有运行（显示 not running），跳过这步。**

**如果嫌麻烦，可以临时关闭防火墙（仅测试用）：**
```bash
systemctl stop firewalld
```

### Step 3: 确认 LLM 容器在跑（避免芯片冲突）

VLM 用 chips 0-1，LLM (Qwen3-30B-A3B) 用 chips 4-7。先确认 LLM 容器状态：

```bash
docker ps | grep mindie
```

- 如果看到 `mindie-qwen3-30b-a3b` → LLM 在跑，OK
- 如果没有 LLM 容器 → 先启动 LLM（可选，明天也可以先只测 VLM）
- 如果有容器用了 chips 0-1 → 冲突，需要停止

```bash
# 启动 LLM（如果需要）
cd /root/mindie-deploy
./run-qwen3-30b-a3b.sh
./run-qwen3-30b-a3b.sh logs    # 等待 "Daemon start success!"
```

- [ ] 芯片无冲突

### Step 4: 启动 VLM 容器

```bash
cd /root/mindie-deploy
chmod +x run-mineru-vlm.sh

# 启动
./run-mineru-vlm.sh
```

脚本会自动执行：
1. 清理旧容器
2. 修复 dtype
3. 创建新容器（映射 chips 0-1，端口 1040-1042）
4. Patch MindIE 配置
5. 后台启动 daemon

- [ ] 容器已创建

### Step 5: 等待模型加载

```bash
./run-mineru-vlm.sh logs
```

等待出现 `Daemon start success!`。模型约 2.5GB，通常 2-3 分钟加载完成。

加载过程中的正常日志：
```
=== Daemon start at ... ===
--- Sourcing environments ---
--- Checking model files ---
--- Starting daemon ---
[WARNING] ...    ← 一些 warning 是正常的
Daemon start success!   ← 看到这行就是成功了
```

- [ ] `Daemon start success!` 出现

**如果等了 5 分钟还没出现**，看日志尾部是否有报错：
```bash
./run-mineru-vlm.sh logs | tail -50
```

常见报错及处理：
- `worldSize mismatch` → config 里 worldSize 与芯片数不匹配，脚本已设为 2，确认 chips 0-1 可用
- `type must be boolean, but is null` → config 缺少必填字段，确认用的是最新版脚本（patch 模式）
- `Out of memory` / `NPU memory insufficient` → 芯片被其他容器占用，检查 `npu-smi info`
- `Failed to load model` → 模型文件损坏，重新传输

### Step 6: 本机测试 VLM 接口

```bash
# 在服务器上执行
./run-mineru-vlm.sh test
```

或手动测试：

```bash
# 检查模型列表
curl -s http://localhost:1040/v1/models

# 应返回类似：
# {"object":"list","data":[{"id":"MinerU2.5-Pro-2604-1.2B",...}]}
```

```bash
# 测试推理
curl -s --max-time 60 -X POST http://localhost:1040/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "MinerU2.5-Pro-2604-1.2B",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 32,
    "stream": false
  }'
```

应返回 JSON 格式的 chat completion 结果。

- [ ] `/v1/models` 返回模型列表
- [ ] 推理返回正常结果

### Step 7: 从麒麟笔记本测试连通性

**回到麒麟笔记本执行：**

```bash
# 测试 VLM 端口
curl -s --max-time 5 http://192.168.13.153:1040/v1/models
```

- [ ] 麒麟能访问到 VLM 接口 → 继续下一步

**如果连接超时或拒绝：**
1. 确认服务器上 `curl localhost:1040/v1/models` 能通（Step 6 已验证）
2. 确认防火墙端口 1040 已开放（Step 2）
3. 确认两台机器在同一网段：`ip addr` 检查

### Step 8: 重启后端，验证 VLM 集成

```bash
# 在麒麟笔记本上
cd ~/project/localknowledgebase-word

# 停止旧后端（如果在跑）
pkill -f "python main.py" 2>/dev/null || true

# 启动后端
cd backend
conda activate craftdoc
python main.py
```

启动日志应显示：
```
==================================================
  Model Server Connectivity Check
==================================================
  LLM  (http://192.168.13.153:1028/v1): OK
  VLM  (http://192.168.13.153:1040/v1): OK
==================================================
```

- [ ] LLM 显示 OK
- [ ] VLM 显示 OK

**如果 VLM 显示 FAILED**：
- 但 Step 7 从麒麟 curl 通了 → 可能是后端代码还在用旧配置，检查 `.env` 中 `MINERU_VL_SERVER=http://192.168.13.153:1040/v1`
- curl 也不通 → 回到 Step 2 检查防火墙

### Step 9: 端到端 PDF 解析测试

在后端运行的情况下，上传一个 PDF 测试解析：

1. 浏览器打开 `http://192.168.13.101:3000`
2. 上传一个 PDF 文件
3. 等待解析完成

或用 curl 测试：

```bash
# 找一个测试 PDF
curl -X POST http://localhost:8000/api/process/upload \
  -F "file=@test.pdf" \
  -F "material_id=test-vlm"
```

- [ ] PDF 解析成功，返回 Markdown 内容

---

## 全部完成后的确认清单

| # | 项目 | 状态 |
|---|------|------|
| 1 | 模型 dtype 已改为 float16 | ☐ |
| 2 | 防火墙 1040 端口已开放 | ☐ |
| 3 | VLM 容器运行中 | ☐ |
| 4 | `Daemon start success!` 出现 | ☐ |
| 5 | 服务器 `curl localhost:1040/v1/models` OK | ☐ |
| 6 | 麒麟 `curl 192.168.13.153:1040/v1/models` OK | ☐ |
| 7 | 后端启动 LLM + VLM 均 OK | ☐ |
| 8 | PDF 解析测试通过 | ☐ |

---

## 上次失败原因回顾

| 问题 | 原因 | 本次应对 |
|------|------|----------|
| 麒麟 curl 不通 1040 | 服务器防火墙拦截端口 | Step 2: 显式开放 1040 |
| MindIE 启动报 dtype 错误 | 模型 config.json 里是 bfloat16，300I Duo 不支持 | Step 1: 手动改成 float16 |
| 后端启动崩溃 | VLService 在 import 时就连 VLM，连不上就崩 | 已改为 lazy init（首次 OCR 才连接） |

---

## 快速命令参考

```bash
# === 在服务器上 (192.168.13.153) ===
cd /root/mindie-deploy

./run-mineru-vlm.sh          # 启动
./run-mineru-vlm.sh logs     # 看日志
./run-mineru-vlm.sh test     # 测试接口
./run-mineru-vlm.sh stop     # 停止

# 防火墙
firewall-cmd --list-ports                  # 查看已开放端口
firewall-cmd --add-port=1040/tcp --permanent && firewall-cmd --reload  # 开端口

# Docker
docker ps                                   # 看运行中的容器
docker logs mindie-mineru-vlm              # 看容器日志
docker exec mindie-mineru-vlm cat /tmp/mindie.log  # 看 daemon 日志

# === 在麒麟笔记本上 (192.168.13.101) ===
curl -s http://192.168.13.153:1040/v1/models  # 测试 VLM 连通
curl -s http://192.168.13.153:1028/v1/models  # 测试 LLM 连通

# 后端
cd ~/project/localknowledgebase-word/backend
conda activate craftdoc
python main.py
```

---

## 如果需要回滚

如果 VLM 部署失败，不影响 LLM 和其他功能：

```bash
# 停止 VLM 容器
cd /root/mindie-deploy
./run-mineru-vlm.sh stop

# 后端仍可正常运行，PDF 解析会失败但其他功能不受影响
```
