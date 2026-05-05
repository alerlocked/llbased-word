# 麒麟系统部署方案

> 目标：将工艺文件辅助编辑系统部署到麒麟 V10 ARM 服务器（离线环境）

## 架构总览

```
┌──────────────────────────────────────────────────┐
│              麒麟 V10 ARM 服务器                   │
│                                                    │
│  nginx (80/443)                                    │
│  ├── / → 前端静态文件 (dist/)                      │
│  └── /api/ → FastAPI 后端 (8000)                   │
│                 ├── SQLite (本地)                   │
│                 ├── ChromaDB (向量)                 │
│                 ├── LangChain                      │
│                 ├── → MindIE API (1025)  [NPU]      │
│                 └── → BGE Service (8086) [NPU]      │
│                                                    │
│  Docker: MindIE 容器 (Qwen3.5 推理)                │
│  Docker: mis-tei 容器 (BGE Embedding/Rerank)       │
└──────────────────────────────────────────────────┘
         │
         │ (可选) HTTP
         ▼
┌──────────────────────────┐
│  x86 服务器: MinerU PDF  │
│  POST /parse → HTML/JSON │
└──────────────────────────┘
```

## 兼容性速查

| 组件 | 状态 | 说明 |
|------|------|------|
| Python 3.11 | 可用 | 源码编译，**不要用 3.13** |
| FastAPI + SQLite | 可用 | 纯 Python，无平台依赖 |
| React 静态文件 | 可用 | 开发机构建，nginx 托管 |
| Docker | 可用 | 麒麟适配版或二进制安装 |
| nginx | 可用 | yum install 或源码编译 |
| ChromaDB | 基本可用 | 需 gcc + Rust 编译 |
| MindIE (Qwen) | 可用 | 300I Duo 专用镜像 |
| BGE Embedding | 可用 | mis-tei 镜像，NPU 推理 |
| **MinerU** | **不可用** | pypdfium2 无 ARM 预编译库 |

## 分步部署

### Phase 0: 在联网机器上准备离线包

```bash
# === Python 3.11 源码 ===
wget https://www.python.org/ftp/python/3.11.9/Python-3.11.9.tgz

# === Node.js arm64 二进制（可选，如果不在服务器构建前端） ===
wget https://nodejs.org/dist/v20.18.0/node-v20.18.0-linux-arm64.tar.xz

# === Python 依赖离线包 ===
# 在同架构 (aarch64 + 麒麟) 联网机器上执行：
pip download -r backend/requirements.txt -d ./offline_py_pkgs
tar czvf offline_py_pkgs.tar.gz offline_py_pkgs/

# === 前端构建产物 ===
cd frontend && npm install && npm run build
# 将 dist/ 目录打包
tar czvf frontend_dist.tar.gz dist/

# === Docker 镜像 ===
docker save mindie:2.3.0-300I-Duo | gzip > mindie-2.3.0.tar.gz
# (mis-tei 镜像同理)

# === 所有文件列表 ===
ls -lh offline_bundle/
# Python-3.11.9.tgz
# offline_py_pkgs.tar.gz
# frontend_dist.tar.gz
# mindie-2.3.0.tar.gz
# nginx-1.24.0.tar.gz (备选)
```

### Phase 1: 基础环境

```bash
# ---- 1.1 编译工具链 ----
sudo yum install -y gcc gcc-c++ make cmake \
  openssl-devel bzip2-devel libffi-devel \
  zlib-devel readline-devel sqlite-devel xz-devel \
  pcre-devel zlib-devel

# Rust (ChromaDB hnswlib 编译需要)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# ---- 1.2 Python 3.11 ----
tar xzf Python-3.11.9.tgz
cd Python-3.11.9
./configure --prefix=/usr/local/python3.11 --enable-optimizations --with-ensurepip=install
make -j$(nproc)
sudo make altinstall

# 创建虚拟环境
/usr/local/python3.11/bin/python3.11 -m venv /opt/app/py311
source /opt/app/py311/bin/activate

# 验证
python -c "import sqlite3; print('SQLite:', sqlite3.sqlite_version)"

# ---- 1.3 Docker ----
# 方式一：麒麟自带
sudo yum install -y docker
sudo systemctl start docker && sudo systemctl enable docker

# 方式二：离线二进制（如果没有 yum 源）
tar xzvf docker-27.3.1.tgz
sudo cp docker/* /usr/bin/
# 创建 systemd service (见附录)

# ---- 1.4 nginx ----
sudo yum install -y nginx
# 或离线编译
tar xzf nginx-1.24.0.tar.gz && cd nginx-1.24.0
./configure --prefix=/usr/local/nginx --with-http_ssl_module --with-http_gzip_static_module
make -j$(nproc) && sudo make install
```

