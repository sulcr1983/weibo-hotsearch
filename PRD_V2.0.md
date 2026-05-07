# 汽车行业舆情监控系统 — 需求文档 V4.1

## 一、产品定位

面向汽车行业从业者的自动化舆情监控与推送系统。接入 22 个权威数据源（11 科技财经 + 7 网页直采 + 4 汽车垂媒），通过品牌匹配 → 四维度门禁 → 汇总过滤 → 金融过滤 → SimHash 去重五层筛选，自动推送日报/周报/月报到飞书和邮箱。

## 二、核心功能

### 2.1 数据采集（22 源）

| 数据源      | 采集方式                       | 频率         | 来源数                                  |
| -------- | -------------------------- | ---------- | ------------------------------------ |
| RSS 科技财经 | feedparser + RSSHub Docker | 每小时        | 11 个                                 |
| 网页直采     | BeautifulSoup / JSON API   | 每小时        | 7 个（新浪/搜狐/第一电动/中国汽车报/网易汽车/盖世汽车/搜狐新闻） |
| 汽车垂媒     | HTML 直采（取 a 标签自身文本）        | 每小时        | 4 个（汽车之家/懂车帝/爱卡汽车/易车网）               |
| 微博热搜     | HTTP API（免Cookie）          | 57\~67分钟随机 | 1 个                                  |

### 2.2 五层筛选流水线

| 层级      | 环节                                      | 说明          |
| ------- | --------------------------------------- | ----------- |
| ① 品牌门禁  | 10 品牌 × 扩展子关键词，标题+正文双门禁                 | 非品牌内容直接丢弃   |
| ② 四维度门禁 | 关键词评分制（每维度 18-22 词），未命中则 LLM 二次判断       | 非业务内容直接丢弃   |
| ③ 汇总过滤  | 标题含"晨报/晚报/汇总/前瞻"等汇总类关键词直接丢弃             | 避免"EV晨报"混入  |
| ④ 金融过滤  | 30+ 金融术语正则，命中 ≥3 个丢弃                    | 股市快讯不入库     |
| ⑤ 去重    | URL MD5 + python-simhash C 扩展 + 标题相似度合并 | 跨来源/跨时间事件合并 |

### 2.3 推送输出

| 类型 | 时间           | 渠道      | 内容                                      |
| -- | ------------ | ------- | --------------------------------------- |
| 日报 | 每日 09:00     | 飞书 + 邮件 | 新闻热点按品牌分组，40 字摘要 + 超链接                  |
| 周报 | 周一 08:00     | 飞书 + 邮件 | AI 150-200 字核心洞察 + 品牌 4 维度分类 + 超链接 + 摘要 |
| 月报 | 每月 1 日 08:00 | 飞书 + 邮件 | AI 月度总结 + 品牌频次排行榜 + 热搜词列表               |

### 2.4 品牌白名单（含扩展子关键词）

小米汽车（小米汽车/小米SU7/小米SU/小米YU7/雷军）、鸿蒙智行（问界/智界/尊界/享界/尚界/鸿蒙智行/余承东）、零跑汽车（零跑/零跑C）、理想汽车（理想汽车/理想L/理想MEGA/理想i/理想ONE）、蔚来汽车（蔚来/萤火虫/乐道/李斌）、极氪汽车（极氪/极氪00）、阿维塔、智己汽车（智己/智己L）、比亚迪（比亚迪/仰望/腾势/方程豹/王传福）、特斯拉（特斯拉/Tesla/Model Y/Model 3/Cybertruck/FSD/马斯克）

### 2.5 四维度分类

| 维度         | 内容范围                       |
| ---------- | -------------------------- |
| 🎨 创意营销/公关 | 跨界联名、危机公关、辟谣、声明、营销活动（18 词） |
| 📤 投放与合作   | KOL 商单、开屏投放、签约、战略合作（18 词）  |
| 🌟 明星与IP   | 代言人、综艺植入、联名款、冠名、赛事赞助（17 词） |
| ⚙️ 核心活动    | 新车上市、技术发布、交付、财报、路试（22 词）   |

## 三、技术架构

### 3.1 统一入口（单进程）

```
car-monitor-v3 (port 8001)
├─ collector/   RSS + Web + Weibo + 垂媒
├─ processor/   品牌/维度/LLM/金融/去重
├─ storage/     SQLite(WAL) + asyncio.Queue
├─ reporter/    日报/周报/月报 + AI总结 + 健康仪表盘
└─ templates/   飞书卡片 + 邮件HTML（品牌色胶囊标签）

辅助：Docker RSSHub(1200) + Redis(6379)
```

### 3.2 数据源配置（YAML）

所有 22 个数据源统一在 `sources/sources.yml` 管理，新增源只需加一个 YAML 条目，零代码改动。

### 3.3 关键技术选型

