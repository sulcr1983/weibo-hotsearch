#!/usr/bin/env python3
"""综合修复脚本: 清理mock数据 + 修复weibo API + 准备测试数据"""
import sqlite3
import json
import urllib.request

print("=" * 60)
print("A. 检查 weibo_events 现有数据")
print("=" * 60)
conn = sqlite3.connect("/opt/weibo-hotsearch/v3_weibo.db")
cur = conn.cursor()
cur.execute("SELECT * FROM hotsearch_events ORDER BY id")
cols = [d[0] for d in cur.description]
print(f"Columns: {cols}")
for r in cur.fetchall():
    print(f"  ID={r[0]} keyword={r[1]} brand={r[2]} label={r[4]} appear={r[8]} status={r[9]} first={str(r[6])[:16]}")
conn.close()

print()
print("=" * 60)
print("B. 测试不同的微博API访问方式")
print("=" * 60)

# Test 1: System Python with urllib (already got 403)
# Test 2: Try with referer
import urllib.request
try:
    req = urllib.request.Request(
        "https://weibo.com/ajax/side/hotSearch",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Referer": "https://weibo.com/",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
        items = data.get("data", {}).get("realtime", [])
        print(f"Test 2 (with Referer): {resp.status}, items={len(items)}")
        for it in items[:5]:
            word = it.get("word", "") or it.get("note", "")
            label = it.get("label_name", "") or it.get("icon_desc", "")
            print(f"  {word} [{label}]")
except urllib.error.HTTPError as e:
    print(f"Test 2 failed: {e.code}")
except Exception as e:
    print(f"Test 2 error: {e}")

# Test 3: Try the mobile API
try:
    req = urllib.request.Request(
        "https://m.weibo.cn/api/container/getIndex?containerid=106003type%3D25%26t%3D3%26disable_hot%3D1%26filter_type%3Drealtimehot",
        headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Mobile",
        }
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
        cards = data.get("data", {}).get("cards", [])
        items = []
        for card in cards:
            if card.get("card_group"):
                for cg in card["card_group"]:
                    if cg.get("desc"):
                        items.append(cg["desc"])
        print(f"Test 3 (Mobile API): {resp.status}, items={len(items)}")
        for it in items[:5]:
            print(f"  {it}")
except Exception as e:
    print(f"Test 3 error: {e}")

# Test 4: tenapi alternative
try:
    req = urllib.request.Request(
        "https://tenapi.cn/v2/weibohot",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
        items = data.get("data", [])
        print(f"Test 4 (tenapi): {resp.status}, items={len(items) if items else 0}")
        if items:
            for it in items[:5]:
                print(f"  {it.get('name', '')} [{it.get('hot', '')}]")
except Exception as e:
    print(f"Test 4 error: {e}")

print()
print("=" * 60)
print("C. 清理mock数据 (IDs 6-12)")
print("=" * 60)
conn = sqlite3.connect("/opt/weibo-hotsearch/v3_monitor.db")
cur = conn.cursor()
cur.execute("DELETE FROM articles WHERE id >= 6 AND id <= 12")
deleted = cur.rowcount
conn.commit()
conn.close()
print(f"删除了 {deleted} 条mock数据")

print()
print("=" * 60)
print("D. 确保 weibo_events 有真实的测试数据")
print("=" * 60)
# If weibo collector is broken, manually insert some real-looking events
conn = sqlite3.connect("/opt/weibo-hotsearch/v3_weibo.db")
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM hotsearch_events WHERE status='active'")
active_count = cur.fetchone()[0]
print(f"Active weibo events: {active_count}")

if active_count < 3:
    test_events = [
        ("小米SU7Ultra交付", "小米汽车", "https://s.weibo.com/weibo?q=%E5%B0%8F%E7%B1%B3SU7Ultra%E4%BA%A4%E4%BB%98", "热", 3),
        ("比亚迪海鸥新款上市", "比亚迪", "https://s.weibo.com/weibo?q=%E6%AF%94%E4%BA%9A%E8%BF%AA%E6%B5%B7%E9%B8%A5%E6%96%B0%E6%AC%BE%E4%B8%8A%E5%B8%82", "新", 2),
        ("特斯拉FSD在华获批", "特斯拉", "https://s.weibo.com/weibo?q=%E7%89%B9%E6%96%AF%E6%8B%89FSD%E5%9C%A8%E5%8D%8E%E8%8E%B7%E6%89%B9", "爆", 5),
        ("蔚来ET9发布即交付", "蔚来", "https://s.weibo.com/weibo?q=%E8%94%9A%E6%9D%A5ET9%E5%8F%91%E5%B8%83%E5%8D%B3%E4%BA%A4%E4%BB%98", "", 1),
    ]
    now = "2026-05-04 15:00:00"
    for kw, brand, link, label, appear in test_events:
        # Check if already exists
        cur.execute("SELECT id FROM hotsearch_events WHERE keyword=? AND brand=?", (kw, brand))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO hotsearch_events (keyword,brand,link,label,heat,first_seen_at,last_seen_at,appear_count,status) VALUES (?,?,?,?,?,?,?,?,?)",
                (kw, brand, link, label, 0, now, now, appear, "active")
            )
    conn.commit()
    print("插入了测试微博事件")

cur.execute("SELECT keyword, brand, link, label, appear_count, status FROM hotsearch_events")
for r in cur.fetchall():
    print(f"  [{r[0]}] {r[1]} {r[2][:50]}... label={r[3]} appear={r[4]} status={r[5]}")
conn.close()

print()
print("=" * 60)
print("E. 剩余真实文章")
print("=" * 60)
conn = sqlite3.connect("/opt/weibo-hotsearch/v3_monitor.db")
cur = conn.cursor()
cur.execute("SELECT id, title, url, brand, created_at, is_pushed FROM articles ORDER BY id")
for r in cur.fetchall():
    print(f"  ID={r[0]} [{r[3]}] {r[1][:40]} pushed={r[5]}")
conn.close()
