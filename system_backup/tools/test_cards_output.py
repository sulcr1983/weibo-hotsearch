#!/usr/bin/env python3
"""生成飞书卡片JSON + HTML预览，用于Playwright可视化验证"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.feishu_cards import render_daily_feishu, render_weekly_feishu, _encode_url, _valid_url

# ==================== 模拟真实数据 ====================

weibo_data = [
    {"brand": "小米汽车", "keyword": "小米SU7Ultra交付破万", "link": "https://s.weibo.com/weibo?q=小米SU7Ultra交付破万", "label": "热", "appear_count": 3},
    {"brand": "比亚迪", "keyword": "比亚迪海鸥新款上市", "link": "https://s.weibo.com/weibo?q=比亚迪海鸥新款上市", "label": "新", "appear_count": 2},
    {"brand": "特斯拉", "keyword": "特斯拉FSD在华获批", "link": "https://s.weibo.com/weibo?q=特斯拉FSD在华获批", "label": "爆", "appear_count": 5},
    {"brand": "蔚来", "keyword": "蔚来ET9发布即交付", "link": "https://s.weibo.com/weibo?q=蔚来ET9发布即交付", "label": "", "appear_count": 1},
    {"brand": "小米汽车", "keyword": "雷军回应SU7质量质疑", "link": "https://s.weibo.com/weibo?q=雷军回应SU7质量质疑", "label": "热", "appear_count": 2},
    {"brand": "小鹏汽车", "keyword": "小鹏MONA首月订单破5万", "link": "https://s.weibo.com/weibo?q=小鹏MONA首月订单破5万", "label": "新", "appear_count": 1},
]

news_data = [
    {
        "id": 1, "title": "比亚迪海鸥荣耀版上市售6.98万起 续航超400km",
        "url": "https://www.d1ev.com/news/xinche/20260504123456.shtml",
        "brand": "比亚迪", "source": "第一电动", "score": 85,
        "created_at": "2026-05-04 14:30:00",
        "content": "比亚迪海鸥荣耀版正式上市，售价6.98万元起，CLTC续航里程超400公里。",
        "summary": "比亚迪海鸥荣耀版上市售6.98万起"
    },
    {
        "id": 2, "title": "小米SU7 Ultra开启首批交付 雷军亲自到场",
        "url": "https://auto.gasgoo.com/news/202605/1I70456301C501.shtml",
        "brand": "小米汽车", "source": "盖世汽车", "score": 90,
        "created_at": "2026-05-04 10:15:00",
        "content": "小米SU7 Ultra首批车辆正式开启交付，雷军亲自到场为首批车主交付。",
        "summary": "小米SU7 Ultra开启首批交付"
    },
    {
        "id": 3, "title": "特斯拉FSD最新版本在国内获批 上海率先开放路测",
        "url": "https://www.autohome.com.cn/news/202605/4/1234567.html",
        "brand": "特斯拉", "source": "汽车之家", "score": 92,
        "created_at": "2026-05-04 09:00:00",
        "content": "特斯拉FSD自动驾驶系统最新版本获中国监管部门批准。",
        "summary": "特斯拉FSD最新版本在国内获批"
    },
    {
        "id": 4, "title": "蔚来ET9正式发布 定位行政旗舰轿车 售价80万起",
        "url": "https://www.sohu.com/a/123456789_100286562",
        "brand": "蔚来", "source": "搜狐汽车", "score": 75,
        "created_at": "2026-05-04 16:45:00",
        "content": "蔚来ET9正式发布，定位行政旗舰轿车，售价80万元起。",
        "summary": "蔚来ET9正式发布 定位行政旗舰轿车"
    },
    {
        "id": 5, "title": "小鹏MONA首月订单突破5万台 何小鹏发内部信庆祝",
        "url": "https://www.dongchedi.com/article/7280001234567890",
        "brand": "小鹏汽车", "source": "懂车帝", "score": 88,
        "created_at": "2026-05-04 11:20:00",
        "content": "小鹏MONA上市首月订单突破5万台，何小鹏发内部信。",
        "summary": "小鹏MONA首月订单突破5万台"
    },
    {
        "id": 6, "title": "理想L7 Pro起售价调整至22.98万 应对市场竞争",
        "url": "https://new.qq.com/rain/a/20260504A0012345",
        "brand": "理想汽车", "source": "腾讯新闻", "score": 70,
        "created_at": "2026-05-04 13:00:00",
        "content": "理想汽车调整L7 Pro起售价至22.98万元。",
        "summary": "理想L7 Pro起售价调整至22.98万"
    },
    {
        "id": 7, "title": "吉利银河E8获C-NCAP五星安全评级",
        "url": "https://www.12365auto.com/news/20260504/456789.shtml",
        "brand": "吉利汽车", "source": "中国汽车质量网", "score": 68,
        "created_at": "2026-05-04 08:30:00",
        "content": "吉利银河E8获得C-NCAP五星安全评级。",
        "summary": "吉利银河E8获C-NCAP五星安全评级"
    },
]

# ==================== 生成卡片JSON ====================

daily_elements = render_daily_feishu(
    weibo_data, news_data,
    "2026-05-04", "2026-05-05 09:00"
)

daily_card = {
    "msg_type": "interactive",
    "card": {
        "header": {
            "title": {"tag": "plain_text", "content": "🚗 昨日汽车行业舆情热点新闻"},
            "template": "wathet"
        },
        "elements": daily_elements
    }
}

# 提取所有 lark_md content
print("=" * 80)
print("【日报 lark_md 内容清单】")
print("=" * 80)
lark_md_contents = []
for i, el in enumerate(daily_elements):
    tag = el.get("tag", "")
    if tag == "div":
        text_block = el.get("text", {})
        if text_block.get("tag") == "lark_md":
            content = text_block.get("content", "")
            lark_md_contents.append(content)
            print(f"\n--- Block #{i + 1} ({tag}/lark_md) ---")
            print(content)
    elif tag == "note":
        elements = el.get("elements", [])
        for ne in elements:
            print(f"\n--- Block #{i + 1} ({tag}/plain_text) ---")
            print(ne.get("content", ""))
    elif tag == "hr":
        print(f"\n--- Block #{i + 1} ({tag}) ---")

# ==================== 测试URL编码 ====================
print("\n" + "=" * 80)
print("【URL编码测试】")
print("=" * 80)

test_urls = [
    "https://s.weibo.com/weibo?q=小米SU7Ultra交付破万",
    "https://s.weibo.com/weibo?q=特斯拉FSD在华获批",
    "https://www.d1ev.com/news/xinche/20260504123456.shtml",
    "https://auto.gasgoo.com/news/202605/1I70456301C501.shtml",
    "",
    "not-a-url",
    "http://localhost:8001/health",
    "http://mock-e2e.com/article/123",
]

for u in test_urls:
    encoded = _encode_url(u)
    validated = _valid_url(u)
    print(f"\n  原始: {u}")
    print(f"  编码: {encoded}")
    print(f"  校验: {validated}")
    if validated:
        # 测试在lark_md中的表现
        md_line = f"• [测试标题]({validated})"
        print(f"  md:  {md_line}")

# ==================== 生成HTML预览 ====================
print("\n" + "=" * 80)
print("【生成HTML预览文件】")
print("=" * 80)

html_path = os.path.join(os.path.dirname(__file__), 'card_preview.html')

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>飞书卡片模拟预览 — 汽车舆情监控</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    background: #E8EAED;
    display: flex;
    justify-content: center;
    padding: 40px 20px;
    font-family: -apple-system, BlinkMacSystemFont, 'Microsoft YaHei', 'PingFang SC', sans-serif;
}
.card {
    max-width: 520px;
    width: 100%;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0,0,0,.08);
    overflow: hidden;
}
.card-header {
    padding: 14px 20px;
    color: #fff;
    font-size: 15px;
    font-weight: 600;
}
.card-header.wathet { background: linear-gradient(135deg, #4A90D9, #357ABD); }
.card-header.turquoise { background: linear-gradient(135deg, #00B4B4, #00848A); }
.card-body { padding: 16px 20px; }
.lark-md { line-height: 1.65; }
.lark-md p { margin: 0; }
.lark-md strong { font-weight: 600; color: #111827; }
.lark-md a { color: #2563EB; text-decoration: none; }
.lark-md a:hover { text-decoration: underline; }
.lark-md hr { border: none; border-top: 1px solid #E5E7EB; margin: 12px 0; }
.divider { border-top: 1px solid #E5E7EB; margin: 10px 0; }
.note { font-size: 12px; color: #9CA3AF; margin-top: 4px; }
.item { margin-bottom: 6px; }
.item .badge { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 11px; font-weight: 600; margin-right: 4px; vertical-align: middle; }
.item .badge-hot { background: #FEE2E2; color: #DC2626; }
.item .badge-new { background: #DCFCE7; color: #16A34A; }
.item .badge-boom { background: #FEE2E2; color: #DC2626; }
.meta { font-size: 12px; color: #9CA3AF; margin-top: 2px; margin-bottom: 8px; padding-left: 8px; }
.brand-stats { font-size: 13px; margin-bottom: 8px; }
.section-header { font-size: 14px; font-weight: 600; color: #111827; margin: 10px 0 6px; }
.stat-line { font-size: 13px; color: #6B7280; margin-bottom: 8px; }
.footer-note { font-size: 12px; color: #9CA3AF; margin-top: 8px; text-align: center; }
.link-check { font-size: 11px; color: #6B7280; margin-left: 6px; }
.link-check.ok { color: #10B981; }
.link-check.err { color: #EF4444; }
</style>
</head>
<body>
"""

