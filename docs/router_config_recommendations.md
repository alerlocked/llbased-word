# Claude Code Router 配置建议

## 1. Token 超限问题（262317 > 262144）

**原因**：`longContext` 使用的 Kimi `kimi-k2-turbo-preview` 单次请求上限为 **262,144 tokens**，当前对话上下文略超即报错。

**可做的配置调整**（在 `config.json` 的 `Router` 中）：

| 项 | 当前值 | 建议 | 说明 |
|----|--------|------|------|
| `longContextThreshold` | 60000 | **80000** 或 **100000** | 提高阈值可减少“过早”切到 Kimi，但会提高 default 模型超限风险；若希望更早用长上下文可保持 60000 或降到 50000。 |
| `longContext` | kimi,kimi-k2-turbo-preview | 视测试结果可选 **qwen,qwen3-max** | Qwen3-max 通常为 128k 上下文，适合 60k–128k 的“长上下文”；超过 128k 再考虑 Kimi（注意 Kimi 上限 262k，接近时需新开会话）。 |

**重要**：路由本身一般不会自动截断上下文。当总 token 接近 260k 时，建议：
- 新开对话，或
- 减少单次附带的文件/代码量。

若后续路由支持“长上下文模型最大 token 上限”（例如 250000），可设为该值以避免刚好超过 262144。

---

## 2. 建议的 Router 配置片段（可替换整段 Router）

在保证各模型连通且性能满意的前提下，可试用下面组合（复制到 `config.json` 的 `"Router"` 中）：

```json
"Router": {
  "default": "zhipu,glm-5",
  "background": "qwen,qwen3-max",
  "think": "deepseek,deepseek-chat",
  "longContext": "qwen,qwen3-max",
  "longContextThreshold": 80000,
  "webSearch": "qwen,qwen3-max",
  "image": "qwen,qwen-vl-max"
}
```

- **longContext 改为 qwen**：用 128k 上下文承担“长上下文”，避免频繁触及 Kimi 的 262k 上限；超 128k 时仍需新开会话或减量。
- **longContextThreshold 提高到 80000**：只有上下文超过 8 万 token 才走长上下文模型，减轻误判。

若测试后 Kimi 延迟更低且你多数对话在 200k 以内，可改回：

```json
"longContext": "kimi,kimi-k2-turbo-preview",
"longContextThreshold": 60000
```

并注意在对话很长时主动新开或精简上下文。

---

## 3. 配置文件位置

- Windows：`%USERPROFILE%\.claude-code-router\config.json`  
- 例如：`c:\Users\alerl\.claude-code-router\config.json`

修改后需重启 Claude Code Router 或重新连接后再测。

---

## 4. 实测结果与推荐组合（基于一次本地测试）

| Provider  | 模型                    | 状态 | 延迟(ms) |
|-----------|-------------------------|------|----------|
| zhipu     | glm-4.7                 | OK   | ~824     |
| zhipu     | glm-5                   | OK   | ~1115    |
| qwen      | qwen3-coder-plus        | OK   | ~2163    |
| qwen      | qwen3-max               | OK   | ~2299    |
| qwen      | qwen-vl-max             | OK   | ~2769    |
| kimi      | kimi2                   | FAIL | 404 模型未找到/无权限 |
| kimi      | kimi-k2-turbo-preview   | OK   | ~3040    |
| deepseek  | deepseek-chat           | OK   | ~1178    |
| deepseek  | deepseek-reasoner       | OK   | ~1193    |

**性能排序（按延迟）**：zhipu(glm-4.7) &lt; deepseek(deepseek-chat) &lt; qwen &lt; kimi。

**建议**：
- **default**：保持 `zhipu,glm-5`，或改为 `zhipu,glm-4.7` 追求更低延迟。
- **longContext**：若常遇 262k 超限，改为 `qwen,qwen3-max`，并设 `longContextThreshold: 80000`。
- **think**：保持 `deepseek,deepseek-chat` 即可。
- Kimi 的 **kimi2** 若不可用，可在 config 的 `Providers[].models` 中移除 `kimi2`，仅保留 `kimi-k2-turbo-preview`，避免路由或测试报错。
