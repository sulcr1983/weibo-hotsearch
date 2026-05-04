"""极简高亮艺术风（方案B v2）— 设计令牌"""
from v2.constants import BRAND_COLORS, DEFAULT_BRAND_COLOR

PALETTE = {
    "bg_primary": "#F8F9FA",
    "surface": "#FFFFFF",
    "surface_hover": "#F3F4F6",
    "text_primary": "#111827",
    "text_secondary": "#6B7280",
    "text_tertiary": "#9CA3AF",
    "divider": "#E5E7EB",
    "divider_bold": "#D1D5DB",
    "blue_link": "#2563EB",
    "blue_bg": "#EFF6FF",
    "navy_dark": "#0F172A",
    "navy_mid": "#1E293B",
    "amber_accent": "#F59E0B",
    "green_dot": "#10B981",
    "green_bg": "#ECFDF5",
    "red_soft": "#FEF2F2",
    "white": "#FFFFFF",
    "brand_card_bg": "#F9FAFB",
}

SPACING = {
    "xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32, "xxl": 48, "xxxl": 64,
}

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
            f'color:#FFFFFF;font-size:13px;font-weight:700;'
            f'padding:3px 14px;border-radius:999px;'
            f'line-height:22px;vertical-align:middle;'
            f'letter-spacing:0.5px;'
            f'font-family:\'Microsoft YaHei\',\'PingFang SC\',Arial,sans-serif;">'
            f'{brand}</span>'
        )
    return (
        f'<span style="display:inline-block;background:{brand_color(brand)};'
        f'color:#FFFFFF;font-size:12px;font-weight:600;'
        f'padding:2px 10px;border-radius:999px;'
        f'line-height:20px;vertical-align:middle;'
        f'letter-spacing:0.3px;'
        f'font-family:\'Microsoft YaHei\',\'PingFang SC\',Arial,sans-serif;">'
        f'{brand}</span>'
    )


def brand_badge_feishu(brand: str) -> str:
    color = brand_color(brand)
    return f'<font color="{color}">**{brand}**</font>'


def stat_card_html(label: str, value: str, accent: str = "#2563EB") -> str:
    return (
        f'<div style="display:inline-block;text-align:center;'
        f'padding:8px 16px;min-width:60px;">'
        f'<div style="font-size:22px;font-weight:700;color:{accent};'
        f'line-height:1.2;">{value}</div>'
        f'<div style="font-size:11px;color:#6B7280;margin-top:2px;">{label}</div>'
        f'</div>'
    )


def brand_section_divider(brand: str) -> str:
    return (
        f'<tr><td style="padding:20px 0 8px;">'
        f'<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="background:{brand_color(brand)};width:3px;'
        f'height:18px;border-radius:2px;vertical-align:middle;"></td>'
        f'<td style="padding-left:10px;vertical-align:middle;">'
        f'{brand_badge_html(brand, "large")}'
        f'</td></tr></table></td></tr>'
    )
