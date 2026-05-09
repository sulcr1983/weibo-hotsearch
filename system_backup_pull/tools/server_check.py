#!/usr/bin/env python3
"""上传到服务器执行: 检查数据库和微博API"""
import sqlite3
import json
import urllib.request

print("=" * 60)
print("1. v3_weibo.db 表结构")
print("=" * 60)
conn = sqlite3.connect("/opt/weibo-hotsearch/v3_weibo.db")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print(f"Tables: {tables}")
for tname in tables:
    cur.execute(f"SELECT COUNT(*) FROM [{tname}]")
    cnt = cur.fetchone()[0]
    print(f"  {tname}: {cnt} rows")
conn.close()

print()
print("=" * 60)
print("2. v3_monitor.db 最近文章")
print("=" * 60)
conn = sqlite3.connect("/opt/weibo-hotsearch/v3_monitor.db")
cur = conn.cursor()
cur.execute("SELECT id,title,url,brand,is_pushed,created_at FROM articles ORDER BY id DESC LIMIT 15")
for r in cur.fetchall():
    print(f"  ID={r[0]} [{r[3]}] {r[1][:40]} | pushed={r[4]} | {r[5][:16]}")
    print(f"    URL: {r[2]}")
conn.close()

print()
print("=" * 60)
print("3. 微博API测试")
print("=" * 60)
try:
    req = urllib.request.Request("https://weibo.com/ajax/side/hotSearch", 
                                  headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
        items = data.get("data", {}).get("realtime", [])
        print(f"Total weibo items: {len(items)}")
        for it in items[:8]:
            word = it.get("word", "") or it.get("note", "")
            label = it.get("label_name", "") or it.get("icon_desc", "")
            print(f"  {word} [{label}]")
except Exception as e:
    print(f"Weibo API error: {e}")

print()
print("=" * 60)
print("4. URL可达性测试")
print("=" * 60)
test_urls = [
    "https://www.d1ev.com/news/qiye/297670",
    "https://auto.gasgoo.com/news/202605/1I70456212C501.shtml",
    "https://www.avatr.com/news/forbidden-city",
    "https://www.sohu.com/a/1018195200_114760",
    "https://www.byd.com/cn/news/han-ev-flash-charge",
]
for u in test_urls:
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"  OK {resp.status}: {u[:50]}...")
    except urllib.error.HTTPError as e:
        print(f"  {e.code}: {u[:50]}...")
    except Exception as e:
        print(f"  ERR {e}: {u[:50]}...")
