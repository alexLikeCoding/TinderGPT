# TinderGPT — 自动约会助手

TinderGPT 用 AI 自动完成 Tinder 上的聊天和约会安排。你只需要右滑点赞，其余由它处理：根据对方资料生成开场白 → 建立情感连接 → 展示吸引力 → 邀约见面 → 推送通知。

## 项目架构

```
TinderGPT/
├── main.py                  # FastAPI 服务器 (localhost:8080)
├── scheduler.py             # 定时调度器，每天3个时段自动运行
├── AI_logic/
│   ├── config.py            # [已定制] 自动从 ~/.claude/settings.json 读取 API 配置
│   ├── local_store.py       # [已定制] 本地 SQLite 存储，替代原 Airtable
│   ├── opener.py            # 开场白生成 (基于对方 Bio)
│   ├── respond.py           # 回复引擎 (Analyzer → Commander → Writer 三阶段)
│   ├── respond_tindebielik.py # 备选回复引擎 (需 unsloth，可选)
│   ├── airtable.py          # [已弃用] 原 Airtable 云端存储，已被 local_store 替代
│   ├── prompts/             # Prompt 模板 (.prompt 文件)
│   ├── rule_base/           # SQLite 搭讪规则库 (pickup_rules)
│   └── cached_messages/     # 缓存的升温水消息
├── driver/
│   ├── driver.py            # Selenium Firefox 驱动
│   ├── FirefoxProfile/      # Firefox 配置文件 (需手动创建)
│   └── connectors/
│       └── tnd_conn.py      # Tinder Selenium 自动化操作
└── .env                     # 环境变量配置
```

### 回复流水线 (respond.py)

1. **Analyzer** (temp=0) — 分析对话阶段，识别对方是否提供了联系方式
2. **Commander** (temp=0.4) — 决定策略标签：Bond / Attractive guy image / Storytelling / Suggesting meeting / Comfort / Ask for contact
3. **Writer** (temp=0.7) — 根据策略标签从规则库取 Pickup 规则，撰写实际消息

## 本地化修改

本项目的以下部分已从原版修改：

1. **API 配置** (`AI_logic/config.py`) — 自动读取 `~/.claude/settings.json` 中的 `ANTHROPIC_AUTH_TOKEN` 和 `ANTHROPIC_MODEL`。DeepSeek Anthropic 端点自动转为 OpenAI 兼容端点 (`/anthropic` → `/v1`)。`.env` 中的 `OPENAI_API_KEY` 可省略。

2. **本地存储** (`AI_logic/local_store.py`) — 用标准库 `sqlite3` 替换了 Airtable 云端存储。数据库文件在 `AI_logic/data/conversations.sqlite`。API 完全兼容原 `airtable.py`。

3. **依赖** — SQLAlchemy 升级至 2.0.51（修复 Python 3.14 兼容性），`airtable-python-wrapper` 已从 requirements.txt 移除。

## 环境配置

`.env` 只需要填写：

```env
USE_LANGUAGE=chinese          # 对话语言
CITY=你的城市                  # 用于邀约时提及地点
PERSONALITY=你的个人简介        # 3-4句话，爱好/性格
PUSHBULLET_API_KEY=           # 可选，手机推送通知
```

`OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` 均可省略，会自动从 `~/.claude/settings.json` 读取。

## 启动方式

```powershell
# 激活虚拟环境
.\env\Scripts\activate

# 带界面运行（调试用，加上 --head 才有浏览器窗口）
python main.py --head

# 无头模式运行（生产环境，不加 --head 即 headless）
python main.py

# 启动每日定时调度器
python scheduler.py
```

## HTTP API 端点

| 端点 | 作用 |
|------|------|
| `GET /start_tnd` | 打开 Tinder 主页 |
| `GET /opener` | 给最新匹配发开场白 |
| `GET /opener/{n}` | 给第 n 个匹配发开场白 |
| `GET /batch_openers/{n}` | 批量给 n 个匹配发开场白 |
| `GET /respond` | 回复第一个未读消息 |
| `GET /respond/{n}` | 回复第 n 个对话（1-8） |
| `GET /respond_all` | 回复所有未读消息 |
| `GET /rise` | 给 3-7 天未联系的匹配发直升消息 |
| `GET /clear_base` | 清理 7 天无联系的记录 |
| `GET /reload` | 热重载 AI prompt 和逻辑，无需重启 |
| `GET /close` | 关闭 Tinder 页面 |
| `POST /send_message` | 发送指定消息 |

`scheduler.py` 每天在3个时段（17-18点、18-19点、20-21点）随机时间自动运行。

## 关键依赖

- **Python**: 3.14
- **浏览器**: Firefox + geckodriver (Selenium 4.9 自带)
- **LLM**: DeepSeek API (OpenAI 兼容模式)，模型 `deepseek-v4-pro`
- **存储**: SQLite (本地 `AI_logic/data/conversations.sqlite`)
- **通知**: Pushbullet (可选)

## 首次使用前

1. 在 Firefox 中创建新 Profile，目录指向 `driver/FirefoxProfile`
2. 在新 Profile 中登录 tinder.com，手动关闭所有弹窗
3. 填写 `.env` 中的 `LANGUAGE`、`CITY`、`PERSONALITY`
4. 运行 `python main.py --head` 启动
