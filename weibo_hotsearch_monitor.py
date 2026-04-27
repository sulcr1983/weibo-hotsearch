#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汽车品牌微博热搜监控系统
功能：自动监控微博热搜并筛选特定汽车品牌，支持AI清洗、飞书与邮件推送
技术栈：Python + FastAPI + SQLite + APScheduler
"""

import re
import os
import logging
from logging.handlers import TimedRotatingFileHandler
import asyncio
import smtplib
from datetime import datetime, timedelta
import aiohttp
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from fastapi import FastAPI
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from tenacity import retry, stop_after_attempt, wait_exponential

# 配置日志系统
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, 'monitor.log')

logger = logging.getLogger('weibo_hotsearch')
logger.setLevel(logging.INFO)
logger.propagate = False  # 防止日志向上冒泡给Uvicorn

# 防止重复添加Handler
if not logger.handlers:
    # 配置TimedRotatingFileHandler
    handler = TimedRotatingFileHandler(
        LOG_FILE,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

    # 添加控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)

# 导入配置
from config import (
    DATABASE_PATH, WEIBO_HOTSEARCH_URL, WEIBO_COOKIE,
    AI_API_KEY, AI_API_URL, AI_MODEL,
    FEISHU_WEBHOOK_URL,
    EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENTS,
    SMTP_SERVER, SMTP_PORT
)
import aiosqlite

# 品牌匹配规则
BRAND_PATTERNS = [
    ("鸿蒙智行", ["问界", "智界", "尊界", "享界", "尚界"]),
    ("蔚来", ["蔚来", "萤火虫", "乐道"]),
    ("比亚迪", ["比亚迪", "仰望", "腾势", "方程豹"]),
    ("其他", ["小米汽车", "零跑", "理想", "极氪", "阿维塔", "智己", "特斯拉"])
]

# 构建品牌正则表达式
BRAND_REGEX = {}
for brand_group, keywords in BRAND_PATTERNS:
    pattern = "|".join([re.escape(keyword) for keyword in keywords])
    BRAND_REGEX[brand_group] = re.compile(pattern, re.IGNORECASE)


async def init_database():
    """初始化数据库，创建weibo_hot_search表"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute('''
            CREATE TABLE IF NOT EXISTS weibo_hot_search (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand_group TEXT,
                keyword TEXT,
                title TEXT,
                link TEXT,
                created_at TEXT,
                is_pushed INTEGER DEFAULT 0,
                source TEXT DEFAULT 'weibo'
            )
            ''')

            try:
                await db.execute('ALTER TABLE weibo_hot_search ADD COLUMN source TEXT DEFAULT \'weibo\'')
            except Exception:
                pass

            await db.commit()
        logger.info("数据库初始化成功")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")


async def save_to_database(brand_group, keyword, title, link, source='weibo'):
    """保存热搜数据到数据库"""
    try:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "INSERT INTO weibo_hot_search (brand_group, keyword, title, link, created_at, is_pushed, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (brand_group, keyword, title, link, created_at, 0, source)
            )
            await db.commit()
        logger.info(f"保存数据成功: {brand_group} - {title}")
    except Exception as e:
        logger.error(f"保存数据失败: {e}")


def match_brand(title):
    """匹配品牌，返回品牌组和匹配的关键词"""
    for brand_group, regex in BRAND_REGEX.items():
        match = regex.search(title)
        if match:
            return brand_group, match.group(0)
    return None, None


async def get_past_24h_hotsearch():
    """获取过去24小时的热搜数据"""
    try:
        past_24h = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT * FROM weibo_hot_search WHERE created_at >= ? AND is_pushed = 0 ORDER BY created_at DESC",
                (past_24h,)
            ) as cursor:
                results = await cursor.fetchall()
                # 转换为字典列表
                rows = []
                for row in results:
                    # 处理可能的字段长度差异
                    row_dict = {
                        'id': row[0],
                        'brand_group': row[1],
                        'keyword': row[2],
                        'title': row[3],
                        'link': row[4],
                        'created_at': row[5],
                        'is_pushed': row[6]
                    }
                    # 如果有source字段，添加它
                    if len(row) > 7:
                        row_dict['source'] = row[7]
                    rows.append(row_dict)
        return rows
    except Exception as e:
        logger.error(f"获取过去24小时热搜数据失败: {e}")
        return []

# 初始化调度器
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动阶段
    await init_database()

    # 添加定时任务，每小时执行一次
    scheduler.add_job(
        scheduled_task,
        trigger=IntervalTrigger(hours=1),
        id="weibo_hotsearch_task",
        name="微博热搜抓取任务",
        replace_existing=True
    )

    # 添加每日汇总任务，每天早上8:00执行
    scheduler.add_job(
        daily_push_task,
        trigger=CronTrigger(hour=9, minute=0),
        id="daily_push_task",
        name="每日汇总推送任务",
        replace_existing=True
    )

    scheduler.start()
    logger.info("调度器启动成功")

    await fetch_weibo_hotsearch()

    yield

    # 清理阶段
    scheduler.shutdown()
    logger.info("调度器已关闭")


# 初始化FastAPI应用
app = FastAPI(
    title="汽车品牌微博热搜监控系统",
    description="自动监控微博热搜并筛选特定汽车品牌",
    version="1.0.0",
    lifespan=lifespan
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def ai_clean_hotsearch(hotsearch_list):
    """使用AI清洗热搜数据（智谱清言）"""
    if not hotsearch_list:
        return []

    if not AI_API_KEY:
        logger.warning("AI API Key未配置，跳过AI清洗")
        return hotsearch_list

    try:
        prompt = f"请帮我清洗以下汽车品牌相关的微博热搜数据，剔除琐碎负面或无关八卦（如车主吵架、单纯交通意外），保留企业动向、新车发布、销量等有价值信息。\n\n"

        for i, item in enumerate(hotsearch_list, 1):
            prompt += f"{i}. {item['title']}\n"

        prompt += "\n请返回保留的热搜序号列表，格式为逗号分隔的数字，例如：1,3,5"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AI_API_KEY}"
        }

        data = {
            "model": AI_MODEL,
            "messages": [
                {"role": "system", "content": "你是一个专业的汽车行业分析师，擅长筛选有价值的行业信息。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(AI_API_URL, headers=headers, json=data, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    result = await response.json()
                    choices = result.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        selected_indices = []
                        numbers = re.findall(r'\d+', content)
                        for num_str in numbers:
                            try:
                                index = int(num_str) - 1
                                if 0 <= index < len(hotsearch_list):
                                    selected_indices.append(index)
                            except:
                                pass
                        selected_indices = list(dict.fromkeys(selected_indices))
                        return [hotsearch_list[i] for i in selected_indices]
                    return hotsearch_list
                else:
                    error_text = await response.text()
                    logger.error(f"调用AI API失败，状态码: {response.status}, 响应: {error_text}")
                    raise Exception(f"AI API调用失败: {response.status}")
    except Exception as e:
        logger.error(f"AI清洗异常: {e}")
        raise


async def send_feishu_card(hotsearch_list, yesterday_date):
    """发送飞书卡片消息（极简信息流风格，带时间维度）"""
    if not FEISHU_WEBHOOK_URL:
        return

    try:
        elements = []
        
        if not hotsearch_list:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"📭 昨日暂无关注的品牌热搜"
                }
            })
        else:
            # 汇总说明
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"💡 这是昨天（{yesterday_date}）全天 24 小时采集到的汽车品牌热搜汇总报告。"
                }
            })
            
            elements.append({"tag": "hr"})
            
            # 热搜列表：[HH:mm] [品牌名] 标题(链接)
            for item in hotsearch_list:
                created_time = item.get('created_at', '')[:16]  # 格式：YYYY-MM-DD HH:mm
                time_part = created_time[11:16] if len(created_time) >= 16 else ''
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"[{time_part}] [{item['brand_group']}] [{item['title']}]({item['link']})"
                    }
                })
        
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"<font color=\"#cccccc\">生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</font>"
            }
        })

        data = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "🚗 汽车品牌热搜日报"
                    },
                    "template": "wathet"
                },
                "elements": elements
            }
        }

        headers = {
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(FEISHU_WEBHOOK_URL, headers=headers, json=data, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    logger.info("飞书推送成功")
                else:
                    error_text = await response.text()
                    logger.error(f"飞书推送失败，状态码: {response.status}, 响应: {error_text}")
    except Exception as e:
        logger.error(f"飞书推送异常: {e}")


def _send_email_sync(hotsearch_list, yesterday_date):
    """同步发送邮件的内部函数（极简信息流风格，带时间维度）"""
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date_str = datetime.now().strftime("%Y-%m-%d")

        if not hotsearch_list:
            html_content = f"""
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>汽车品牌热搜日报</title>
            </head>
            <body style="margin: 0; padding: 0; background-color: #ffffff; font-family: 'Microsoft YaHei', Arial, sans-serif;">
                <div style="max-width: 600px; margin: 0 auto; padding: 30px 20px;">
                    <h1 style="color: #1a1a1a; font-size: 20px; font-weight: bold; margin-bottom: 20px;">🚗 汽车品牌热搜日报</h1>
                    
                    <p style="color: #666666; font-size: 13px; line-height: 1.8; margin-bottom: 25px;">您好！以下是系统为您汇总的昨日全天汽车热搜动向：</p>
                    
                    <p style="color: #999999; font-size: 14px; line-height: 1.8;">📭 昨日暂无关注的品牌热搜</p>
                    
                    <div style="margin-top: 50px; padding-top: 20px; border-top: 1px solid #eeeeee;">
                        <p style="color: #cccccc; font-size: 12px; line-height: 1.8;">生成时间：{current_time}</p>
                    </div>
                </div>
            </body>
            </html>
            """
        else:
            # 带时间维度的汇总说明
            summary_intro = f"💡 这是昨天（{yesterday_date}）全天 24 小时采集到的汽车品牌热搜汇总报告。"
            
            html_content = f"""
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>汽车品牌热搜日报</title>
            </head>
            <body style="margin: 0; padding: 0; background-color: #ffffff; font-family: 'Microsoft YaHei', Arial, sans-serif;">
                <div style="max-width: 600px; margin: 0 auto; padding: 30px 20px;">
                    <h1 style="color: #1a1a1a; font-size: 20px; font-weight: bold; margin-bottom: 20px;">🚗 汽车品牌热搜日报</h1>
                    
                    <p style="color: #666666; font-size: 13px; line-height: 1.8; margin-bottom: 25px;">您好！以下是系统为您汇总的昨日全天汽车热搜动向：</p>
                    <p style="color: #666666; font-size: 13px; line-height: 1.8; margin-bottom: 25px;">{summary_intro}</p>
                    
                    <div style="margin-bottom: 20px;">
            """

            # 热搜列表：[HH:mm] [品牌名] 标题
            for item in hotsearch_list:
                created_time = item.get('created_at', '')[:16]
                time_part = created_time[11:16] if len(created_time) >= 16 else ''
                html_content += f"""
                        <div style="border-bottom: 1px solid #eeeeee; padding: 12px 0;">
                            <a href="{item['link']}" target="_blank" style="text-decoration: none;">
                                <span style="color: #999999; font-size: 12px;">[{time_part}]</span>
                                <span style="color: #666666; font-size: 13px;">[{item['brand_group']}]</span>
                                <span style="color: #1a1a1a; font-size: 14px; font-weight: bold; text-decoration: none;">{item['title']}</span>
                            </a>
                        </div>
                """

            html_content += f"""
                    </div>
                    
                    <div style="margin-top: 50px; padding-top: 20px; border-top: 1px solid #eeeeee;">
                        <p style="color: #cccccc; font-size: 12px; line-height: 1.8;">生成时间：{current_time}</p>
                    </div>
                </div>
                
                <style>
                    a:hover span {{ text-decoration: underline; }}
                </style>
            </body>
            </html>
            """

        message = MIMEMultipart()
        message["From"] = EMAIL_SENDER
        message["To"] = ",".join(EMAIL_RECIPIENTS)
        message["Subject"] = Header(f"汽车品牌热搜日报 - {date_str}", "utf-8")

        message.attach(MIMEText(html_content, "html", "utf-8"))

        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
                try:
                    server.starttls()
                    logger.info("SMTP TLS连接建立成功")
                except smtplib.SMTPNotSupportedError as e:
                    logger.warning(f"SMTP服务器不支持TLS: {e}")
                except Exception as e:
                    logger.error(f"SMTP TLS连接失败: {e}")
                    raise
                
                try:
                    server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                    logger.info("SMTP登录成功")
                except smtplib.SMTPAuthenticationError as e:
                    logger.error(f"SMTP认证失败，请检查邮箱账号和授权码: {e}")
                    raise
                except smtplib.SMTPException as e:
                    logger.error(f"SMTP登录异常: {e}")
                    raise
                
                try:
                    server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENTS, message.as_string())
                    logger.info("邮件发送成功")
                except smtplib.SMTPRecipientsRefused as e:
                    logger.error(f"邮件收件人被拒绝: {e}")
                    raise
                except smtplib.SMTPSenderRefused as e:
                    logger.error(f"邮件发件人被拒绝: {e}")
                    raise
                except smtplib.SMTPException as e:
                    logger.error(f"邮件发送异常: {e}")
                    raise
        except smtplib.SMTPConnectError as e:
            logger.error(f"SMTP连接失败，请检查SMTP服务器地址和端口: {e}")
            raise
        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"SMTP服务器断开连接: {e}")
            raise
        except Exception as e:
            logger.error(f"邮件发送异常: {e}")
            raise
    except Exception as e:
        logger.error(f"邮件构建异常: {e}")
        raise


async def send_email_summary(hotsearch_list, yesterday_date):
    """发送邮件汇总（极简信息流风格，带时间维度）"""
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECIPIENTS:
        return

    await asyncio.to_thread(_send_email_sync, hotsearch_list, yesterday_date)


async def mark_as_pushed(hotsearch_list):
    """标记热搜数据为已推送"""
    if not hotsearch_list:
        return

    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            for item in hotsearch_list:
                await db.execute(
                    "UPDATE weibo_hot_search SET is_pushed = 1 WHERE id = ?",
                    (item['id'],)
                )
            await db.commit()
        logger.info("标记已推送成功")
    except Exception as e:
        logger.error(f"标记已推送失败: {e}")


async def clean_old_data():
    """清理7天前的历史数据"""
    try:
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                "DELETE FROM weibo_hot_search WHERE created_at < ?",
                (seven_days_ago,)
            )
            deleted_count = cursor.rowcount
            await db.commit()
        logger.info(f"清理7天前的历史数据成功，删除了 {deleted_count} 条记录")
    except Exception as e:
        logger.error(f"清理历史数据失败: {e}")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), reraise=True)
async def fetch_weibo_hotsearch():
    """抓取微博热搜数据"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cookie": WEIBO_COOKIE,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(WEIBO_HOTSEARCH_URL, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # 解析 <td class="td-02"> 中的 <a> 标签
                    td_elements = soup.find_all('td', class_='td-02')
                    hotsearch_list = []

                    for td in td_elements:
                        a_tag = td.find('a')
                        if a_tag and a_tag.get('href'):
                            title = a_tag.get_text(strip=True)
                            link = "https://s.weibo.com" + a_tag['href']
                            if title:
                                hotsearch_list.append((title, link))

                    logger.info(f"抓取微博热搜成功，共获取 {len(hotsearch_list)} 条热搜")

                    # 处理抓取到的数据
                    for title, link in hotsearch_list:
                        brand_group, keyword = match_brand(title)
                        if brand_group:
                            await save_to_database(brand_group, keyword, title, link, source='weibo')
                else:
                    error_text = await response.text()
                    logger.error(f"抓取微博热搜失败，状态码: {response.status}, 响应: {error_text}")
                    raise Exception(f"微博抓取失败: {response.status}")
    except Exception as e:
        logger.error(f"抓取微博热搜异常: {e}")
        raise


async def scheduled_task():
    """定时任务函数"""
    logger.info(f"执行定时任务: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await fetch_weibo_hotsearch()


async def fetch_trendradar_data():
    """从TrendRadar获取舆情数据"""
    # TODO: 实现TrendRadar数据抓取逻辑
    # 1. 调用TrendRadar API获取数据
    # 2. 解析返回的数据结构
    # 3. 提取相关的汽车品牌信息
    # 4. 保存到数据库，source='trendradar'
    logger.info("TrendRadar数据抓取功能待实现")
    return []


async def daily_push_task():
    """每日汇总推送任务（严格分离采集与推送）"""
    yesterday_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    hotsearch_list = await get_past_24h_hotsearch()
    
    if hotsearch_list:
        try:
            cleaned_list = await ai_clean_hotsearch(hotsearch_list)
        except Exception as e:
            logger.error(f"AI清洗失败，使用原始数据推送: {e}")
            cleaned_list = hotsearch_list
        
        if cleaned_list:
            await send_feishu_card(cleaned_list, yesterday_date)
            await send_email_summary(cleaned_list, yesterday_date)
            await mark_as_pushed(cleaned_list)
    else:
        await send_feishu_card([], yesterday_date)
        await send_email_summary([], yesterday_date)
    
    await clean_old_data()


@app.get("/", summary="首页")
async def root():
    """返回系统状态"""
    return {
        "status": "running",
        "message": "汽车品牌微博热搜监控系统运行中",
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


@app.get("/hotsearch", summary="获取热搜数据")
async def get_hotsearch(brand_group: str = None, limit: int = 50):
    """获取热搜数据，可按品牌组筛选"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            if brand_group:
                async with db.execute(
                    "SELECT * FROM weibo_hot_search WHERE brand_group = ? ORDER BY created_at DESC LIMIT ?",
                    (brand_group, limit)
                ) as cursor:
                    results = await cursor.fetchall()
            else:
                async with db.execute(
                    "SELECT * FROM weibo_hot_search ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ) as cursor:
                    results = await cursor.fetchall()
            
            # 转换为字典列表
            rows = []
            for row in results:
                rows.append({
                    'id': row[0],
                    'brand_group': row[1],
                    'keyword': row[2],
                    'title': row[3],
                    'link': row[4],
                    'created_at': row[5],
                    'is_pushed': row[6]
                })

        return {
            "status": "success",
            "data": rows,
            "count": len(rows)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"获取数据失败: {e}"
        }


if __name__ == "__main__":
    import uvicorn
    logger.info("正在启动应用...")
    try:
        uvicorn.run(
            "weibo_hotsearch_monitor:app",
            host="127.0.0.1",
            port=8002,
            reload=True
        )
    except Exception as e:
        logger.exception(f"启动应用时发生错误: {e}")