# qpquiz-web（高级版）· 带账号、SRS 与离线同步的自测题库

在本机跑一个 Web 服务，手机连同一个 Wi-Fi 用浏览器答题；支持多用户账号、间隔重复复习、
离线答题队列与多题型（单选 / 多选 / 判断）。

技术栈：FastAPI + SQLite + 原生 JS，无前端构建步骤；密码用 PBKDF2 哈希，令牌用 HMAC 自签。

## 功能

- **账号体系**：注册 / 登录，PBKDF2 密码哈希，HMAC-SHA256 自签令牌（7 天有效），
  所有成绩与复习计划按用户隔离
- **多题型**：`single` / `multi` / `judge`，判分逻辑走插件注册表，新增题型只需注册一个函数
- **SRS 复习**：SM-2 调度（答对 1 天 → 3 天 → 3×ease，答错清零），`/study/due` 取到期题
- **离线队列**：断网时作答先存 `localStorage`，恢复后 `POST /api/sync` 批量补传
- **同步冲突**：同一题服务端已有不同答案时返回 `conflict` 与 `server_choice`，不覆盖
- **幂等**：`(user_id, client_id)` 唯一约束，重复上报返回 `duplicate`
- **限流与可观测**：滑动窗口限流（240 次/分钟）、`X-Request-ID`、`X-Response-Time`
- **移动端**：响应式布局、PWA manifest、可在手机上添加到主屏幕

## 快速开始

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app        # 或 ./run.sh
```

- 电脑打开 `http://127.0.0.1:8765`
- 手机同一 Wi-Fi 打开 `http://<电脑IP>:8765`，注册一个账号即可开始

首次启动会在 `data/secret.key` 生成令牌签名密钥（0600 权限），可用
`QPQUIZ_SECRET` 环境变量覆盖。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/register` | 注册：`{email, password}`，返回 token |
| POST | `/api/auth/login` | 登录 |
| GET | `/api/auth/me` | 当前用户（需 Bearer token） |
| GET | `/api/meta` | 题库规模、分类、题型 |
| POST | `/api/sessions` | 创建一轮 |
| POST | `/api/sessions/{id}/answers` | 作答，练习模式返回解析 |
| GET | `/api/sessions/{id}/summary` | 结果与错题 |
| GET | `/api/study/due` | 到期复习题 + 新题 |
| POST | `/api/study/review` | 提交一次复习，返回下次间隔 |
| POST | `/api/sync` | 离线事件批量补传（幂等 + 冲突检测） |
| GET | `/api/stats` · `/api/history` | 按用户统计与历史 |

启动后 `/api/docs` 有完整 OpenAPI 文档。

## 结构

```text
app/
├── main.py           # 应用工厂：题库、DB、签名密钥、中间件、路由
├── security.py       # PBKDF2 密码哈希、HMAC 令牌
├── middleware.py     # 请求 ID / 耗时 / 限流
├── domain/
│   ├── models.py     # Question（kind + answers）、SessionItem、QuizSession
│   ├── plugins.py    # 题型注册表与判分
│   ├── srs.py        # SM-2 调度
│   ├── selection.py  # 抽题
│   └── engine.py     # 计分与状态流转
├── data/
│   ├── database.py   # schema v1 → v2 迁移（users/cards/sync_events）
│   └── repository.py # 用户、会话、卡片、同步幂等
└── api/              # schemas + routes
web/                  # index.html / app.js / style.css（登录、答题、复习、离线队列）
tests/                # 20 个 pytest 用例
```

## 数据模型

- `users`：邮箱唯一，密码只存 `pbkdf2$迭代次数$salt$hash`
- `sessions` / `session_items`：按 `user_id` 隔离，记录每题的选择、对错、耗时
- `cards`：`(user_id, question_id)` 主键，保存 ease / interval / reps / lapses / due_at
- `sync_events`：`(user_id, client_id)` 唯一，保证离线补传幂等

## 测试

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

覆盖题型判分（含多选部分匹配）、SM-2 调度、密码与令牌安全、用户隔离、
SRS 到期查询、同步幂等与冲突、完整 HTTP 流程。

## 分支

| 分支 | 内容 |
| --- | --- |
| `main` | 仓库说明 |
| `level/intermediate` | 中级版：FastAPI + SQLite + 原生 JS |
| `level/advanced` | 当前版本：账号、SRS、离线同步、插件化题型、CI |

## License

MIT
