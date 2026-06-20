from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from src.infra.config import load_search_config
from src.infra.time_context import current_year, search_timestamp

SearchEngine = Literal["bing", "baidu", "auto"]

_DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

_FRESHNESS_KEYWORDS = ("新特性", "新闻", "最新", "发布", "版本", "更新", "what's new", "release notes")
_YEAR_PATTERN = re.compile(r"20\d{2}")


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    engine: str
    stale_hint: str = ""


def _client(timeout: float) -> httpx.Client:
    cfg = load_search_config()
    headers = dict(_DEFAULT_HEADERS)
    ua = cfg.get("search", {}).get("user_agent")
    if ua:
        headers["User-Agent"] = ua
    return httpx.Client(headers=headers, timeout=timeout, follow_redirects=True)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def enrich_query(query: str) -> str:
    """为时效性查询补充年份/「最新」，提高结果新鲜度。"""
    cfg = load_search_config().get("search", {})
    if not cfg.get("auto_enrich_query", True):
        return query.strip()

    q = query.strip()
    year = current_year()
    if not _YEAR_PATTERN.search(q):
        q = f"{q} {year}"

    if any(kw in query for kw in _FRESHNESS_KEYWORDS) and "最新" not in q:
        q = f"{q} 最新"

    return q


def _detect_stale(text: str) -> str:
    """检测摘要中是否出现过时年份表述。"""
    year = current_year()
    found_years = {int(y) for y in _YEAR_PATTERN.findall(text)}
    old_years = {y for y in found_years if y < year - 1}
    if old_years:
        return f"摘要含较旧年份 {sorted(old_years)}，请以 {year} 年信息为准并谨慎引用"
    stale_phrases = ("尚未发布", "还未发布", "预计将在", "截至目前")
    if any(p in text for p in stale_phrases):
        return f"摘要可能已过时（当前为 {year} 年），请结合搜索时间判断"
    return ""


def search_bing(query: str, max_results: int = 5, timeout: float = 15) -> list[SearchResult]:
    # Bing freshness: ez5 = past year filter (approximate)
    url = (
        f"https://www.bing.com/search?q={quote_plus(query)}"
        f"&count={max_results}&setlang=zh-Hans"
        f'&filters=ex1:"ez5_18340"'
    )
    with _client(timeout) as client:
        resp = client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results: list[SearchResult] = []
    for item in soup.select("li.b_algo")[:max_results]:
        title_el = item.select_one("h2 a")
        snippet_el = item.select_one(".b_caption p") or item.select_one("p")
        if not title_el:
            continue
        title = _clean(title_el.get_text())
        snippet = _clean(snippet_el.get_text() if snippet_el else "")
        combined = f"{title} {snippet}"
        results.append(
            SearchResult(
                title=title,
                url=title_el.get("href", ""),
                snippet=snippet,
                engine="bing",
                stale_hint=_detect_stale(combined),
            )
        )
    return results


def search_baidu(query: str, max_results: int = 5, timeout: float = 15) -> list[SearchResult]:
    # 百度：排序按时间 gpc=sf=1 有时效性排序
    url = f"https://www.baidu.com/s?wd={quote_plus(query)}&rn={max_results}"
    with _client(timeout) as client:
        resp = client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results: list[SearchResult] = []
    containers = soup.select("div.result.c-container, div.c-container")
    for item in containers[: max_results * 2]:
        title_el = item.select_one("h3 a") or item.select_one("a")
        if not title_el:
            continue
        snippet_el = (
            item.select_one(".c-abstract")
            or item.select_one(".content-right_8Zs40")
            or item.select_one("span.content-right_8Zs40")
            or item.select_one("div.c-row")
        )
        href = title_el.get("href", "")
        title = _clean(title_el.get_text())
        snippet = _clean(snippet_el.get_text() if snippet_el else "")
        if not title:
            continue
        combined = f"{title} {snippet}"
        results.append(
            SearchResult(
                title=title,
                url=href,
                snippet=snippet,
                engine="baidu",
                stale_hint=_detect_stale(combined),
            )
        )
        if len(results) >= max_results:
            break
    return results


def format_results(results: list[SearchResult], original_query: str, enriched_query: str) -> str:
    if not results:
        return "未找到相关搜索结果。"

    year = current_year()
    lines = [
        f"【搜索时间】{search_timestamp()}（当前年份：{year}）",
        f"【原始查询】{original_query}",
    ]
    if enriched_query != original_query:
        lines.append(f"【增强查询】{enriched_query}")
    lines.append(
        "【重要】以下为用户搜索工具返回的实时网页摘要，回答时必须优先依据这些内容，"
        f"不要用训练数据中的旧信息覆盖。若摘要年份早于 {year - 1} 年或含「尚未发布」等表述，应标注可能过时。"
    )
    lines.append("")

    for i, r in enumerate(results, 1):
        lines.append(f"{i}. [{r.title}]({r.url})")
        if r.snippet:
            lines.append(f"   {r.snippet}")
        lines.append(f"   来源: {r.engine}")
        if r.stale_hint:
            lines.append(f"   ⚠ {r.stale_hint}")
        lines.append("")

    return "\n".join(lines)


def web_search_impl(query: str, engine: SearchEngine = "auto") -> str:
    cfg = load_search_config().get("search", {})
    max_results = int(cfg.get("max_results", 5))
    timeout = float(cfg.get("timeout", 15))
    default_engine = cfg.get("default_engine", "auto")
    engine = engine if engine != "auto" else default_engine

    original_query = query.strip()
    enriched = enrich_query(original_query)
    logger.info("搜索: {} -> {}", original_query, enriched)

    engines: list[str]
    if engine == "auto":
        engines = ["bing", "baidu"]
    else:
        engines = [engine]

    errors: list[str] = []
    for name in engines:
        try:
            if name == "bing":
                results = search_bing(enriched, max_results, timeout)
            else:
                results = search_baidu(enriched, max_results, timeout)
            if results:
                return format_results(results, original_query, enriched)
            errors.append(f"{name}: 无结果")
        except Exception as exc:
            logger.warning("搜索失败 {}: {}", name, exc)
            errors.append(f"{name}: {exc}")

    return "搜索失败。\n" + "\n".join(errors)
