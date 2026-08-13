# 工艺文件辅助编辑系统

> 工艺意图 → 标准工艺术语 → 工艺文件生成。基于 AI 的工艺文件智能编辑与辅助系统。

## 跑起来

```bash
# 后端
cd backend
pip install -r requirements.txt
python init_db.py        # first run only
python main.py           # http://127.0.0.1:8000

# 前端
cd ../frontend
npm install
npm run dev              # http://127.0.0.1:3000
```

## 往哪看

README 只是指针——项目真相在下面这些**单一事实源**，不在这里复制（复制即腐烂）：

| 真相 | 去哪看 |
|---|---|
| 当前架构 / Agent 系统 / 技术栈 | [CLAUDE.md](CLAUDE.md) |
| 进度 / 状态 | [DEV-LOG.md](DEV-LOG.md) |
| 协作开发（新同事先看） | [ONBOARDING.md](ONBOARDING.md) → [CONTRIBUTING.md](CONTRIBUTING.md) |
| 策略 / 优先级 | 根 [CLAUDE.md](../../CLAUDE.md) + [本项目 CLAUDE.md](CLAUDE.md) |

> 约定：架构 / 功能描述不写进 README（写进即腐烂），真相见上表。历史在 git。