| 组件     | 选型                                       |
| ------ | ---------------------------------------- |
| Web 框架 | FastAPI + Uvicorn（异步单端口）                 |
| 数据库    | SQLite WAL + aiosqlite                   |
| 去重     | python-simhash C 扩展（Hamming≤20）+ 标题相似度兜底 |
| 中文分词   | Jieba + 自定义品牌词典                          |
| AI 总结  | 火山引擎 Ark (doubao-seed-2-0-pro-260215)    |
| 推送     | 飞书 Interactive Card + QQ SMTP            |
| 调度     | APScheduler AsyncIOScheduler             |
| 日志     | TimedRotatingFileHandler（8 天轮转）          |
| 源配置    | PyYAML                                   |

### 3.4 数据库

**articles**：url\_hash(PK) | title | url | source | source\_level | brand | keywords(JSON) | content | simhash | event\_id | summary | score | score\_tier | is\_pushed | push\_date | created\_at

**events**：event\_id(PK) | brand | title | keywords(JSON) | article\_count | sources(JSON) | first\_seen | last\_seen

**hotsearch\_events**（v3\_weibo.db）：id | keyword | brand | link | label | heat | first\_seen\_at | last\_seen\_at | appear\_count | status

## 四、调度策略

| 任务   | 触发器                 | 说明               |
| ---- | ------------------- | ---------------- |
| 新闻采集 | interval(hours=1)   | 22 源全量采集         |
| 微博采集 | interval(57\~67m随机) | 微博热搜 API → 品牌匹配  |
| 日报   | cron(09:00)         | 昨日 40 字摘要汇总      |
| 周报   | cron(周一 08:00)      | 7 天汇总 + AI 总结    |
| 月报   | cron(每月 1 日 08:00)  | 品牌频次 + 热搜词       |
| 清理   | cron(09:05)         | 新闻 8 天 / 微博 30 天 |

## 五、API 接口

| 方法   | 路径                | 说明                       |
| ---- | ----------------- | ------------------------ |
| GET  | `/`               | 系统状态                     |
| GET  | `/health`         | 来源健康仪表盘（成功/失败/类型分布/DB统计） |
| POST | `/collect`        | 手动触发采集                   |
| POST | `/report/daily`   | 手动触发日报                   |
| POST | `/report/weekly`  | 手动触发周报                   |
| POST | `/report/monthly` | 手动触发月报                   |

## 六、质量红线

1. 品牌白名单严格锁定 — 变更需同时改 BRAND\_PATTERNS + BRAND\_COLORS
2. 所有入库内容必须通过四维度门禁 + 汇总过滤器
3. 金融快讯必须过滤
4. 推送函数不加 retry（非幂等）
5. AI 生成失败降级为原始数据推送
6. 异步队列满时丢弃而非阻塞
7. 单源异常不影响整体采集

## 七、数据保留

- 新闻 8 天，微博 30 天
- 日志 8 天轮转
- 数据库 WAL 模式，cache\_size=64MB

## 八、项目结构

```
/opt/weibo-hotsearch/
├── .env                          # 配置（不纳入版本管理）
├── .gitignore
├── system/                       # 核心黑盒
│   ├── main.py                   # V4.0 统一入口
│   ├── config.py                 # 路径锚点 + 环境变量
│   ├── requirements.txt          # 13 个依赖
│   ├── README.md                 # 软件说明书
│   ├── collector/                # 采集层（4 文件）
│   ├── processor/                # 处理层（5 文件）
│   ├── storage/                  # 存储层（1 文件）
│   ├── reporter/                 # 推送层（5 文件）
│   ├── templates/                # 视觉层（5 文件）
│   ├── sources/                  # 数据源 YAML 配置
│   ├── tests/                    # 回归测试
│   │   └── test_v3.py            # 8 项测试 ALL PASS
│   └── services/                 # systemd 服务
│       └── car-monitor-v3.service
├── data/                         # 数据库
└── logs/                         # 日志
```

## 九、部署

```bash
cd /opt/weibo-hotsearch
python3 -m venv venv
./venv/bin/pip install -r system/requirements.txt
sudo cp system/services/car-monitor-v3.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now car-monitor-v3
```

## 十、V4.0 → V4.1 更新

### 微博采集重构

- 主源从 `s.weibo.com/top/summary`（需Cookie）改为 `weibo.com/ajax/side/hotSearch`（免Cookie，无需登录）
- 调度频率从 60 分钟改为 57\~67 分钟随机间隔，降低被封禁风险
- 去重窗口从 30 分钟扩展到 24 小时（同品牌+同标题唯一）
- 链接统一使用 `s.weibo.com/weibo?q=关键词`，不再依赖不可靠的 `word_scheme` 字段
- 飞书日报微博板块含热搜标签（爆/热/新/沸）并自动去重合并

### 过滤器优化

- UGC 正则从 10 词收缩到 6 词（移除 `\d+小时前|分钟前|次阅读|万阅读` 等误杀项）
- 观点过滤器从全局13词收缩到仅虎嗅7词，避免误杀正常汽车新闻

### 日报格式升级

- 从逐条平铺改为 品牌分组→四维度分组→40字摘要→来源+时间

### 测试覆盖

- 8 项回归测试（test\_v3.py）+ 全链路集成测试（采集→入库→日报→周报→Health API）

### API 变更

- `POST /collect` 现在同时触发新闻 + 微博采集

