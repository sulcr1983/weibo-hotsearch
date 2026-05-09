"""邮件SMTP推送"""
import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header

from templates.email_daily import render_daily_email
from templates.email_weekly import render_weekly_email
from templates.email_monthly import render_monthly_email
from v2.logger import get_logger

logger = get_logger('email')


def _send_sync(sender: str, pw: str, recipients: list, server: str, port: int, subject: str, html: str):
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = ','.join(recipients)
    msg['Subject'] = Header(subject, 'utf-8')
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    with smtplib.SMTP(server, port, timeout=30) as s:
        try:
            s.starttls()
        except smtplib.SMTPNotSupportedError:
            pass
        s.login(sender, pw)
        s.sendmail(sender, recipients, msg.as_string())
    logger.info(f"邮件发送成功: {subject}")


class Emailer:
    def __init__(self, sender: str, pw: str, recipients: list, server: str = 'smtp.qq.com', port: int = 587):
        self.sender = sender
        self.pw = pw
        self.recipients = recipients
        self.server = server
        self.port = port

    def _send(self, subject: str, html: str):
        if not self.sender or not self.pw:
            return
        try:
            _send_sync(self.sender, self.pw, self.recipients, self.server, self.port, subject, html)
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")

    async def send_daily(self, report: dict):
        h = render_daily_email(report.get('weibo', []), report.get('news', []), report.get('date', ''), report.get('generated_at', ''))
        await asyncio.to_thread(self._send, '昨日汽车行业舆情热点新闻', h)

    async def send_weekly(self, report: dict):
        h = render_weekly_email(
            report.get('week_start', ''), report.get('week_end', ''),
            report.get('ai_summary', ''), report.get('by_brand', {}),
            report.get('total_items', 0), report.get('generated_at', ''))
        ws = report.get('week_start', '')[5:]
        we = report.get('week_end', '')[5:]
        await asyncio.to_thread(self._send, f'上周汽车行业10个品牌舆情汇总 {ws}-{we}', h)

    async def send_monthly(self, report: dict):
        h = render_monthly_email(report)
        await asyncio.to_thread(self._send, f'微博月度舆情报告 {report.get("label","")}', h)