### Phase 2: Python 依赖

```bash
# 离线安装
source /opt/app/py311/bin/activate
tar xzf offline_py_pkgs.tar.gz
pip install --no-index --find-links=./offline_py_pkgs -r requirements.txt
```

### Phase 3: 前端部署

```bash
sudo mkdir -p /opt/app/frontend
tar xzf frontend_dist.tar.gz -C /opt/app/frontend/
```

### Phase 4: 后端部署

```bash
# 拷贝后端代码
sudo mkdir -p /opt/app/backend
cp -r backend/* /opt/app/backend/

# 修改配置 → 指向本地 MindIE
# vim /opt/app/backend/app/config.py
# LLM_BASE_URL = "http://localhost:1025/v1"
# LLM_MODEL_NAME = "qwen35"
```

### Phase 5: MindIE 服务

```bash
# 加载镜像
docker load -i mindie-2.3.0.tar.gz

# 启动容器（参考 step3_start_service.sh）
bash step3_start_service.sh
```

### Phase 6: BGE Embedding 服务

```bash
# 加载 mis-tei 镜像
docker load -i mis-tei-6.0.0-300I-Duo.tar.gz

# 启动 BGE-M3 Embedding（占用 1 颗 NPU）
docker run -u root \
  -e ASCEND_VISIBLE_DEVICES=86 \
  -itd --name=bge-embed --net=host \
  --privileged=true \
  -v /opt/models/BAAI:/home/HwHiAiUser/model \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver \
  --entrypoint /home/HwHiAiUser/start.sh \
  mis-tei:6.0.0-300I-Duo-aarch64 \
  BAAI/bge-m3 127.0.0.1 8086

# 测试
curl http://127.0.0.1:8086/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": "测试", "model": "bge-m3"}'
```

### Phase 7: nginx 配置

```bash
sudo tee /etc/nginx/conf.d/app.conf << 'EOF'
server {
    listen 80;
    server_name _;

    # 前端
    location / {
        root /opt/app/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # SSE 流式响应
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
EOF

sudo nginx -t && sudo systemctl reload nginx
```

### Phase 8: 启动后端

```bash
source /opt/app/py311/bin/activate
cd /opt/app/backend
nohup python main.py > /var/log/app.log 2>&1 &

# 或用 systemd 管理（见附录）
```

## NPU 资源分配（44 张 300I Duo = 88 芯片）

| 用途 | 芯片数 | Device IDs | 说明 |
|------|--------|------------|------|
| Qwen3.5-32B | 4 | 0-3 | 主推理，TP=4 |
| Qwen3.5-9B | 2 × 10 | 4-23 | 高并发，10 个实例 |
| BGE-M3 Embedding | 1 | 24 | 向量化 |
| BGE-Rerank | 1 | 25 | 重排序 |
| 预留 | 62 | 26-87 | 后续扩展 |

## 关键风险

### 1. MinerU 在 ARM 上不可用
- **原因**：pypdfium2 无 ARM 预编译库，detectron2 不支持 ARM
- **方案 A**：x86 服务器跑 MinerU，麒麟通过 HTTP API 调用
- **方案 B**：ARM 上用 PyMuPDF 替代，牺牲 OCR 精度
- **建议**：PMF 阶段先用方案 A（一台 x86 机器做 PDF 解析）

### 2. Python 版本必须降级
- 当前项目用 3.13，麒麟上只能用 3.11
- MindIE 也只支持到 3.11.4
- 需要验证所有依赖在 3.11 上的兼容性

### 3. KYSEC 安全模块拦截
- **现象**：Python 调用外部 HTTPS API 间歇性失败，`ssl.do_handshake()` 抛出 `PermissionError: [Errno 13] Permission denied`
- **原因**：KYSEC 的 fpro（文件保护）和 ppro（进程保护）会拦截 Python SSL 握手
- **curl 正常但 Python 不行**：KYSEC 对不同程序有不同策略
- **修复**：编辑 `/etc/kysec/kysec.conf`，将 `kysec_fpro = 1` 和 `kysec_ppro = 1` 改为 `0`，然后 `sudo reboot`
- **注意**：仅测试环境可关闭，生产环境需联系麒麟安全团队配置白名单

### 4. 离线部署
- 所有 pip 包需在 aarch64 + 麒麟同环境下载
- Docker 镜像需提前 load
- NPU 驱动需提前安装

## 附录

### systemd 服务文件

```ini
# /etc/systemd/system/craft-backend.service
[Unit]
Description=Craft Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/app/backend
ExecStart=/opt/app/py311/bin/python main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable craft-backend
sudo systemctl start craft-backend
```
