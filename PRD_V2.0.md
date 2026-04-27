# 汽车行业舆情监控系统 — 需求文档 V2.0

## 一、产品定位

面向汽车行业从业者的自动化舆情监控与推送系统，覆盖微博热搜 + 新闻媒体双数据源，通过 AI 清洗 + SimHash 聚类 + 品牌门禁三层过滤，每日 09:00 自动推送精选日报。

## 二、核心功能

### 2.1 数据采集
| 数据源 | 采集方式 | 频率 | 说明 |
|--------|---------|------|------|
| 微博热搜 | BeautifulSoup 解析 | 每小时 | V1.0 模块，Sidecar 隔离运行 |
| RSS 新闻源 | feedparser + RSSHub | 每小时 | V2.0 模块，11 个数据源 |
| 全文提取 | trafilatura → readability → meta | 采集时 | 三段式降级提取 |

### 2.2 数据处理
| 处理环节 | 算法/方法 | 说明 |
|---------|----------|------|
| 品牌门禁 | 正则双门禁（标题+正文前200字） | 10 组品牌严格匹配 |
| AI 清洗 | 智谱清言 glm-4-flash | 剔除琐碎负面，保留行业价值 |
| 去重 | url_hash (MD5) | URL 级别防重 |
| 事件聚类 | 手写 SimHash (64bit) + 汉明距离 ≤3 | 语义相似文章归入同一事件 |
| 关键词提取 | Jieba TF-IDF top-10 | 用于 Event_ID 生成 |

### 2.3 推送输出
| 推送类型 | 时间 | 渠道 | 内容 |
|---------|------|------|------|
| 每日日报 | 09:00 | 飞书 + 邮件 | 微博热搜 + 新闻热点，品牌彩色标签 |
| 每周周报 | 周一 08:00 | 飞书 + 邮件 | AI 行业分析 + 品牌分类明细 |

### 2.4 品牌白名单（严格锁定）
小米汽车、鸿蒙智行（问界/智界/尊界/享界/尚界）、零跑汽车、理想汽车、蔚来汽车（含萤火虫/乐道）、极氪汽车、阿维塔、智己汽车、比亚迪（含仰望/腾势/方程豹）、特斯拉

## 三、技术架构

### 3.1 Sidecar 双模块架构
```
┌─────────────────────────────────────────────┐
│  Ubuntu Server                             │
│                                             │
│  ┌──────────────┐  ┌──────────────────────┐ │
│  │ V1.0 Sidecar │  │ V2.0 Main            │ │
│  │ port:8002    │  │ port:8001            │ │
│  │ 微博热搜采集  │  │ RSS新闻采集           │ │
│  │ AI清洗+推送   │  │ 品牌匹配+聚类+推送    │ │
│  │ weibo_*.db   │  │ news_articles.db     │ │
│  └──────────────┘  └──────────────────────┘ │
│                                             │
│  ┌──────────────┐  ┌───────┐  ┌──────────┐ │
│  │ TrendRadar   │  │ Redis │  │ RSSHub   │ │
│  │ port:8000    │  │ :6379 │  │ :1200    │ │
│  └──────────────┘  └───────┘  └──────────┘ │
└─────────────────────────────────────────────┘
```

### 3.2 V2.0 模块依赖链
```
constants.py → logger.py → storage.py → processor.py → fetcher.py → reporter.py → main.py
     ↓              ↓           ↓            ↓             ↓            ↓
  品牌白名单     日志配置    DataVault     SimHash      RSS+提取     飞书+邮件
  RSS源配置                 WAL模式       品牌匹配      三段降级      品牌色彩
  品牌色彩                  异步队列       Jieba分词     超时熔断      日报+周报
```

### 3.3 关键技术选型
| 组件 | 选型 | 理由 |
|------|------|------|
| Web框架 | FastAPI + Uvicorn | 异步高性能，自动API文档 |
| 数据库 | SQLite WAL + aiosqlite | 单机轻量，WAL并发读写 |
| 写入队列 | asyncio.Queue(maxsize=500) | 纯异步，与FastAPI事件循环融合 |
| RSS解析 | feedparser | 业界标准，容错强 |
| 全文提取 | trafilatura → readability-lxml → meta | 三段降级，覆盖率高 |
| 中文分词 | Jieba | 成熟稳定，自定义词典 |
| 相似度 | 手写 SimHash 64bit | 50行核心代码，无第三方依赖 |
| AI清洗 | 智谱清言 glm-4-flash | 性价比高，中文理解强 |
| 推送 | 飞书 Interactive Card + QQ SMTP | 双渠道冗余 |
| 定时调度 | APScheduler AsyncIOScheduler | 原生异步，Cron+Interval |
| 重试 | Tenacity wait_exponential | 仅用于网络请求，推送不复重 |
| 日志 | TimedRotatingFileHandler | 按天轮转，30天保留 |
| 文件锁 | filelock | 跨平台，替代 fcntl |
| Docker | docker-compose | RSSHub + Redis + TrendRadar |

### 3.4 数据库设计
**articles 表**: url_hash(PK) | title | url | source | source_level | brand | keywords(JSON) | content | simhash | event_id | summary | is_pushed | push_date | created_at

**events 表**: event_id(PK) | brand | title | keywords(JSON) | article_count | sources(JSON) | first_seen | last_seen

**weibo_hot_search 表(V1.0)**: id | brand_group | keyword | title | link | created_at | is_pushed | source

## 四、部署架构

### 4.1 服务器信息
- OS: Ubuntu 24.04 64bit
- IP: <服务器IP>
- 部署路径: /opt/weibo-hotsearch
- V1.0: systemd service (weibo-monitor.service), port 8002
- V2.0: systemd service (car-monitor-v2.service), port 8001
- Docker: TrendRadar(8000) + Redis(6379) + RSSHub(1200)

### 4.2 数据保留策略
- 文章数据: 8 天自动清理
- 日志文件: 30 天轮转
- 数据库: WAL 模式，cache_size=64MB

## 五、API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | / | V2.0 系统状态 |
| GET | /v2/articles | 查询新闻文章 |
| GET | /v2/events | 查询事件聚类 |
| POST | /v2/collect | 手动触发采集 |
| POST | /v2/report/daily | 手动触发日报 |
| POST | /v2/report/weekly | 手动触发周报 |

## 六、质量红线
1. 品牌白名单严格锁定，不可发散
2. 推送函数不加 @retry（非幂等）
3. AI 清洗失败降级为原始数据推送
4. 数据库写入 3 次指数退避重试
5. 内存超 50 条触发 GC
6. 写入队列满时丢弃而非阻塞
