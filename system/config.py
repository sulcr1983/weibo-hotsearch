#!/usr/bin/env python3
"""汽车行业舆情监控 V4.1 — 全局配置 (路径锚点 + 环境变量)"""
import os
from pathlib import Path
from dotenv import load_dotenv

SYSTEM_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SYSTEM_DIR.parent

DATA_DIR = PROJECT_ROOT / 'data'
LOG_DIR = PROJECT_ROOT / 'logs'
TEMPLATES_DIR = SYSTEM_DIR / 'templates'
SERVICES_DIR = SYSTEM_DIR / 'services'

load_dotenv(PROJECT_ROOT / '.env')

DB_PATH = str(PROJECT_ROOT / os.getenv('DB_PATH', 'v3_monitor.db'))
WEIBO_DB_PATH = str(PROJECT_ROOT / os.getenv('WEIBO_DB_PATH', 'v3_weibo.db'))

WEIBO_HOTSEARCH_URL = 'https://s.weibo.com/top/summary'
#   注意：V4.1 weibo_collector 改用 weibo.com/ajax/side/hotSearch（免Cookie）
#   WEIBO_COOKIE 已废弃，保留仅为向后兼容
WEIBO_COOKIE = os.getenv('WEIBO_COOKIE', '')

# AI 总结生成（火山引擎 Ark / doubao-seed）
# 注意：Ark 平台需先在控制台创建 Endpoint（接入点），模型名为 ep-xxxxxxxx-xxxxx 格式
# 详见 https://console.volcengine.com/ark/region:ark+cn-beijing/endpoint
AI_API_KEY = os.getenv('AI_API_KEY', '')
AI_API_URL = os.getenv('AI_API_URL', 'https://ark.cn-beijing.volces.com/api/v3/chat/completions')
AI_MODEL = os.getenv('AI_MODEL', 'ep-0000000000000-xxxxx')

FEISHU_WEBHOOK_URL = os.getenv('FEISHU_WEBHOOK_URL', '')

EMAIL_SENDER = os.getenv('EMAIL_SENDER', '')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
EMAIL_RECIPIENTS = [r.strip() for r in os.getenv('EMAIL_RECIPIENTS', '').split(',') if r.strip()]
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.qq.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))

NEWS_RETENTION_DAYS = 8
WEIBO_RETENTION_DAYS = 30
LOG_RETENTION_DAYS = 8
