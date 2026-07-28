# PLAN: 前端 Content-Type 接管（解耦系统 mimetypes）

> seal 后不可变。详细 plan 见 `~/.claude/plans/curried-imagining-seal.md`。进度记 DEV-LOG / git。

## 改动清单

| 文件 | 改什么 |
|------|--------|
| 主项目 `backend/main.py` | ① import 区后加 `_MEDIA_TYPES` 映射 + `_media_type(path)` 函数（不碰系统 `mimetypes` 库）；② 前端服务段重写：`FRONTEND_DIST = settings.PROJECT_ROOT / "frontend" / "dist"`（顺带修 **pitfalls T02** 跨层级路径），`root()` 条件分支返 `FileResponse(index.html, media_type="text/html; charset=utf-8")`，**删** `app.mount("/", StaticFiles(html=True))`，加 `spa_fallback` catch-all（带 media_type）注册在所有 `@app` 路由之后 |
| win10 `backend/main.py` | mirror：加映射+函数；`root` 的 FileResponse 加 media_type；**删** `/assets` StaticFiles mount（/assets 改由 spa_fallback 统一服务）；`spa_fallback` 两处 FileResponse 加 media_type |
| `dist/工艺文件系统/app/backend/main.py` | cp 自 win10 同步 |

## 禁区
- 禁用 `mimetypes.add_type` / 改全局 `mimetypes` 库（已否决，污染全局）
- 不动 API 路由 / 业务逻辑 / CORS / 请求日志中间件
- 不改 kylin（Linux 读 `/etc/mime.types`，免疫）
- 不动 `app.mount("/static/data", ...)`

## 验证
- 开发机（主项目）：`npm run build` → 启动后端 → `curl -I /` = `text/html; charset=utf-8`；`/assets/*.js` = `application/javascript; charset=utf-8`；`/health` 200 不被拦；浏览器 SPA + 子路由刷新正常
- 现场：win10 重新打包后，注册表脏的那台机器页面能开（用户现场验证）