# Card 1: Daily Report
html += '<div class="card" style="margin-bottom: 32px;">\n'
html += '<div class="card-header wathet">🚗 昨日汽车行业舆情热点新闻</div>\n'
html += '<div class="card-body lark-md">\n'

for i, el in enumerate(daily_elements):
    tag = el.get("tag", "")
    if tag == "hr":
        html += '<div class="divider"></div>\n'
    elif tag == "div":
        text_block = el.get("text", {})
        if text_block.get("tag") == "lark_md":
            content = text_block.get("content", "")
            # Render as raw markdown (approximate feishu rendering)
            # Process <font color="xxx">**text**</font> → styled bold
            import re as re2
            def render_inline(text):
                # Handle <font color="...">text</font>
                def font_replacer(m):
                    color = m.group(1)
                    inner = m.group(2)
                    inner = inner.replace('**', '<strong>').replace('</strong>', '</strong>').rstrip('**').rstrip('<strong>').rstrip('</strong>')
                    # Fix nested ** handling
                    inner = re2.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', inner)
                    return f'<span style="color:{color}; font-weight:600">{inner}</span>'
                text = re2.sub(r'<font color="([^"]+)"[^>]*>([\s\S]*?)</font>', font_replacer, content)
                # Bold
                text = re2.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
                # Links [text](url)
                def link_replacer(m):
                    label = m.group(1)
                    url = m.group(2)
                    return f'<a href="{url}" target="_blank" title="{url}">{label}</a>'
                text = re2.sub(r'\[([^\]]+)\]\(([^)]+)\)', link_replacer, text)
                # Line breaks
                text = text.replace('\n', '<br>')
                return text

            rendered = render_inline(content)

            # Heuristic: section headers
            if content.startswith('**📰') or content.startswith('**🔥') or content.startswith('**昨日'):
                html += f'<div class="section-header">{rendered}</div>\n'
            elif content.startswith('📊') or content.startswith('📭'):
                html += f'<div class="stat-line">{rendered}</div>\n'
            else:
                # Individual items
                if content.strip():
                    html += f'<div class="item">{rendered}</div>\n'
    elif tag == "note":
        elements = el.get("elements", [])
        for ne in elements:
            html += f'<div class="note">{ne.get("content", "")}</div>\n'

