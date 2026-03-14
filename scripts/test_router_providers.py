#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code Router 各 Provider 连通性与延迟测试脚本。

用法:
  python scripts/test_router_providers.py [--config PATH]
  # 不传 --config 时默认读取 %USERPROFILE%\\.claude-code-router\\config.json

会请求各 Provider 的 chat/completions，统计成功/失败与耗时，并给出 Router 组合建议。
不写入、不打印 API Key；仅从本地 config 读取。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from urllib.request import Request, urlopen, build_opener, ProxyHandler, install_opener
from urllib.error import URLError, HTTPError

# 默认 config 路径（Windows）
DEFAULT_CONFIG_PATH = os.path.join(
    os.environ.get("USERPROFILE", os.path.expanduser("~")),
    ".claude-code-router",
    "config.json",
)


def load_config(path: str) -> dict:
    """从本地文件加载 config，不暴露 key。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_request(
    url: str,
    api_key: str,
    model: str,
    proxy_url: str | None,
    body: dict,
) -> Request:
    """构建 POST Request，支持 proxy 通过环境变量生效（脚本内不直接改 proxy）。"""
    req = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    return req


def get_chat_completions_url(provider: dict, model: str) -> str:
    """根据 provider 的 api_base_url 得到 chat completions 完整 URL。"""
    base = provider["api_base_url"].rstrip("/")
    # qwen/dashscope：base 已是完整 path
    if "dashscope.aliyuncs.com" in base:
        return base if "chat/completions" in base else f"{base}"
    # deepseek：官方为 https://api.deepseek.com/chat/completions
    if "deepseek.com" in base:
        return base if "chat/completions" in base else f"{base}/v1/chat/completions"
    # kimi：https://api.moonshot.cn/v1/chat/completions
    if "moonshot.cn" in base:
        return base if "chat/completions" in base else f"{base}/v1/chat/completions"
    # zhipu：https://open.bigmodel.cn/api/paas/v4 -> .../v4/chat/completions
    if "bigmodel.cn" in base:
        return f"{base}/chat/completions"
    if "/v1" in base:
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def test_provider(
    provider: dict,
    proxy_url: str | None,
    timeout: int = 30,
) -> list[dict]:
    """
    对单个 provider 下的每个 model 发一次最小 chat 请求，返回每条结果。
    每条: { "provider", "model", "ok", "status_code", "latency_ms", "error" }
    """
    api_key = provider.get("api_key") or ""
    if not api_key:
        return [
            {
                "provider": provider.get("name", "?"),
                "model": m,
                "ok": False,
                "status_code": None,
                "latency_ms": None,
                "error": "no api_key",
            }
            for m in provider.get("models", [])
        ]

    results = []
    for model in provider.get("models", []):
        url = get_chat_completions_url(provider, model)
        body = {
            "model": model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 10,
        }
        req = build_request(url, api_key, model, proxy_url, body)
        t0 = time.perf_counter()
        ok = False
        status_code = None
        err_msg = None
        try:
            # 若需走 proxy，请设置环境变量 HTTP_PROXY/HTTPS_PROXY 后运行本脚本
            resp = urlopen(req, timeout=timeout)
            status_code = resp.getcode()
            _ = resp.read()
            ok = 200 <= status_code < 300
        except HTTPError as e:
            status_code = e.code
            try:
                body_err = e.read().decode("utf-8")
                err_msg = body_err[:200] if body_err else str(e.reason)
            except Exception:
                err_msg = str(e.reason)
        except URLError as e:
            err_msg = str(e.reason)
        except Exception as e:
            err_msg = str(e)
        latency_ms = round((time.perf_counter() - t0) * 1000)

        results.append({
            "provider": provider.get("name", "?"),
            "model": model,
            "ok": ok,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "error": err_msg,
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="测试 Claude Code Router 各 Provider 连通性与延迟")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="config.json 路径（默认: 用户目录 .claude-code-router/config.json）",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="单次请求超时秒数",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.config):
        print(f"未找到配置文件: {args.config}", file=sys.stderr)
        sys.exit(1)

    config = load_config(args.config)
    providers = config.get("Providers") or []
    proxy_url = config.get("PROXY_URL") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")

    # 使用 config 或环境变量中的代理（使 urlopen 走代理）
    if proxy_url:
        print(f"使用代理: {proxy_url}\n")
        opener = build_opener(ProxyHandler({"http": proxy_url, "https": proxy_url}))
        install_opener(opener)
    else:
        print("未设置代理；若需代理请配置 config 的 PROXY_URL 或环境变量 HTTPS_PROXY。\n")

    all_results: list[dict] = []
    for prov in providers:
        all_results.extend(
            test_provider(prov, proxy_url, timeout=args.timeout)
        )

    # 打印表格
    print("Provider | Model                    | 状态   | 状态码 | 延迟(ms)")
    print("-" * 70)
    for r in all_results:
        status = "OK" if r["ok"] else "FAIL"
        code = r["status_code"] or "-"
        lat = r["latency_ms"] if r["latency_ms"] is not None else "-"
        err = f"  # {r['error'][:50]}..." if r.get("error") and len(r.get("error", "")) > 50 else (f"  # {r['error']}" if r.get("error") else "")
        print(f"{r['provider']:8} | {r['model']:24} | {status:6} | {code!s:6} | {lat!s:8}{err}")
    print()

    # 汇总与建议
    ok_list = [r for r in all_results if r["ok"]]
    fail_list = [r for r in all_results if not r["ok"]]
    if fail_list:
        print("失败项:")
        for r in fail_list:
            print(f"  - {r['provider']}/{r['model']}: {r.get('error', 'unknown')}")
        print()

    if not ok_list:
        print("无可用模型，请检查网络、代理与 API Key。")
        sys.exit(2)

    # 按 provider 取各模型最低延迟
    by_provider: dict[str, list[dict]] = {}
    for r in ok_list:
        by_provider.setdefault(r["provider"], []).append(r)
    best_per_provider = {}
    for prov, rows in by_provider.items():
        best = min(rows, key=lambda x: x["latency_ms"] or 999999)
        best_per_provider[prov] = best

    print("各 Provider 推荐模型（按延迟）:")
    for prov, r in sorted(best_per_provider.items(), key=lambda x: x[1]["latency_ms"] or 0):
        print(f"  {prov}: {r['model']}  (~{r['latency_ms']} ms)")
    print()

    # 给出 Router 建议
    router = config.get("Router") or {}
    print("当前 Router 配置:")
    for k, v in router.items():
        print(f"  {k}: {v}")
    print()
    print("建议（在 token 超限时）:")
    print("  1. 将 longContext 改为 qwen,qwen3-max，longContextThreshold 设为 80000；")
    print("  2. 或保持 longContext 为 kimi，在对话很长时新开会话或减少附带内容。")
    print("  详细说明见: docs/router_config_recommendations.md")
    sys.exit(0 if not fail_list else 1)


if __name__ == "__main__":
    main()
