#!/usr/bin/env python3
"""端到端测试：准备数据 + 触发日报 + 捕获输出供Playwright验证"""
import sqlite3, json, sys, os

sys.path.insert(0, "/opt/weibo-hotsearch/system")

# A. Backdate real articles to yesterday
print("=" * 60)
print("A. 将真实文章日期改为昨天(2026-05-04)")
print("=" * 60)
conn = sqlite3.connect("/opt/weibo-hotsearch/v3_monitor.db")
cur = conn.cursor()
cur.execute("SELECT id, title, created_at FROM articles WHERE id >= 13 AND is_pushed=0")
for r in cur.fetchall():
    old_time = r[2].replace("2026-05-05", "2026-05-04")
    cur.execute("UPDATE articles SET created_at=? WHERE id=?", (old_time, r[0]))
    print(f"  ID={r[0]} → {old_time[:16]}")
conn.commit()

# Reset pushed status to test push
cur.execute("UPDATE articles SET is_pushed=0, push_date=NULL WHERE id >= 13")
conn.commit()
conn.close()

# B. = Build the daily report using actual code =====================
print()
print("=" * 60)
print("B. 使用实际代码构建日报")
print("=" * 60)

from datetime import datetime, timedelta
from reporter.builder import ReportBuilder
from storage.database import Database
from config import DB_PATH as cfg_db, WEIBO_DB_PATH as cfg_weibo

db = Database(cfg_db, cfg_weibo)
# Can't use async in sync context easily, so use raw SQL instead
conn = sqlite3.connect("/opt/weibo-hotsearch/v3_monitor.db")
cur = conn.cursor()
date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
print(f"查询日期: {date}")

cur.execute("SELECT * FROM articles WHERE date(created_at) = ? AND is_pushed=0 ORDER BY score DESC", (date,))
cols = [d[0] for d in cur.description]
articles = [dict(zip(cols, r)) for r in cur.fetchall()]
print(f"新闻文章: {len(articles)} 条")
for a in articles:
    print(f"  [{a['brand']}] {a['title'][:40]} score={a.get('score','?')} url={a.get('url','')[:60]}")

conn.close()

# Weibo events
conn2 = sqlite3.connect("/opt/weibo-hotsearch/v3_weibo.db")
cur2 = conn2.cursor()
cur2.execute("SELECT * FROM hotsearch_events WHERE date(first_seen_at) = ? ORDER BY appear_count DESC", (date,))
cols2 = [d[0] for d in cur2.description]
weibo = [dict(zip(cols2, r)) for r in cur2.fetchall()]
print(f"微博事件: {len(weibo)} 条")
for w in weibo:
    print(f"  [{w['brand']}] {w['keyword']} label={w.get('label','')} appear={w.get('appear_count','')} link={w.get('link','')[:50]}")

conn2.close()

# C. Generate card output
print()
print("=" * 60)
print("C. 生成飞书卡片")
print("=" * 60)
from templates.feishu_cards import render_daily_feishu, _encode_url, _valid_url

generated_at = datetime.now().strftime('%Y-%m-%d %H:%M')
elements = render_daily_feishu(weibo, articles, date, generated_at)

# Extract lark_md content
lark_md_blocks = []
for el in elements:
    tag = el.get("tag", "")
    if tag == "div":
        tb = el.get("text", {})
        if tb.get("tag") == "lark_md":
            lark_md_blocks.append({"tag": tag, "content": tb["content"]})
    elif tag == "note":
        lark_md_blocks.append({"tag": tag, "elements": el.get("elements", [])})

# Save full card JSON for Playwright preview
card_data = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "🚗 昨日汽车行业舆情热点新闻"}, "template": "wathet"},
        "elements": []
    }
}
out = []
for el in elements:
    simplified = {"tag": el["tag"]}
    if el["tag"] == "div" and "text" in el:
        simplified["text"] = {"tag": el["text"]["tag"], "content": el["text"].get("content", "")[:120]}
    elif el["tag"] == "note":
        simplified["content"] = " ".join(ne.get("content", "") for ne in el.get("elements", []))
    out.append(simplified)

with open("/tmp/daily_card_output.json", "w", encoding="utf-8") as f:
    json.dump({
        "card_summary": out,
        "full_card": {
            "header": card_data["card"]["header"],
            "element_count": len(elements),
        },
        "lark_md_contents": [b["content"] for b in lark_md_blocks if b["tag"] == "div"],
        "url_encoding_test": {
            "weibo_links": [
                {"raw": w.get("link", ""), "encoded": _encode_url(w.get("link", ""))} 
                for w in weibo
            ],
            "news_links": [
                {"raw": a.get("url", ""), "encoded": _encode_url(a.get("url", ""))}
                for a in articles[:3]
            ]
        }
    }, f, ensure_ascii=False, indent=2)

print("\n所有 lark_md 区块内容:")
for i, b in enumerate(lark_md_blocks):
    if b["tag"] == "div":
        print(f"\n--- Block #{i+1} ---")
        print(b["content"])

print(f"\nJSON输出已保存到 /tmp/daily_card_output.json")
print("完成!")
