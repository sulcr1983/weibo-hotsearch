#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join(BASE_DIR, "weibo_hotsearch.db"))

WEIBO_HOTSEARCH_URL = "https://s.weibo.com/top/summary"
WEIBO_COOKIE = os.getenv("WEIBO_COOKIE", "")

AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_API_URL = os.getenv("AI_API_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
AI_MODEL = os.getenv("AI_MODEL", "glm-4-flash")

FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "")

EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENTS = [r for r in os.getenv("EMAIL_RECIPIENTS", "").split(",") if r.strip()]
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.qq.com")
try:
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
except ValueError:
    SMTP_PORT = 587
