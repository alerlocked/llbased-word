#!/bin/bash
# ============================================================================
# 现场连接诊断 & 修复脚本
#
# 用法:
#   chmod +x fix-connection.sh
#   ./fix-connection.sh              # 诊断 + 自动修复
#   ./fix-connection.sh diag         # 只诊断，不修改
#   ./fix-connection.sh fix          # 只修复
# ============================================================================
set -e

SERVER_IP="${SERVER_IP:-192.168.13.153}"
MY_IP="$(ip addr show | grep 'inet ' | grep -v '127.0.0.1' | head -1 | awk '{print $2}' | cut -d/ -f1)"

echo "============================================================"
echo "  CraftDoc 连接诊断"
echo "  本机 IP: $MY_IP"
echo "  服务器 : $SERVER_IP"
echo "============================================================"

# ---- 1. 网络层 ----
echo ""
echo "=== Step 1: 网络连通性 ==="
if ping -c 2 -W 2 $SERVER_IP > /dev/null 2>&1; then
    echo "  [OK] ping $SERVER_IP 通了"
else
    echo "  [FAIL] ping $SERVER_IP 不通"
    echo "    检查: 网线是否插好, IP 是否在同一网段"
    echo "    本机 IP: $MY_IP (需要和 $SERVER_IP 在同一 /24 网段)"
    exit 1
fi

# ---- 2. 端口连通性 ----
check_port() {
    local host=$1 port=$2 name=$3
    if curl -s --max-time 3 http://${host}:${port}/v1/models > /dev/null 2>&1; then
        echo "  [OK] $name port $port 可访问"
        return 0
    else
        echo "  [FAIL] $name port $port 不可访问"
        return 1
    fi
}

echo ""
echo "=== Step 2: 模型服务端口 ==="
LLM_OK=true
VLM_OK=true
check_port $SERVER_IP 1028 "LLM (Qwen3-30B)" || LLM_OK=false
check_port $SERVER_IP 1040 "VLM (MinerU VLM)" || VLM_OK=false

# ---- 3. 如果端口不通，检查防火墙 ----
if [ "$LLM_OK" = "false" ] || [ "$VLM_OK" = "false" ]; then
    echo ""
    echo "=== Step 3: 检查服务器防火墙 ==="
    echo "  尝试 SSH 到 $SERVER_IP 检查防火墙状态..."

    FIREWALL_STATUS=$(ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@$SERVER_IP \
        "firewall-cmd --state 2>/dev/null || echo 'not-installed'" 2>/dev/null || echo "ssh-failed")

    if [ "$FIREWALL_STATUS" = "running" ]; then
        echo "  [!] 防火墙正在运行 (firewall-cmd --state = running)"
        echo "      这很可能就是端口不通的原因"

        if [ "${1:-diag}" != "diag" ]; then
            echo ""
            echo "  正在开放端口 1028 和 1040..."
            ssh -o StrictHostKeyChecking=no root@$SERVER_IP "
                firewall-cmd --add-port=1028/tcp --permanent
                firewall-cmd --add-port=1040/tcp --permanent
                firewall-cmd --reload
                echo 'Firewall rules added'
            "
            echo "  [OK] 防火墙规则已添加"

            # Re-check
            echo ""
            echo "  重新检查端口..."
            check_port $SERVER_IP 1028 "LLM (Qwen3-30B)" || true
            check_port $SERVER_IP 1040 "VLM (MinerU VLM)" || true
        else
            echo ""
            echo "  修复命令 (在服务器上执行):"
            echo "    ssh root@$SERVER_IP"
            echo "    firewall-cmd --add-port=1028/tcp --permanent"
            echo "    firewall-cmd --add-port=1040/tcp --permanent"
            echo "    firewall-cmd --reload"
            echo ""
            echo "  或者直接关闭防火墙 (测试用):"
            echo "    ssh root@$SERVER_IP 'systemctl stop firewalld'"
        fi
    elif [ "$FIREWALL_STATUS" = "not-installed" ]; then
        echo "  防火墙未安装。检查 iptables:"
        ssh -o StrictHostKeyChecking=no root@$SERVER_IP "iptables -L INPUT -n --line-numbers 2>/dev/null | head -20"
    elif [ "$FIREWALL_STATUS" = "ssh-failed" ]; then
        echo "  [FAIL] SSH 连接失败"
        echo "    检查: ssh root@$SERVER_IP 是否可以手动连接"
    else
        echo "  防火墙状态: $FIREWALL_STATUS (未运行)"
        echo "  端口不通可能是容器未启动，检查 docker:"
        echo "    ssh root@$SERVER_IP 'docker ps -a'"
    fi
fi

# ---- 4. 检查容器状态 ----
echo ""
echo "=== Step 4: 检查服务器容器状态 ==="
CONTAINERS=$(ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@$SERVER_IP \
    "docker ps -a --format '{{.Names}}\t{{.Status}}' | grep mindie" 2>/dev/null || echo "ssh-failed")

if [ "$CONTAINERS" = "ssh-failed" ]; then
    echo "  无法通过 SSH 检查容器"
else
    echo "$CONTAINERS" | while IFS=$'\t' read -r name status; do
        if echo "$status" | grep -q "Up"; then
            echo "  [OK] $name - $status"
        else
            echo "  [FAIL] $name - $status (需要重启)"
        fi
    done
fi

# ---- 5. 更新 .env ----
echo ""
echo "=== Step 5: 确认 .env 配置 ==="
ENV_FILE="$HOME/project/localknowledgebase-word/backend/.env"
if [ -f "$ENV_FILE" ]; then
    LLM_URL=$(grep "^DASHSCOPE_BASE_URL_COMPLEX=" "$ENV_FILE" | cut -d= -f2)
    VLM_URL=$(grep "^MINERU_VL_SERVER=" "$ENV_FILE" | cut -d= -f2)
    BACKEND=$(grep "^MINERU_BACKEND=" "$ENV_FILE" | cut -d= -f2)
    FALLBACK=$(grep "^VL_SERVICE_FALLBACK_TO_QWEN=" "$ENV_FILE" | cut -d= -f2)

    echo "  LLM URL    : $LLM_URL"
    echo "  VLM URL    : $VLM_URL"
    echo "  MINERU_BACKEND : ${BACKEND:-transformers}"
    echo "  FALLBACK   : ${FALLBACK:-true}"

    if [ -z "$BACKEND" ] || [ "$BACKEND" = "transformers" ]; then
        echo ""
        echo "  [!] MINERU_BACKEND 未设置或为 transformers (CPU 模式, 太慢)"
        echo "      应改为: MINERU_BACKEND=http-client"
    fi
    if [ -z "$FALLBACK" ] || [ "$FALLBACK" = "true" ]; then
        echo ""
        echo "  [!] VL_SERVICE_FALLBACK_TO_QWEN=true (会尝试连云端, 无网环境应关闭)"
        echo "      应改为: VL_SERVICE_FALLBACK_TO_QWEN=false"
    fi
else
    echo "  [FAIL] .env 文件不存在: $ENV_FILE"
fi

# ---- Summary ----
echo ""
echo "============================================================"
echo "  诊断完成"
if [ "$LLM_OK" = "true" ] && [ "$VLM_OK" = "true" ]; then
    echo "  结果: 全部正常, 可以启动后端"
    echo "  执行: cd ~/project/localknowledgebase-word && ./start-all.sh"
else
    echo "  结果: 存在连接问题, 按上述提示修复"
fi
echo "============================================================"
