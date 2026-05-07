# 汽车行业舆情监控系统 V4.3 — 软件说明书

## 一、痛点直击

汽车行业从业者每天面对海量信息：微博热搜每分钟刷新、各媒体平台持续更新。手工翻看 30+ 个新闻源追踪 10 个品牌的动态，耗时耗力且容易遗漏关键信息。

**这个系统解决的核心问题：**

| 痛点 | 系统对策 |
|------|---------|
| 信息源太多，看不过来 | 一键接入 23 个数据源（12 RSS + 7 网页直采 + 4 垂媒），每小时轮询 |
| 海量内容中找品牌信息如大海捞针 | 10 品牌正则双门禁 + 四维度门禁，非业务内容不写入数据库 |
| 品牌动态杂乱，无法判断重要性 | 4 维度评分分类（营销/投放/明星IP/核心活动），每品牌精选 3-10 条 |
| 每天人工汇总日报太累 | 每日 09:00 自动推送日报到飞书 + 邮箱 |
| 周报需要追踪趋势写分析 | 每周一 08:00 AI 生成 150-200 字行业总结 + 品牌分类明细 |
| 月度没有全局视野 | 每月 1 日 08:00 品牌频次榜 + 热搜词表格 + AI 月度总结 |

## 二、核心使命

**一句话：7×24 小时自动监控 10 个汽车品牌舆情，品牌匹配 → 四维度门禁 → 汇总过滤 → 金融过滤 → 去重聚类 → 日报/周报/月报推送到飞书和邮箱。**

## 三、看不见的工作

这些优化用户不会直接感受到，但它们是系统"不崩、不丢、不乱"的保障：

### 3.1 路径自愈机制

系统启动时自动创建数据库文件及索引。所有路径通过 `config.py` 中基于 `pathlib.Path` 的锚点常量引用，代码中不存在任何 `../` 相对路径字符串，宿主机、Docker 环境、不同用户名路径下均能正确运行。

### 3.2 数据库幂等性保护

- 新闻文章：`url_hash (MD5)` 唯一索引 + `INSERT OR IGNORE`，同一 URL 不会重复写入
- 写入队列满时丢弃而非阻塞，保护系统不因下游阻塞而崩溃
- SQLite WAL 模式 + 64MB 缓存 + `NORMAL` 同步策略，兼顾并发读写性能与数据安全

### 3.3 品牌匹配精度调优

10 个品牌 × 扩展子关键词（如：小米汽车→小米汽车|小米SU7|小米SU|小米YU7），配合"标题优先→正文兜底"的双门禁匹配。精确短语切换避免泛匹配误报。

### 3.4 金融简报过滤

正则匹配涨超/跌超/收盘/恒指/中概股等 30+ 金融术语，命中 ≥3 个自动丢弃。杜绝"蔚来涨超 4%"这类股市快讯混入业务内容。

### 3.5 四维度门禁

品牌匹配后必须通过 4 维度评分分类（每个维度 18-22 个关键词），累计评分选最高维度，未命中任何维度则直接丢弃。确保入库的每一条内容都严格属于 🎨/📤/🌟/⚙️ 四个业务维度。

### 3.6 三层去重

```
URL MD5 → python-simhash 内容聚类(Hamming≤16) → 事件合并(跨时间/跨来源)
```

同一话题被多个媒体在不同时间报道时，自动合并为一条，标注 "来源：36氪、第一财经、凤凰网 | 首现 14:20"。

### 3.7 异步写入队列 + 优雅停机

SQLite WAL 模式 + `asyncio.Queue` 解耦读写，停止服务时自动 flush 队列、关闭连接、取消调度器，确保数据不丢失。

### 3.8 异常不崩坏体系

- 单个源连接超时不影响其他源（独立 try-except）
- AI 生成失败自动降级为原始数据推送
- 全部异常记录到按天轮转日志（8 天保留）
- reschedule_job 失败时 fallback 到 add_job，避免崩溃循环

### 3.9 漏斗追踪与可观测性

采集全链路可观测，每个处理节点记录丢弃原因：

```
[数据源] → [品牌门禁] → [维度分类] → [金融过滤] → [去重入库]
              ↓              ↓            ↓            ↓
         NO_BRAND_MATCH  NO_DIMENSION  FINANCIAL  DUPLICATE

每轮采集输出漏斗报告：
  源捕获: 215 → 品牌命中: 23 → 维度通过: 12 → 入库: 4 条
```

