# testV2 · qpquiz v2

Python 自测题库的第二版，提供两个独立分支，对应两种难度：

| 分支 | 难度 | 形态 |
| --- | --- | --- |
| [`level/intermediate`](../../tree/level/intermediate) | 中级 | FastAPI + SQLite + 原生 JS 的本机 Web 应用 |
| [`level/advanced`](../../tree/level/advanced) | 高级 | 在 Web 版基础上加账号体系、离线同步、SRS 复习与插件化题型 |

两个分支都是**孤儿分支**：没有共同历史，各自独立演进。

## 怎么用（两个分支通用）

```bash
git checkout level/intermediate    # 或 level/advanced
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app
```

然后电脑打开 `http://127.0.0.1:8765`，手机连同一个 Wi-Fi 打开 `http://<电脑IP>:8765`，
浏览器菜单里「添加到主屏幕」即可当 App 使用。

## 分支说明

- **level/intermediate**：分层架构（domain / data / api / web），服务端会话状态，
  SQLite 迁移，19 个 pytest 用例。
- **level/advanced**：中级全部能力 + 用户注册登录（HMAC 令牌）、按用户的 SRS 复习调度、
  离线答题队列与同步冲突解决、插件化题型（单选 / 多选 / 判断）、限流与请求 ID、CI 流程。

## License

MIT
