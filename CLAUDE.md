# TinderGPT — 自动约会助手

AI 驱动的 Tinder 聊天助手。你右滑点赞，它负责发开场白、聊天、邀约见面。

## 项目架构

```
TinderGPT/
├── main.py                     # FastAPI 服务器 (localhost:8080)
├── auto_respond.py             # 自动轮询回复 (每2分钟检查新消息)
├── scheduler.py                # [未启用] 定时调度器
├── probe_tinder.py             # Tinder 页面结构探测工具
├── AI_logic/
│   ├── config.py               # [定制] 从 ~/.claude/settings.json 自动读取 API 密钥
│   ├── local_store.py          # [定制] 本地 SQLite (替代原 Airtable)
│   ├── opener.py               # 开场白生成 (英语)
│   ├── respond.py              # 回复引擎 (Analyzer → Commander → Writer)
│   ├── misc.py                 # 翻译工具
│   ├── prompts/                # 6 个 prompt 模板 (按《聊天话术技巧》重写)
│   │   ├── opener.prompt
│   │   ├── analyzer.prompt
│   │   ├── commander_step1.prompt
│   │   ├── commander_step2.prompt
│   │   ├── writer.prompt
│   │   └── writer_tindebielik.prompt
│   ├── rule_base/              # SQLite 搭讪规则库 (7 条中文规则)
│   │   ├── rules_db.sqlite
│   │   ├── rules_db_conn.py
│   │   └── seed_rules.py       # 重建规则库脚本
│   ├── data/                   # 对话记忆数据库
│   │   └── conversations.sqlite
│   └── cached_messages/
│       ├── rise_msg_orig.txt
│       └── rise_msg.txt
├── driver/
│   ├── driver.py               # Firefox + Selenium (自动隐藏 webdriver 标记)
│   ├── FirefoxProfile/         # 持久化 Firefox 配置 (保持 Tinder 登录)
│   └── connectors/
│       └── tnd_conn.py         # Tinder 页面自动化操作
├── images/                     # README 图片
├── .env                        # 环境配置
├── .env.template
├── requirements.txt
└── readme.md
```

## 回复流水线

```
消息 → Analyzer(temp=0) → Commander(temp=0.3) → Writer(temp=0.5) → 回复
```

1. **Analyzer** — 分析对话阶段、追踪三项指标 (情感纽带/吸引力形象/讲故事)
2. **Commander** — 选策略标签 (Bond/Attractive guy image/Storytelling/Suggesting meeting/Comfort/Ask for contact)
3. **Writer** — 从规则库取话术规则，撰写消息。自动检测对方语言，匹配回复。

## 本地化修改

1. **API** (`config.py`) — 读取 `~/.claude/settings.json`，DeepSeek Anthropic 端点 `/anthropic` → OpenAI `/v1`
2. **存储** (`local_store.py`) — `sqlite3` 替代 Airtable，`AI_logic/data/conversations.sqlite`
3. **模型** (`.env`) — `OPENAI_MODEL=deepseek-chat` (兼容 function calling)
4. **Prompt** — 按《聊天话术技巧》重写全部 6 个 prompt
5. **规则库** — 7 条规则用中文重写 (推拉/情绪共鸣/间接邀约等)
6. **语言** — 开场白默认英语，回复自动匹配对方语言
7. **防检测** — 隐藏 `navigator.webdriver`，锁文件自动清理

## 环境配置

`.env` 必填：
```env
USE_LANGUAGE=english           # 开场白语言
CITY=Kuala Lumpur              # 你的城市
PERSONALITY=你的简介            # 3-4句话
```

可省略 (自动读取 Claude 配置)：
```env
# OPENAI_API_KEY
# OPENAI_BASE_URL
OPENAI_MODEL=deepseek-chat    # 覆盖默认模型
PUSHBULLET_API_KEY=           # 可选，手机通知
```

## 使用

```powershell
# 终端 1：主服务 (一直跑着)
cd e:\my-sweet-agent\TinderGPT
.\env\Scripts\python.exe main.py --head

# 终端 2：自动回复 (可选，一直跑着)
.\env\Scripts\python.exe auto_respond.py
```

### 手动操作

| 端点 | 查找标签 | 作用 |
|------|---------|------|
| `start_tnd` | — | 打开 Tinder 主页 |
| `opener` | "配对" | 给新匹配发开场白 (英语)。只在配对页操作，不碰消息页 |
| `respond` | "消息" | 回复第一个对话。如果最后一条是我们发的则自动跳过 |
| `respond_all` | "消息" | 回复所有未读消息，跳过已回复的 |
| `respond/{n}` | "消息" | 回复第 n 个对话 |
| `rise` | "消息" | 给 3-7 天沉默的匹配发复活消息 |
| `clear_base` | — | 清理 7 天以上过期记录 |
| `reload` | — | 热重载 prompt，无需重启 |
| `close` | — | 关闭 Tinder 页面 |

### 日常操作

1. 手机刷 Tinder 右滑
2. `auto_respond.py` 自动发开场白 + 自动回复（每 2 分钟轮询）
3. 也可手动：`localhost:8080/opener` 或 `localhost:8080/respond`
4. AI 聊到火候自动要号码，Pushbullet 通知你

### 行为规则

- **开场白** 只看"配对"标签页（新匹配），聊过的不再发
- **回复** 只看"消息"标签页，对方没回复之前不会追发第二条
- **语言**：开场白默认英语，回复自动匹配对方语言

### 探测 Tinder 页面结构

当 Tinder 更新 UI 导致 XPath 失效时：
```powershell
.\env\Scripts\python.exe probe_tinder.py
```

## 关键依赖

- **Python**: 3.14
- **浏览器**: Firefox (当前 v152)
- **Selenium**: 4.45 (自动管理 geckodriver)
- **LLM**: DeepSeek API (deepseek-chat, OpenAI 兼容模式)
- **存储**: SQLite 本地 (`AI_logic/data/conversations.sqlite`)
- **规则库**: SQLite (`AI_logic/rule_base/rules_db.sqlite`)