Trace 日志记录每条数据的完整处理路径，失败数据保存 HTML 快照到 `snapshots/` 目录。

## 四、监控品牌覆盖

| 品牌 | 匹配关键词 | 品牌色 |
|------|-----------|--------|
| 小米汽车 | 小米汽车 / 小米SU7 / 小米YU7 | `#FF6900` |
| 鸿蒙智行 | 鸿蒙智行 / 问界 / 智界 / 尊界 / 享界 / 尚界 | `#CE0E2D` |
| 零跑汽车 | 零跑汽车 / 零跑 / 零跑C | `#0052D9` |
| 理想汽车 | 理想汽车 / 理想L / 理想MEGA / 理想i / 理想ONE | `#4A90D9` |
| 蔚来汽车 | 蔚来汽车 / 蔚来 / 萤火虫 / 乐道 | `#2E6BE6` |
| 极氪汽车 | 极氪汽车 / 极氪 / 极氪00 | `#00B2A9` |
| 阿维塔 | 阿维塔 | `#6C5CE7` |
| 智己汽车 | 智己汽车 / 智己 / 智己L | `#E84393` |
| 比亚迪 | 比亚迪 / 仰望 / 腾势 / 方程豹 | `#C0392B` |
| 特斯拉 | 特斯拉 / Tesla / Model Y / Model 3 | `#E74C3C` |

## 五、数据源清单

### 5.1 RSS 源（12 个，YAML 配置 + RSSHub 聚合）

| 类别 | 来源 |
|------|------|
| 科技商业 | 36氪、钛媒体 |
| RSSHub 聚合 | 第一财经快讯、财联社热门、财联社深度、华尔街见闻、澎湃新闻精选、财新最新、36氪快讯、虎嗅、知乎日报 |
| 极客 | 极客公园 |

### 5.2 网页直采源（7 个，YAML 配置）

| 来源 | 采集模式 |
|------|---------|
| 新浪汽车 | JSON API |
| 搜狐汽车、第一电动、中国汽车报、网易汽车、盖世汽车、搜狐新闻 | HTML 解析 |

### 5.3 浏览器渲染源（Playwright 无头浏览器）

| 来源 | 说明 |
|------|------|
| 新华网汽车 | 反爬页面，需浏览器渲染 JS 后提取 |

### 5.4 汽车垂媒（4 个，YAML 配置）

| 来源 | 说明 |
|------|------|
| 汽车之家、懂车帝、爱卡汽车、易车网新闻 | HTML 直采，取 a 标签自身文本 |

## 六、推送输出

> **时间口径说明**：日报/周报/月报按「滚动窗口」计算（过去24h/7d/自然月），
> 不是严格日历日。若需对齐「昨天 00:00~23:59」口径，请在 builder.py 中改用
> `timedelta(days=1)` + 日期字符串匹配。

### 6.1 日报（每日 09:00）

| 渠道 | 标题 | 内容 |
|------|------|------|
| 邮箱 | 昨日汽车行业舆情热点新闻 | 新闻热点按品牌分组，40 字摘要，品牌色胶囊标签 |
| 飞书 | 同上 | 同上，lark_md 原生卡片 |

### 6.2 周报（每周一 08:00）

| 渠道 | 标题 | 内容 |
|------|------|------|
| 邮箱 | 上周汽车行业10个品牌舆情汇总 MM-DD-MM-DD | AI 150-200 字核心洞察 + 品牌 4 维度分类明细 + 摘要 |
| 飞书 | 同上 | 同上，lark_md 原生卡片 |

### 6.3 月报（每月 1 日 08:00）

| 渠道 | 标题 | 内容 |
|------|------|------|
| 邮箱 | 微博月度舆情报告 YYYY年M月 | AI 月度总结 + 品牌频次排行榜 + 热搜词列表表格 |
| 飞书 | 同上 | 同上，lark_md 原生卡片 |

### 6.4 四维度分类规则

| 维度 | 收录内容 | 关键词数 |
|------|---------|---------|
| 🎨 创意营销/公关 | 跨界联名、危机公关、辟谣、用户互动 | 18 个 |
| 📤 投放与合作 | KOL 商单、开屏投放、签约、战略合作 | 18 个 |
| 🌟 明星与IP | 代言人、综艺植入、联名款、赛事赞助 | 17 个 |
| ⚙️ 核心活动 | 新车上市、技术发布、交付、财报、路试 | 22 个 |