html += '</div>\n</div>\n'

# ==================== Card 2: URL Test Card ====================
html += '<div class="card" style="margin-bottom: 32px;">\n'
html += '<div class="card-header turquoise">🔗 所有链接可点击性测试</div>\n'
html += '<div class="card-body" style="font-size:14px; line-height:1.8;">\n'

all_links = []
for w in weibo_data:
    enc = _encode_url(w['link'])
    all_links.append(('weibo', w['keyword'], enc))
    html += f'<div><strong>🔥 微博</strong>：{w["keyword"]} '
    if enc:
        html += f'<a href="{enc}" target="_blank" style="color:#2563EB">🔗 打开</a>'
        html += f'<span class="link-check ok"> ✓</span>'
    else:
        html += f'<span class="link-check err"> ✗ 无链接</span>'
    html += '</div>\n'

for n in news_data:
    enc = _encode_url(n['url'])
    all_links.append(('news', n['title'], enc))
    html += f'<div><strong>📰 新闻</strong>：{n["title"][:30]}... '
    if enc:
        html += f'<a href="{enc}" target="_blank" style="color:#2563EB">🔗 打开</a>'
        html += f'<span class="link-check ok"> ✓</span>'
    else:
        html += f'<span class="link-check err"> ✗ 无链接</span>'
    html += '</div>\n'

html += '</div>\n</div>\n'

# ==================== Card 3: Raw JSON ====================
html += '<div class="card" style="margin-bottom: 32px;">\n'
html += '<div class="card-header" style="background:#1E293B;">📋 实际推送JSON (部分)</div>\n'
html += '<div class="card-body">\n'
html += '<pre style="font-size:11px; line-height:1.4; overflow-x:auto; background:#F8F9FA; padding:12px; border-radius:6px; max-height:400px; overflow-y:auto;">'

json_preview = {
    "msg_type": daily_card["msg_type"],
    "card": {
        "header": daily_card["card"]["header"],
        "elements": [
            {
                "tag": el.get("tag"),
                "text": {"tag": el.get("text", {}).get("tag"), "content": (el.get("text", {}).get("content", "")[:80] + "...") if el.get("text", {}).get("tag") == "lark_md" else el.get("text", {})} if el.get("tag") == "div" and el.get("text") else None
            } if el.get("tag") in ("div",) else {"tag": el.get("tag")} for el in daily_elements[:8]
        ] + [{"...": f"... 还有 {len(daily_elements) - 8} 个元素"}]
    }
}
html += json.dumps(json_preview, indent=2, ensure_ascii=False)
html += '</pre>\n</div>\n</div>\n'

html += '</body>\n</html>'

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"HTML预览已生成: {html_path}")
print(f"\n共 {len(lark_md_contents)} 个 lark_md 区块")
print(f"共 {len(all_links)} 个链接")

# 保存完整JSON供参考
json_path = os.path.join(os.path.dirname(__file__), 'daily_card.json')
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(daily_card, f, ensure_ascii=False, indent=2)
print(f"完整JSON已保存: {json_path}")
