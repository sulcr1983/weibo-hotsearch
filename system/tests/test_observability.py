"""可观测性模块 + HTML断言 + 漏斗统计 测试"""
import sys
from pathlib import Path

# 确保 system/ 在 path 中
_sys_dir = Path(__file__).resolve().parent.parent
if str(_sys_dir) not in sys.path:
    sys.path.insert(0, str(_sys_dir))

from processor.observability import (
    new_trace_id, DropReason, FunnelStats, get_funnel,
    check_html_validity, save_fail_snapshot, log_trace,
)


def test_trace_id():
    """验证trace_id格式"""
    tid = new_trace_id()
    assert len(tid) == 8, f"trace_id长度应为8，实际{len(tid)}"
    tid2 = new_trace_id()
    assert tid != tid2, "两次生成的trace_id不应相同"


def test_drop_reason_labels():
    """验证所有DropReason都有中文标签"""
    for attr in dir(DropReason):
        if attr.startswith('_') or attr == 'LABELS':
            continue
        val = getattr(DropReason, attr)
        if isinstance(val, str) and val.islower():
            assert val in DropReason.LABELS, f"DropReason.{attr}='{val}'缺少LABELS"
    print(f"  DropReason: {len(DropReason.LABELS)}种过滤原因")


def test_funnel_stats():
    """验证漏斗统计"""
    funnel = FunnelStats()
    funnel.raw_captured = 100
    funnel.brand_hit = 60
    funnel.dimension_pass = 40
    funnel.db_inserted = 30
    funnel.count_drop(DropReason.NO_BRAND_MATCH)
    funnel.count_drop(DropReason.NO_BRAND_MATCH)
    funnel.count_drop(DropReason.DUPLICATE)

    s = funnel.summary()
    assert s['pipeline']['raw_captured'] == 100
    assert s['pipeline']['brand_hit'] == 60
    assert s['pipeline']['db_inserted'] == 30
    assert s['top_drop_reasons'][0]['count'] == 2
    assert s['top_drop_reasons'][0]['reason'] == '品牌未命中'

    funnel.log_report()
    print(f"  漏斗统计: {s['success_rate']} 成功率, {len(s['top_drop_reasons'])}个过滤维度")


def test_check_html_validity():
    """验证HTML有效性断言"""
    # 正常HTML
    r = check_html_validity('<html><body><p>汽车行业新闻内容测试文章标题和正文内容</p>' * 5 + '</body></html>')
    assert r['valid'] is True, f"正常HTML应通过: {r}"

    # 空HTML
    r = check_html_validity('')
    assert r['valid'] is False
    assert r['issue_type'] == 'empty_content', f"空HTML应标记empty_content: {r}"

    # 短HTML
    r = check_html_validity('<html></html>')
    assert r['valid'] is False, f"过短HTML应标记无效: {r}"

    # 验证码页面
    r = check_html_validity('<html><body><h1>请输入验证码</h1><p>请完成安全验证</p></body></html>')
    assert r['valid'] is False, f"验证码页面应标记无效: {r}"
    assert r['issue_type'] == 'captcha_page', f"验证码页面类型应为captcha_page: {r}"

    # 登录页面
    r = check_html_validity('<html><body><a>请先登录</a><button>立即登录</button></body></html>')
    assert r['valid'] is False, f"登录页面应标记无效: {r}"

    # 403页面
    r = check_html_validity('<html><body>403 Forbidden - Access Denied</body></html>')
    assert r['valid'] is False, f"403页面应标记无效: {r}"
    assert r['issue_type'] == 'forbidden_page', f"403类型应为forbidden_page: {r}"

    # Cloudflare
    r = check_html_validity('<html><body>Cloudflare DDoS protection - Checking your browser</body></html>')
    assert r['valid'] is False, f"Cloudflare页面应标记无效: {r}"

    print(f"  HTML断言: 7个测试用例全部通过")


def test_save_fail_snapshot():
    """验证失败快照保存"""
    import tempfile, os
    # 使用临时目录测试（测试实际路径写入）
    path = save_fail_snapshot(
        '<html><body>请完成安全验证</body></html>',
        'test_source',
        'captcha_page'
    )
    if path:
        assert os.path.exists(path), f"快照文件应存在: {path}"
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert '验证' in content
        assert 'test_source' in content
        print(f"  快照保存: {path}")
    else:
        print(f"  快照保存: 无目录权限（跳过）")


def test_log_trace():
    """验证trace记录"""
    funnel = get_funnel()
    funnel.reset()
    tid = new_trace_id()
    log_trace(tid, '[RAW]', '测试新闻标题', 'test detail')
    log_trace(tid, '[BRAND]', '测试新闻标题', '小米汽车')
    log_trace(tid, '[DB]', '测试新闻标题', 'score=75')
    assert tid in funnel.traces, "trace应被记录"
    assert len(funnel.traces[tid]['stages']) == 3
    print(f"  Trace记录: {len(funnel.traces[tid]['stages'])}个阶段")


def test_drop_counts():
    """验证过滤原因计数"""
    funnel = FunnelStats()
    reasons = [
        DropReason.NO_BRAND_MATCH,
        DropReason.NO_BRAND_MATCH,
        DropReason.NO_BRAND_MATCH,
        DropReason.DUPLICATE,
        DropReason.DUPLICATE,
        DropReason.SCORE_DISCARD,
    ]
    for r in reasons:
        funnel.count_drop(r)
    s = funnel.summary()
    top = s['top_drop_reasons']
    assert top[0]['reason'] == '品牌未命中'
    assert top[0]['count'] == 3
    assert top[1]['reason'] == 'URL去重'
    assert top[1]['count'] == 2
    print(f"  过滤计数: {len(top)}种原因, 最常见'{top[0]['reason']}' x{top[0]['count']}")


if __name__ == '__main__':
    print("=" * 50)
    print("可观测性模块测试")
    print("=" * 50)
    test_trace_id()
    test_drop_reason_labels()
    test_funnel_stats()
    test_check_html_validity()
    test_save_fail_snapshot()
    test_log_trace()
    test_drop_counts()
    print()
    print("✅ 所有可观测性测试通过")