## 七、技术架构

### 7.1 统一入口架构（V4.3）

```
┌─────────── Ubuntu Server ───────────┐
│                                      │
│  car-monitor-v3 (8001)              │
│  ├─ RSS订阅 + RSSHub(1200) → 品牌门禁│
│  ├─ 网页直采 + Playwright 浏览器渲染 │
│  ├─ 微博热搜 → 品牌匹配 → weibo DB  │
│  ├─ Observability: 漏斗追踪 + Trace  │
│  ├─ 金融过滤 → 四维度门禁           │
│  ├─ python-simhash 去重 + 事件聚类   │
│  ├─ 写队列 → v3_monitor.db          │
│  ├─ 每日09:00 日报                  │
│  ├─ 每周一08:00 周报                │
│  └─ 每月1日08:00 月报               │
│                                      │
│  nohup 后台运行 (避免 systemd 重启循环)│
│  RSSHub Docker 容器辅助              │
└──────────────────────────────────────┘
```

### 7.2 数据处理流水线

```
[数据源] → [品牌正则过滤] → [四维度门禁] → [金融过滤] → [URL去重]
                                                              ↓
                                                   [python-simhash聚类]
                                                              ↓
                                                   [事件合并(跨时间/跨来源)]
                                                              ↓
                                                   [日报/周报/月报推送]
```

### 7.3 技术选型

| 组件 | 选型 | 选型理由 |
|------|------|---------|
| Web 框架 | FastAPI + Uvicorn | 异步原生，性能逼近 Node.js，自动生成 API 文档 |
| 数据库 | SQLite WAL + aiosqlite | 单机免部署，WAL 模式支持并发读写，零维护 |
| 定时调度 | APScheduler AsyncIOScheduler | 原生异步 Cron + Interval，与 FastAPI 事件循环融合 |
| RSS 解析 | feedparser | 行业标准库，容错性强，支持多编码 |
| 中文分词 | Jieba | TF-IDF 关键词提取 + 自定义品牌词典 |
| 去重 | python-simhash (C扩展) + 标题相似度兜底 | 比纯 Python 快约 100 倍，Hamming≤20 |
| AI 总结 | 火山引擎 Ark (doubao-seed-2-0-pro-260215) | 高性价比，中文理解强 |
| 推送 | 飞书 Interactive Card + QQ SMTP | 双渠道冗余 |
| 日志 | TimedRotatingFileHandler | 按天轮转，8 天保留 |
| 配置 | PyYAML | `sources/sources.yml` 统一管理 22 个数据源 |

## 八、部署指南

### 环境要求

- Ubuntu 24.04 64bit / Python 3.10+
- Docker（RSSHub 聚合服务，localhost:1200）
- Playwright Chromium（浏览器渲染采集）

### 部署步骤

```bash
# 上传项目到 /opt/weibo-hotsearch/ 后执行
cd /opt/weibo-hotsearch
bash system/services/deploy.sh

# 或手动
python3 -m venv venv
./venv/bin/pip install -r system/requirements.txt
playwright install chromium  # 浏览器渲染依赖
nohup ./venv/bin/python system/main.py > /dev/null 2>&1 &
```

## 九、配置说明

编辑 `/opt/weibo-hotsearch/.env`：

```ini
# ── 数据库路径 ──
DB_PATH=v3_monitor.db
WEIBO_DB_PATH=v3_weibo.db

# ── 微博热搜（V4.1 已改为免Cookie API，以下配置已废弃）──
# WEIBO_COOKIE=SUB=_2A25...  （V4.1 不再需要）

# ── AI API（火山引擎 Ark，用于周报/月报生成）──
AI_API_URL=https://ark.cn-beijing.volces.com/api/v3/chat/completions
AI_API_KEY=你的API_Key
AI_MODEL=doubao-seed-2-0-pro-260215

# ── 飞书机器人 Webhook ──
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx

# ── 邮件发送（QQ 邮箱 SMTP）──
EMAIL_SENDER=your@qq.com
EMAIL_PASSWORD=授权码（非QQ密码）
EMAIL_RECIPIENTS=receiver@qq.com
SMTP_SERVER=smtp.qq.com
SMTP_PORT=587

# ── RSSHub Docker 地址 ──
RSSHUB_HOST=http://localhost:1200

# ── 浏览器渲染（可选，默认 false）──
PLAYWRIGHT_ENABLED=false
```

