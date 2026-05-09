"""设计令牌 V5.1 — Apple简约科技风 + 邮件共用shell"""
from v2.constants import BRAND_COLORS, DEFAULT_BRAND_COLOR

PALETTE = {
    "bg_primary": "#F5F5F7",
    "surface": "#FFFFFF",
    "surface_hover": "#F2F2F4",
    "text_primary": "#1D1D1F",
    "text_secondary": "#6E6E73",
    "text_tertiary": "#AEAEB2",
    "divider": "#E5E5EA",
    "divider_bold": "#D1D1D6",
    "blue_link": "#0071E3",
    "blue_bg": "#F0F6FF",
    "navy_dark": "#1D1D1F",
    "navy_mid": "#2D2D30",
    "amber_accent": "#FF9F0A",
    "green_dot": "#34C759",
    "green_bg": "#F0FFF4",
    "red_soft": "#FFF5F5",
    "red_accent": "#FF3B30",
    "white": "#FFFFFF",
    "brand_card_bg": "#FAFAFA",
    "accent_gradient_from": "#1D1D1F",
    "accent_gradient_to": "#3A3A3C",
}

SPACING = {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32, "xxl": 48, "xxxl": 64}

DIMENSION_ICONS = {
    "🎨 创意营销/公关事件": "🎨",
    "📤 投放与合作": "📤",
    "🌟 明星与IP合作": "🌟",
    "⚙️ 核心活动": "⚙️",
}


def brand_color(brand: str) -> str:
    return BRAND_COLORS.get(brand, DEFAULT_BRAND_COLOR)


def brand_badge_html(brand: str, size: str = "normal") -> str:
    if size == "large":
        return (
            f'<span style="display:inline-block;background:{brand_color(brand)};'
            f'color:#FFFFFF;font-size:12px;font-weight:600;padding:3px 12px;border-radius:99px;'
            f'line-height:20px;vertical-align:middle;letter-spacing:0.3px;'
            f'font-family:\'PingFang SC\',\'Microsoft YaHei\',sans-serif;">{brand}</span>'
        )
    return (
        f'<span style="display:inline-block;background:{brand_color(brand)};'
        f'color:#FFFFFF;font-size:11px;font-weight:600;padding:2px 10px;border-radius:99px;'
        f'line-height:18px;vertical-align:middle;letter-spacing:0.2px;'
        f'font-family:\'PingFang SC\',\'Microsoft YaHei\',sans-serif;">{brand}</span>'
    )


def brand_badge_feishu(brand: str) -> str:
    return f'<font color="{brand_color(brand)}">**{brand}**</font>'


# ── 邮件共用 Shell ──

def email_shell(title: str, accent_color: str, body_content: str,
                 generated_at: str = '') -> str:
    """邮件通用外壳：header + body + footer"""
    P = PALETTE
    S = SPACING
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
</head>
<body style="margin:0;padding:0;background:{P['bg_primary']};font-family:'PingFang SC','Microsoft YaHei','Helvetica Neue',sans-serif;-webkit-font-smoothing:antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{P['bg_primary']};">
<tr><td align="center" style="padding:{S['lg']}px {S['sm']}px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;border-radius:14px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.06);">
<tr>
<td style="background:linear-gradient(135deg,{P['accent_gradient_from']} 0%,{P['accent_gradient_to']} 100%);padding:{S['lg']}px {S['xl']}px;">
<h1 style="margin:0;font-size:18px;font-weight:700;color:{P['white']};letter-spacing:0.3px;">{title}</h1>
</td>
</tr>
<tr><td style="background:{accent_color};height:3px;font-size:0;">&nbsp;</td></tr>
<tr><td style="background:{P['surface']};padding:{S['xl']}px {S['xl']}px {S['sm']}px;">
{body_content}
</td></tr>
<tr><td style="background:{P['surface']};padding:{S['sm']}px {S['xl']}px {S['md']}px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td style="border-top:1px solid {P['divider']};padding-top:{S['sm']}px;">
<span style="font-size:10px;color:{P['text_tertiary']};">生成 {generated_at} · 汽车行业舆情监控系统</span>
</td></tr>
</table>
</td></tr>
</table>
</td></tr></table>
</body></html>"""
