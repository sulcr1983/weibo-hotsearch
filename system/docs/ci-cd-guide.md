# weibo-hotsearch CI/CD & 线上运维手册

---

## 目录

1. [CI 流程与配置](#1-ci-流程与配置)
2. [测试失败快速排查树](#2-测试失败快速排查树)
3. [CI 失败标准修复流程](#3-ci-失败标准修复流程)
4. [调度健康检查与心跳检测](#4-调度健康检查与心跳检测)
5. [线上监控方案与埋点](#5-线上监控方案与埋点)
6. [反爬应对策略与告警模板](#6-反爬应对策略与告警模板)
7. [附录：命令速查表](#7-附录命令速查表)

---

## 1. CI 流程与配置

### 1.1 Pipeline 概览

```
提交代码
  │
  ├─ JOB 1: Lint ─────────────────────────────── 3m
  │   ├─ ruff 快速检查（import/语法/命名）
  │   ├─ black 格式检查
  │   ├─ mypy 类型检查（核心模块）
  │   └─ detect-secrets 秘密泄露扫描
  │
  ├─ JOB 2: Test（3.11 / 3.12 矩阵）─────────── 5m
  │   ├─ 单元测试（离线，排除 network/performance）
  │   ├─ 覆盖率报告（xml）
  │   └─ Codecov 上传
  │
  ├─ JOB 3: Integration（仅 main）───────────── 5m
  │   ├─ VCR 录制回放
  │   └─ 定时触发（每天 06:00 UTC+8）自动重录
  │
  └─ JOB 4: Notify（仅 main 失败时）─────────── 1m
      └─ 创建 GitHub Issue 标记 ci-failure
```

### 1.2 触发条件

| 事件 | 分支 | 执行 Jobs |
|------|------|-----------|
| `push` | main | lint → test → integration → notify |
| `pull_request` | main | lint → test |
| `schedule` (06:00 CST) | main | lint → test → integration |
| `workflow_dispatch` | 任意 | 全部，可指定 VCR 录制模式 |

### 1.3 关键环境变量

需在 GitHub Secrets 中配置：

| Secret | 用途 |
|--------|------|
| `CODECOV_TOKEN` | 覆盖率上传令牌（Codecov） |
| `FEISHU_WEBHOOK_URL` | （可选）飞书告警推送 |
| `DINGTALK_WEBHOOK_URL` | （可选）钉钉告警推送（见告警模板） |

### 1.4 覆盖率阈值

| 阈值范围 | 动作 |
|----------|------|
| ≥ 80% | 通过 |
| 70% – 79% | 警告（报表面板标黄） |
| < 70% | **阻断**（`--cov-fail-under=70`） |

> 注意：`main.py` 和 `tests/` 自身不计入核心覆盖率。

---

## 2. 测试失败快速排查树

```
pytest 失败
│
├─ ImportError / ModuleNotFoundError
│  ├─ pip install -r system/requirements-test.txt
│  ├─ 从 project root 运行（PYTHONPATH 包含 system/）
│  └─ 检查 `conftest.py` 中 sys.path 插入
│
├─ AssertionError
│  ├─ 检查 fixture 数据与函数实际行为是否一致
│  │   例：match_brand 返回 (brand, keyword) 而非 (brand, bool)
│  ├─ 数据库测试：使用 `_direct_insert()` 绕过 worker 队列
│  ├─ 时间过滤器：`get_articles(hours=24)` 默认过滤旧数据
│  │   修复：使用 `datetime.now()` 动态生成 created_at
│  └─ 内容过滤器：`is_digest()`/`is_financial_brief()` 依赖正则模式
│       修复：以代码实际声明为准，不用猜测模式
│
├─ RuntimeError / EventLoopClosed
│  ├─ pytest-asyncio 版本兼容（≥ 0.23 与 pytest 9.x）
│  ├─ fixture 必须用 @pytest_asyncio.fixture（非 @pytest.fixture）
│  └─ 检查是否混用 thread + async（Windows 事件循环差异）
│
├─ pytest-benchmark 失败
│  ├─ 未安装：pip install pytest-benchmark
│  └─ 跳过：pytest -m "not performance"
│
├─ VCR cassette 未找到
│  ├─ 首次需 --record-mode=once（需网络）
│  └─ CI 中 schedule 触发时自动重录
│
├─ CoverageFailure（总覆盖率 < 70%）
│  ├─ 检查是否新增了大段未测代码
│  ├─ 忽略 test_v3.py / test_v51.py 等旧文件
│  └─ 在 pytest.ini 的 --ignore 中排除
│
└─ 超时（timeout > 120s）
   ├─ 数据库测试过多：每个 in_memory_db 耗时 ~2s
   ├─ 使用 --ignore 跳过不再需要的旧测试
   └─ 考虑使用 --durations=10 找出最慢用例
```

---

## 3. CI 失败标准修复流程

```
Step 1: 查看失败日志
  └─ GitHub Actions → 对应 Job → 展开失败步骤
  └─ 定位具体文件和行号

Step 2: 本地复现
  └─ cd /opt/weibo-hotsearch
  └─ pip install -r system/requirements-test.txt
  └─ pytest 失败用例路径::函数名 -v --tb=long

Step 3: 修复
  ├─ 测试期望错误 → 修正测试断言
  ├─ 代码行为错误 → 修正业务逻辑
  └─ 环境差异（Windows vs Linux） → 调整路径/编码

Step 4: 验证全量
  └─ pytest --ignore=system/tests/test_v3.py ... -v

Step 5: 提交 & 推送
  └─ git add -A && git commit -m "fix: ..."
  └─ git push origin main
  └─ 等待 CI 绿标
```

---

## 4. 调度健康检查与心跳检测

### 4.1 一键检查

```bash
# 单次运行
bash system/services/health_check.sh

# 持续监控（每 5 分钟检查一次）
bash system/services/health_check.sh --daemon 300
```

### 4.2 crontab 集成

```cron
# /etc/cron.d/weibo-health
*/5 * * * * root bash /opt/weibo-hotsearch/system/services/health_check.sh >> /var/log/weibo-health.log 2>&1
```

### 4.3 systemd 定时器（替代 crond）

```ini
# /etc/systemd/system/weibo-health.timer
[Unit]
Description=weibo-hotsearch 心跳检测定时器

[Timer]
OnCalendar=*-*-* *:00/5
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/weibo-health.service
[Unit]
Description=weibo-hotsearch 心跳检测
After=network.target

[Service]
Type=oneshot
ExecStart=/opt/weibo-hotsearch/system/services/health_check.sh
```

### 4.4 检查项速查

| 序号 | 检查项 | 失败级别 | 失败后果 | 修复方式 |
|------|--------|---------|---------|---------|
| 1 | 进程 PID | CRITICAL | 服务未运行 | `bash system/services/deploy.sh` |
| 2 | 端口 8001 | CRITICAL | API 不可达 | 检查进程是否绑定正确端口 |
| 3 | API /status | CRITICAL | 内部状态不明 | 检查 main.py 日志 |
| 4 | 调度任务数 | WARNING | 采集器停止 | 检查 scheduler 初始化 |
| 5 | 数据库文件 | WARNING | 数据丢失风险 | 检查磁盘空间/权限 |
| 6 | 日志 ERROR | WARNING | 存在异常 | 查看 ERROR 上下文 |

---

## 5. 线上监控方案与埋点

### 5.1 关键埋点位置

在 `main.py` 和采集器中添加以下埋点（使用 `observability.log_trace`）：

| 埋点 | 位置 | 监控指标 | 告警阈值 |
|------|------|---------|---------|
| `collect.request` | 采集器入口 | 请求总数、成功数 | 成功率 < 90% |
| `collect.parse` | HTML/JSON 解析 | 解析失败数、空结果 | 失败率 > 10% |
| `collect.selectors` | 选择器命中率 | 各选择器匹配计数 | 命中数骤降 > 50% |
| `collect.status_code` | HTTP 响应 | 403/5xx 计数 | 403 > 5/min |
| `db.write_latency` | database.enqueue | 写入延迟（ms） | P99 > 500ms |
| `db.queue_size` | database 队列 | 队列积压数 | > 100 |
| `scheduler.run` | 每个 job 执行 | 执行耗时、失败数 | 失败 > 3/次 |
| `memory.rss` | 进程级别 | RSS 内存 | > 500MB |
| `heartbeat.ts` | /status 接口 | 最后心跳时间 | > 5min 无心跳 |

### 5.2 Prometheus + Grafana（推荐）

```yaml
# prometheus.yml — 采集器配置
scrape_configs:
  - job_name: 'weibo-hotsearch'
    scrape_interval: 15s
    # 通过 /metrics exporter 暴露（需挂载 Prometheus 客户端）
    static_configs:
      - targets: ['localhost:8001']
```

Grafana 仪表盘推荐配置：

```json
{
  "title": "weibo-hotsearch 运行大盘",
  "panels": [
    {"title": "请求成功率", "type": "graph", "target": "rate(collect_request_total[5m])"},
    {"title": "解析失败率", "type": "graph", "target": "rate(collect_parse_fail_total[5m])"},
    {"title": "内存趋势",  "type": "graph", "target": "process_resident_memory_bytes"},
    {"title": "数据库队列", "type": "gauge", "target": "db_queue_size"},
    {"title": "调度执行耗时", "type": "heatmap", "target": "scheduler_run_duration_seconds_bucket"}
  ]
}
```

> **轻量替代方案**：若不想部署 Prometheus，可改方案：
> - 阿里云 ARMS / 腾讯云 CM：日志关键词监控
> - 直接解析 `logs/main.log` 生成指标（见 health_check.sh）
> - `crontab` 定时 curl /status 推送到飞书图表卡片

### 5.3 内存泄漏检测

```bash
# 方案 A: tracemalloc（Python 内置）
python -X tracemalloc system/main.py

# 方案 B: objgraph 快照对比
python3 -c "
import objgraph, gc
objgraph.show_growth(limit=15)
# 运行一段时间后再次调用，对比新增对象
"

# 方案 C: memray（推荐，火焰图）
pip install memray
memray run -o /tmp/weibo-mem.bin system/main.py
memray flamegraph /tmp/weibo-mem.bin
```

### 5.4 async 任务池调优建议

```yaml
# 当前问题: 采集器使用 asyncio.Queue + 单 worker → 写入成为瓶颈
# 优化方向:
collectors:
  semaphore: 10             # 并发控制，避免被限流
  connection_limit: 20      # TCPConnector(limit=20)
  dns_cache_ttl: 300        # DNS 缓存 5 分钟
  timeout:
    connect: 10             # 连接超时 10s
    read: 30                # 读取超时 30s

database:
  worker_count: 2           # 数据库写入 worker（当前单 worker）
  queue_maxsize: 500         # 队列最大积压
```

---

## 6. 反爬应对策略与告警模板

### 6.1 选择器失效自动检测

在采集器解析层添加以下逻辑（以 `web_scraper.py` 为例）：

```python
# ── 启动时注册选择器签名 ──
SELECTOR_SIGNATURES = {
    'sina_news': {
        'title': {'css': 'h1.article-title', 'min_matches': 1, 'critical': True},
        'content': {'css': 'div.article-content p', 'min_matches': 3, 'critical': True},
        'time': {'css': 'time.pub-date', 'min_matches': 1, 'critical': False},
    },
    'weibo_hotsearch': {
        'items': {'css': 'table.s-table tr', 'min_matches': 10, 'critical': True},
    },
}

def validate_selectors(html: str, source_name: str) -> dict:
    """验证选择器命中率，返回报告"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'lxml')
    sigs = SELECTOR_SIGNATURES.get(source_name, {})
    report = {'source': source_name, 'passed': True, 'failures': []}
    for field, config in sigs.items():
        elements = soup.select(config['css'])
        count = len(elements)
        if count < config['min_matches']:
            report['passed'] = False
            report['failures'].append({
                'field': field,
                'expected': config['min_matches'],
                'actual': count,
                'critical': config['critical'],
            })
    return report
```

### 6.2 异常状态码响应策略

```python
# ── 状态码驱逐机制 ──
STATUS_CODE_ACTIONS = {
    403: {'action': 'rotate_ua', 'cooldown': 300},   # User-Agent 轮换
    429: {'action': 'backoff', 'cooldown': 600},      # 指数退避
    503: {'action': 'retry', 'cooldown': 60},          # 自动重试
    520: {'action': 'fallback', 'cooldown': 300},      # 降级到备用 URL
}

# ── 指数退避重试 ──
async def fetch_with_backoff(url: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            resp = await session.get(url, timeout=aiohttp.ClientTimeout(total=30))
            if resp.status == 200:
                return await resp.text()
            elif resp.status in STATUS_CODE_ACTIONS:
                action = STATUS_CODE_ACTIONS[resp.status]
                await asyncio.sleep(action['cooldown'] * (2 ** attempt))
            else:
                resp.raise_for_status()
        except aiohttp.ClientError as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)
```

### 6.3 告警模板

#### 飞书卡片（推荐）

```json
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": {"tag": "plain_text", "content": "⚠️ weibo-hotsearch 告警通知"},
      "template": "red"
    },
    "elements": [
      {"tag": "div", "text": {"tag": "lark_md", "content": "**级别**: {{level}}\n**时间**: {{timestamp}}\n**模块**: {{module}}"}},
      {"tag": "hr"},
      {"tag": "div", "text": {"tag": "lark_md", "content": "**详情**:\n{{message}}"}},
      {"tag": "hr"},
      {"tag": "action", "actions": [
        {"tag": "button", "text": {"tag": "plain_text", "content": "查看日志"}, "url": "ssh://{{host}}/opt/weibo-hotsearch/logs/main.log"},
        {"tag": "button", "text": {"tag": "plain_text", "content": "忽略"}, "type": "default"}
      ]}
    ]
  }
}
```

#### 钉钉 Markdown

```json
{
  "msgtype": "markdown",
  "markdown": {
    "title": "⚠️ weibo-hotsearch 采集器告警",
    "text": "### ⚠️ 采集器告警\n\n**级别**: {{level}}\n**时间**: {{timestamp}}\n**模块**: {{module}}\n\n> {{message}}\n\n---\n🔗 [查看日志](ssh://{{host}}/opt/weibo-hotsearch/logs/main.log)"
  }
}
```

#### 企业微信

```json
{
  "msgtype": "markdown",
  "markdown": {
    "content": "⚠️ **weibo-hotsearch 采集器告警**\n>级别: {{level}}\n>时间: {{timestamp}}\n>模块: {{module}}\n>详情: {{message}}\n\n[查看日志](ssh://{{host}}/opt/weibo-hotsearch/logs/main.log)"
  }
}
```

### 6.4 告警触发规则

| 告警名称 | 触发条件 | 级别 | 频率限制 |
|---------|---------|------|---------|
| `selector_stale` | 某源选择器命中量 < 阈值 × 0.5 | P1 | 30min |
| `http_403_surge` | 5min 内 403 > 10 次 | P1 | 15min |
| `http_5xx_surge` | 5min 内 5xx > 5 次 | P2 | 15min |
| `parse_failure` | 解析失败率 > 20% | P2 | 30min |
| `empty_result` | 采集结果为空 | P2 | 1h |
| `scheduler_silent` | 某 job 超过 2 倍间隔未执行 | P2 | 1h |
| `memory_high` | RSS > 500MB | P3 | 1h |
| `db_queue_full` | 队列积压 > 100 | P3 | 30min |

---

## 7. 附录：命令速查表

```bash
# ── 本地测试 ──
pytest -m "not network and not performance" -v          # 离线单元测试
pytest --ignore=system/tests/test_v3.py -v              # 忽略旧文件
pytest -k "brand_matcher or scoring" -v                 # 按模块筛选
pytest --durations=10                                    # 找出最慢的 10 个用例
pytest --record-mode=once system/tests/test_integration.py  # 录制 VCR

# ── 覆盖率 ──
pytest --cov=system --cov-report=html --cov-fail-under=70  # HTML 报告
coverage report -m --skip-covered                           # CLI 详情

# ── 静态检查 ──
ruff check system/ --fix                                  # 自动修复
black system/ --line-length=100                           # 格式化
mypy system/processor/scoring.py --ignore-missing-imports # 类型检查

# ── 部署 ──
bash system/services/deploy.sh                            # nohup 部署
bash system/services/health_check.sh                      # 健康检查
bash system/services/diagnose.sh                          # 全面诊断

# ── VCR 录制管理 ──
ls system/tests/cassettes/                                # 查看录制文件
# 删除并重新录制：
rm -rf system/tests/cassettes/
pytest system/tests/test_integration.py --record-mode=once
```