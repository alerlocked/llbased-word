# 需求对齐卡：前端 Content-Type 接管（解耦系统 mimetypes）

## 背景 / 根因（本会话已确认）
现场 win10 便携版在某台 Windows 机器上前端响应 `index.html` 的 `Content-Type: text/utf-8`，浏览器拒绝渲染 → 页面打不开；另一台注册表干净的机器正常。
- 根因：前端静态服务（`FileResponse` / `StaticFiles`）没传 `media_type`，委托给 `mimetypes.guess_type`；Python `mimetypes` 在 Windows 读注册表 `HKEY_CLASSES_ROOT\.html`，那台机器该值被污染成 `text/utf-8`。
- 验证根因（那台机器）：`python -c "import mimetypes; print(mimetypes.guess_type('index.html'))"` 或 `reg query "HKEY_CLASSES_ROOT\.html" /v "Content Type"`

## 目标
前端响应的 Content-Type 由代码显式指定（FileResponse `media_type` + 自建扩展名映射），不再委托系统 `mimetypes`，与 Windows 注册表状态彻底解耦。任意机器表现一致。

## 成功标准（可观察）
1. 主项目开发机 `build frontend` 后：
   - `curl -I http://localhost:8000/` → `Content-Type: text/html; charset=utf-8`
   - `/assets/*.js` → `application/javascript; charset=utf-8`
   - SPA 子路由（如 `/projects/xxx`）→ fallback 到 index.html，200
   - `/health`、`/api/*` 不被 catch-all 拦截
2. 移植 win10 重新打包后，现场那台注册表脏的机器页面能正常打开。

## 边界
- 做：主项目 `backend/main.py` 前端服务段（root + spa_fallback + `_media_type` 映射）；开发机验证；mirror 到 win10 `backend/main.py` + `dist/工艺文件系统` 工作目录同步；win10 重新打包便携版。
- 不做：禁用 `mimetypes.add_type` 全局补丁（已否决，污染全局 mimetypes 库）。
- 不做：不动后端业务逻辑、API 路由、其他中间件。
- 不做：本次不改 kylin（跑 Linux 麒麟，读 `/etc/mime.types` 不读注册表，免疫）。

## 模糊点（已清零）
- **主项目 `root()` 行为变化**：当前无条件返 API info；改成照搬 win10 条件分支（`FRONTEND_DIST.exists() ? FileResponse(index.html) : API info`）。开发模式无 dist → 仍返 API info，不破坏开发体验。✅ 澄清（自洽，结构对齐 win10）
- **映射表覆盖范围**：`.html .htm .js .mjs .css .json .svg .png .jpg .ico .woff .woff2 .map .wasm`，未知扩展回退 `application/octet-stream`。✅ 接受
- **spa_fallback 注册位置**：所有 `@app` 路由（含 `/`、`/health`、`/api/*`）之后，确保 catch-all 不拦截业务路由。✅ 澄清

## 下游
→ `PLAN-content-type-fix.md`（同 slug）
