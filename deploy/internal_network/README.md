# 内网部署方案

## 部署概述

工艺文件辅助编辑系统支持完全离线的内网部署，适用于对数据安全要求较高的企业环境。

### 部署特性
- **完全离线**: 所有依赖包和模型文件都可本地部署
- **数据安全**: 100%本地存储，无外部网络请求
- **跨平台**: 支持Windows、Linux（包括麒麟系统）
- **灵活配置**: 可根据硬件资源调整配置

## 部署准备

### 硬件要求
- **CPU**: 4核以上
- **内存**: 8GB以上（推荐16GB）
- **磁盘空间**: 50GB以上（包含模型文件）
- **GPU**: 可选（用于加速模型推理）

### 软件要求
- **操作系统**: Windows 7+ / Linux / 麒麟系统
- **Python**: 3.10+
- **Node.js**: 16+
- **Redis**: 5.0+（可选，用于缓存）

### 离线包准备
```bash
# 创建离线依赖包（在有网络的环境中执行）
scripts/create_offline_package.sh

# 下载模型文件
scripts/download_models.sh
```

## 部署步骤

### 1. 准备环境
```bash
# 复制项目到目标服务器
scp -r craft-document-assistant user@server:/opt/

# 进入部署目录
cd /opt/craft-document-assistant/deploy/internal_network
```

### 2. 执行部署
```bash
# 赋予执行权限
chmod +x deploy.sh

# 执行部署脚本
./deploy.sh
```

### 3. 配置应用
```bash
# 配置API密钥
cp backend/.env.example backend/.env
# 编辑 backend/.env 文件

# 配置部署参数
# 编辑 backend/config/internal_network.json
```

### 4. 启动服务
```bash
# 启动所有服务
./start_all.sh

# 或分别启动
./start_backend.sh
./start_frontend.sh
```

## 目录结构

```
craft-document-assistant/
├── deploy/                     # 部署相关文件
│   └── internal_network/       # 内网部署方案
│       ├── deploy.sh          # 部署脚本
│       ├── README.md          # 部署说明
│       └── config/            # 部署配置模板
├── models/                    # AI模型文件
├── offline_deps/              # 离线依赖包
├── start_all.sh               # 启动脚本
├── start_backend.sh           # 后端启动脚本
└── start_frontend.sh          # 前端启动脚本
```

## 故障排除

### 常见问题
1. **磁盘空间不足**: 确保有足够空间存放模型文件（约20-40GB）
2. **内存不足**: 调整 `internal_network.json` 中的内存限制
3. **端口冲突**: 修改配置文件中的端口号
4. **依赖缺失**: 确保离线包完整或网络连接正常

### 日志查看
- **后端日志**: `backend/logs/`
- **前端日志**: 浏览器开发者工具
- **部署日志**: `deploy.log`

## 安全考虑

### 网络安全
- 默认只监听 localhost
- 如需外部访问，请配置反向代理和防火墙
- 建议使用HTTPS加密通信

### 数据安全
- 所有数据本地存储
- API密钥不要提交到版本控制
- 定期备份数据目录

## 性能优化

### GPU加速
```json
// backend/config/internal_network.json
{
  "use_gpu": true,
  "gpu_device": "cuda:0"
}
```

### 内存优化
```json
{
  "max_memory_mb": 8192,
  "enable_memory_monitoring": true
}
```

### 缓存配置
```json
{
  "redis_url": "redis://localhost:6379/0",
  "cache_enabled": true,
  "cache_ttl_minutes": 60
}
```

## 维护指南

### 更新应用
1. 停止当前服务
2. 更新代码文件
3. 重新运行部署脚本
4. 重启服务

### 备份恢复
- **备份**: 复制 `data/` 目录
- **恢复**: 将备份的 `data/` 目录覆盖到新部署中

### 监控
- CPU和内存使用情况
- 磁盘空间监控
- 服务健康检查端点: `/health`

---

**注意**: 此部署方案为简化版本，实际生产环境可能需要更复杂的配置和安全措施。