## 十、运维手册

### 常用命令

```bash
# 启动服务（nohup 模式，避免 systemd 重启循环）
cd /opt/weibo-hotsearch && bash system/services/deploy.sh

# 查看日志
tail -f /opt/weibo-hotsearch/logs/main.log

# 停止/重启
pkill -f "uvicorn main:app"
cd /opt/weibo-hotsearch && bash system/services/deploy.sh

# 手动触发采集
curl -X POST http://localhost:8001/collect

# 手动触发日报/周报/月报
curl -X POST http://localhost:8001/report/daily
curl -X POST http://localhost:8001/report/weekly
curl -X POST http://localhost:8001/report/monthly
```

### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 系统状态 |
| POST | `/collect` | 手动触发一次新闻采集 |
| POST | `/report/daily` | 手动触发日报推送 |
| POST | `/report/weekly` | 手动触发周报推送 |
| POST | `/report/monthly` | 手动触发月报推送 |

### 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| 服务反复重启 | Python 导入失败或 reschedule_job 异常 | 查看 `/opt/weibo-hotsearch/logs/main.log`；已修复崩溃循环 Bug |
| 邮件发送失败 | QQ 授权码过期 | 重新获取 QQ 邮箱授权码，更新 `.env` |
| 微博抓取失败 | API 变更或频率限制 | 检查 `weibo.com/ajax/side/hotSearch` 可达性，降低采集频率 |
| AI 生成失败 | 火山引擎余额不足或 Key 错误 | 确认 `AI_API_KEY` 和 `AI_MODEL` |
| RSSHub 503 | Docker 容器未启动 | `docker start rsshub` |
| 飞书推送失败 | Webhook URL 过期 | 更新 `.env` 中的 `FEISHU_WEBHOOK_URL` |
| RSSHub 外网不通 | 阿里云安全组拦截 | RSSHub 仅 localhost 访问，应用同机部署无需外网 |

## 十一、项目结构

```
/opt/weibo-hotsearch/
├── .env                          # 私密配置
├── .gitignore
├── README.md                     # 产品说明书
├── system/                       # 核心黑盒
│   ├── main.py                   # V4.3 统一入口（FastAPI + APScheduler + 启动自检）
│   ├── config.py                 # 路径锚点 + 环境变量
│   ├── requirements.txt          # 依赖清单
│   ├── README.md                 # 本说明书
│   ├── collector/                # 采集层（5 文件）
│   │   ├── rss_fetcher.py        # RSS 订阅（12 源，含 RSSHub 聚合）
│   │   ├── web_scraper.py        # HTML/API 网页直采（7 源）
│   │   ├── weibo_collector.py    # 微博热搜 API 采集
│   │   ├── auto_media.py         # 汽车垂媒（4 源）
│   │   └── playwright_scraper.py # Playwright 浏览器渲染（反爬站点）
│   ├── processor/                # 处理层（6 文件）
│   │   ├── brand_matcher.py      # 品牌匹配 + HTML 剥离 + 金融/汇总/UGC/观点过滤
│   │   ├── deduplicator.py       # python-simhash 去重 + 事件聚类
│   │   ├── classifier.py         # 4 维度评分分类
│   │   ├── llm_classifier.py     # LLM 兜底分类（关键词未命中时）
│   │   ├── keyworder.py          # Jieba TF-IDF 关键词提取（兼容新版 API）
│   │   └── observability.py      # 漏斗追踪 + Trace 日志 + 失败快照
│   ├── storage/                  # 存储层
│   │   └── database.py           # SQLite(WAL) + 异步写入队列
│   ├── reporter/                 # 推送层（5 文件）
│   │   ├── builder.py            # 日报/周报/月报数据组装 + 事件合并
│   │   ├── feishu.py             # 飞书卡片推送
│   │   ├── emailer.py            # 邮件 SMTP 推送
│   │   ├── ai_writer.py          # AI 总结生成（周报+月报）
│   │   └── health.py             # 来源健康仪表盘
│   ├── templates/                # 视觉层（5 文件）
│   │   ├── design_tokens.py      # 色板 + 品牌标签函数
│   │   ├── email_daily.py        # 日报邮件 HTML
│   │   ├── email_weekly.py       # 周报邮件 HTML
│   │   ├── email_monthly.py      # 月报邮件 HTML
│   │   └── feishu_cards.py       # 飞书日报/周报/月报卡片
│   ├── sources/                  # 数据源统一配置
│   │   ├── __init__.py           # YAML 加载器 + {RSSHUB_HOST} 模板替换
│   │   └── sources.yml           # 23 个数据源（增删改只需改 YAML）
│   ├── v2/                       # 共享模块
│   │   ├── constants.py          # 品牌白名单 / 阈值 / 颜色
│   │   └── logger.py             # 统一日志工厂（含 Windows 兼容）
│   ├── tests/                    # 回归测试
│   │   ├── test_v3.py            # 8 项核心测试
│   │   └── test_observability.py # 漏斗追踪测试
│   └── services/                 # 部署
│       └── deploy.sh
├── data/                         # 数据库目录
│   ├── v3_monitor.db             # 新闻文章 + 事件
│   └── v3_weibo.db               # 微博热搜 + 月度快照
└── logs/                         # 运行日志（8 天轮转）
```

