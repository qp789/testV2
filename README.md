# qpquiz-web · 手机可用的 Python 自测题库

一个跑在本机的 Web 应用：电脑上启动服务，手机连同一个 Wi-Fi 用浏览器打开就能答题，还能「添加到主屏幕」当 App 用。

后端 FastAPI + SQLite，前端原生 JS（无构建步骤），15 道内置 Python 单选题。

## 功能

- **两种模式**：练习（每题作答后立刻看解析）/ 考试（全部答完统一回顾）
- **服务端会话状态**：每道题的作答都落库，刷新页面、换设备都能继续
- **筛选**：题量、分类自由组合，随机抽题
- **统计**：答题轮数、正确率、最佳单轮、平均分、分类正确率
- **历史**：每轮的时间、模式、得分，点开可看当轮错题
- **错题回顾**：错题 + 你的选择 + 正确答案 + 解析
- **移动端适配**：响应式布局、44px 以上触控区域、支持添加到主屏幕（PWA manifest）

## 快速开始

```bash
# 1. 准备环境（Python 3.10+）
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. 启动
.venv/bin/python -m app
# 或者一键脚本：./run.sh
```

看到 `http://127.0.0.1:8765` 后：

- 电脑上直接打开；
- 手机连同一个 Wi-Fi，访问 `http://<电脑的局域网 IP>:8765`（服务默认监听 `0.0.0.0`）；
- 手机浏览器菜单里选「添加到主屏幕」，图标和全屏体验接近原生 App。

### 配置（环境变量）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `QPQUIZ_HOST` | `0.0.0.0` | 监听地址，改成 `127.0.0.1` 可只允许本机 |
| `QPQUIZ_PORT` | `8765` | 端口 |
| `QPQUIZ_DB` | `data/qpquiz.db` | SQLite 路径 |
| `QPQUIZ_QUESTIONS` | `data/questions.json` | 题库路径 |

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/meta` | 题库规模、分类、版本 |
| GET | `/api/questions` | 题目列表（不含答案） |
| POST | `/api/sessions` | 创建一轮：`{mode, count, categories, difficulties, seed}` |
| GET | `/api/sessions/{id}` | 会话状态（当前题目、进度、得分） |
| POST | `/api/sessions/{id}/answers` | 作答：`{question_id, choice, elapsed_ms}`，练习模式返回解析 |
| POST | `/api/sessions/{id}/finish` | 提前结束并返回总结 |
| GET | `/api/sessions/{id}/summary` | 结果：得分、分类正确率、错题 |
| GET | `/api/stats` | 全局统计 |
| GET | `/api/history?limit=20` | 历史记录 |

完整 OpenAPI 文档：启动后打开 `/api/docs`。

## 项目结构

```text
app/
├── main.py            # 应用工厂：题库、数据库、路由、静态资源
├── config.py          # 路径与监听配置
├── domain/            # 纯领域逻辑：模型、抽题、计分（不依赖框架）
│   ├── models.py
│   ├── selection.py
│   └── engine.py
├── data/              # SQLite：连接、迁移、仓储
│   ├── database.py
│   └── repository.py
├── api/               # HTTP 层：pydantic 入参与路由
└── __main__.py        # python3 -m app
web/                   # 前端：index.html / app.js / style.css
data/questions.json    # 题库
tests/                 # pytest：领域、仓储、API 共 19 个用例
```

## 数据与计分

- 分值按难度：1/2/3 → 10/14/18 分，跳过记 0 分；
- 数据库两张表：`sessions`（每轮汇总）与 `session_items`（每题作答明细），
  侧边统计全部由 SQL 实时聚合；
- schema 版本记录在 `PRAGMA user_version`，`app/data/database.py` 的
  `MIGRATIONS` 支持顺序升级。

## 测试

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

覆盖抽题过滤与随机复现、计分边界、会话状态流转、SQLite 存取与聚合、HTTP 全流程
（创建会话 → 逐题作答 → 结果 → 统计 → 历史）以及参数校验与冲突场景。

## 分支

| 分支 | 内容 |
| --- | --- |
| `main` | v1：命令行版本 |
| `level/intermediate` | 当前版本：本机 Web 应用（中级） |
| `level/advanced` | 进阶版本：账号体系、离线同步、SRS 复习（高级） |

## License

MIT，见 [LICENSE](LICENSE)。
