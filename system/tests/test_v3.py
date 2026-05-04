"""V4.1 回归测试"""
import sys
sys.path.insert(0, 'system')

def test_imports():
    from config import SYSTEM_DIR, DB_PATH, FEISHU_WEBHOOK_URL
    from v2.constants import BRAND_REGEX, RSS_FEEDS, WEB_FEEDS, HAMMING_THRESHOLD
    from processor.brand_matcher import match_brand, strip_html, is_financial_brief
    from processor.deduplicator import compute_simhash, generate_event_id
    from processor.classifier import classify_dimension
    from processor.keyworder import extract_keywords
    from templates.design_tokens import PALETTE, brand_badge_html
    print('[PASS] All imports')


def test_brand_match():
    from processor.brand_matcher import match_brand
    cases = [
        ('小米SU7 Ultra纽北', '小米汽车'),
        ('问界M9销量突破', '鸿蒙智行'),
        ('比亚迪海鸥上市', '比亚迪'),
        ('特斯拉FSD获批', '特斯拉'),
        ('理想L6交付破万', '理想汽车'),
        ('零跑C16发布', '零跑汽车'),
        ('蔚来萤火虫ONE', '蔚来汽车'),
        ('极氪007旅行版', '极氪汽车'),
        ('阿维塔12上市', '阿维塔'),
    ]
    for text, expected in cases:
        b, _ = match_brand(text)
        assert b == expected, f'{text}: expected {expected}, got {b}'
    print('[PASS] Brand matching (9/9)')


def test_financial_filter():
    from processor.brand_matcher import is_financial_brief
    assert is_financial_brief('热门中概股美股盘前涨跌不一，蔚来涨超4%')
    assert is_financial_brief('港股收盘恒指涨1.68% 蔚来涨近9%')
    assert not is_financial_brief('乐道L80新车预售，蔚来创始人李斌表示订单好于预期')
    assert not is_financial_brief('问界M9大定突破20万台')
    print('[PASS] Financial filter')


def test_simhash():
    from processor.deduplicator import compute_simhash, _hamming_distance
    s1 = compute_simhash('小米SU7 Ultra纽北圈速突破7分钟 雷军发博庆贺')
    s2 = compute_simhash('小米SU7 Ultra在纽北跑进7分钟创下纪录 雷军发文宣布')
    s3 = compute_simhash('比亚迪海鸥荣耀版上市 5.98万起售')
    assert s1 != '0' * 16
    v1, v2, v3 = int(s1, 16), int(s2, 16), int(s3, 16)
    d12 = _hamming_distance(v1, v2)
    d13 = _hamming_distance(v1, v3)
    assert d12 < d13, f'simhash: similar({d12}) should be < different({d13})'
    print(f'[PASS] Simhash (similar={d12}, different={d13})')


def test_classifier():
    from processor.classifier import classify_dimension
    assert '⚙️' in classify_dimension('小米SU7 Ultra纽北发布')
    assert '🌟' in classify_dimension('刘德华代言尊界品牌官宣')
    assert '📤' in classify_dimension('蔚来与中石化达成换电站战略合作')
    assert '🎨' in classify_dimension('特斯拉官方回应召回事件 发布致歉声明')
    print('[PASS] Dimension classifier')


def test_html_strip():
    from processor.brand_matcher import strip_html
    assert strip_html('<b>蔚来港股大涨超9%</b>') == '蔚来港股大涨超9%'
    assert strip_html('<a href="">title</a><br/>') == 'title'
    print('[PASS] HTML stripping')


def test_config():
    from config import DB_PATH, WEIBO_DB_PATH, NEWS_RETENTION_DAYS, WEIBO_RETENTION_DAYS
    assert 'v3_monitor.db' in DB_PATH
    assert 'v3_weibo.db' in WEIBO_DB_PATH
    assert NEWS_RETENTION_DAYS == 8
    assert WEIBO_RETENTION_DAYS == 30
    print('[PASS] Config values')


def test_templates():
    from templates.design_tokens import PALETTE, brand_badge_html, brand_badge_feishu
    from templates.email_daily import render_daily_email
    from templates.email_weekly import render_weekly_email
    from templates.email_monthly import render_monthly_email
    assert PALETTE['blue_link'] == '#2563EB'
    assert '小米汽车' in brand_badge_html('小米汽车', 'large')
    assert '#' in brand_badge_feishu('小米汽车')
    print('[PASS] Templates')


if __name__ == '__main__':
    print('V4.1 回归测试')
    print('=' * 50)
    tests = [
        test_imports, test_brand_match, test_financial_filter,
        test_simhash, test_classifier, test_html_strip,
        test_config, test_templates,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}')
    print('=' * 50)
    print('All tests completed')