## 十二、从 V3 到 V4 的关键变化

| 维度 | V3 | V4 |
|------|----|----|
| 数据源 | 18 个 | 22 个（+4 汽车垂媒） |
| 配置方式 | 硬编码 constants.py | YAML `sources/sources.yml` |
| 内容过滤 | 品牌 → 维度 → 金融 三层 | 品牌 → 维度/LLM → 汇总 → 金融 → 去重 五层 |
| AI 模型 | glm-4-flash（已下线） | doubao-seed-2-0-pro-260215 |
| 去重 | Hamming≤16 | Hamming≤20 + 标题相似度兜底 |
| 仪表盘 | 无 | GET /health 来源成功/失败详情 |
| 垂媒采集 | 无 | 汽车之家/懂车帝/爱卡/易车 4 源 |
| 代码文件 | 32 文件（含死代码） | 32 文件（纯净） |

## 十三、版本演进

### V4.0 → V4.1

| 维度 | V4.0 | V4.1 |
|------|------|------|
| 微博采集 | 直接API（需Cookie，已失效） | `weibo.com/ajax/side/hotSearch`（免Cookie，无需登录） |
| 微博调度 | 每 60 分钟 | 每 57~67 分钟（随机） |
| 微博去重 | 同标题30分钟去重 | 同品牌+同标题 24h 去重 |
| 日报格式 | 逐条列举 | 品牌分组→四维度分组→40字摘要 |
| 测试覆盖 | 无集成测试 | 8项回归测试 |

### V4.1 → V4.2

| 维度 | V4.1 | V4.2 |
|------|------|------|
| AI 模型 | 豆包 doubao-seed-2-0-pro | DeepSeek V3 |
| 品牌匹配 | 宽松子关键词 | 精简白名单（精确短语） |
| 金融过滤 | 仅 financial_brief | + 快讯类过滤 |
| 代码规模 | 32 文件（含死代码） | 纯净无死代码 |

### V4.2 → V4.3

| 维度 | V4.2 | V4.3 |
|------|------|------|
| 数据源 | 22 个 | 23 个（+ RSSHub 9 路由 + Playwright 浏览器渲染） |
| RSS 聚合 | 直连各站 RSS | RSSHub Docker 聚合（localhost:1200） |
| 浏览器渲染 | 无 | Playwright 无头浏览器（新华网汽车反爬） |
| 可观测性 | 基础日志 | 漏斗追踪 + Trace 日志 + 失败快照 |
| 配置系统 | 硬编码 URL | `{RSSHUB_HOST}` 模板变量 + web_scraper link_prefix/suffix |
| 启动检查 | 无 | 依赖可用性 + 环境变量 + 数据库路径自检 |
| Bug 修复 | - | jieba API 兼容 + Windows 日志轮转 + 崩溃循环修复 |
| 部署模式 | systemd 托管 | nohup 后台运行（避免 systemd 12 秒重启循环） |
| 代码清理 | 32 文件 | 42 文件，移除 tech_debt/refactor_suggestions/PRD_V2.0 |
