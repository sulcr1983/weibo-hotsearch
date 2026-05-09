"""HTML解析工具 V5.0 — 统一的链接提取 + 去重逻辑（消除4个采集器的重复）"""
from typing import List, Set
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def extract_links(html: str, base_url: str, article_sel: str = 'a[href]',
                  container_sel: str = '', max_items: int = 20) -> List[dict]:
    """
    从 HTML 中提取文章链接（替代各采集器的重复解析循环）

    返回: [{'title': str, 'url': str}, ...]
    """
    soup = BeautifulSoup(html, 'html.parser')

    if container_sel:
        containers = soup.select(container_sel)
        links: List[Tag] = []
        for c in containers:
            links.extend(c.select(article_sel))
    else:
        links = soup.select(article_sel)

    results: List[dict] = []
    seen_urls: Set[str] = set()

    for el in links:
        if len(results) >= max_items:
            break
        title = el.get_text(strip=True)
        href = el.get('href', '').strip()
        if not title or len(title) < 5 or not href:
            continue
        if any(bad in href.lower() for bad in ['javascript:', 'mailto:', '#', 'tel:', 'login']):
            continue
        full_url = urljoin(base_url, href)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        results.append({'title': title, 'url': full_url})

    return results


def clean_html_text(html: str, max_lines: int = 300) -> str:
    """从 HTML 中提取纯文本（用于 AI 爬虫等场景）"""
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript', 'iframe', 'svg']):
            tag.decompose()
        text = soup.get_text(separator='\n', strip=True)
        lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 2]
        return '\n'.join(lines[:max_lines])
    except Exception:
        return html[:4000]


def strip_html(text: str) -> str:
    """去除 HTML 标签"""
    try:
        soup = BeautifulSoup(text, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    except Exception:
        return text