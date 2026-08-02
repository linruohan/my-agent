from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from loguru import logger

from src.infra.config import load_search_config
from src.infra.http_client import shared_http_client
from src.infra.time_context import current_year, search_timestamp

SearchEngine = Literal["bing", "baidu", "auto"]

_DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.bing.com/",
}

_FRESHNESS_KEYWORDS = ("新特性", "新闻", "最新", "发布", "版本", "更新", "what's new", "release notes")
_YEAR_PATTERN = re.compile(r"20\d{2}")
_VERSION_PATTERN = re.compile(r"\d+\.\d+")
_PYTHON_VERSION_RE = re.compile(r"python\s*(\d+\.\d+)", re.I)
_HAS_CJK = re.compile(r"[\u4e00-\u9fff]")


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    engine: str
    stale_hint: str = ""


def _request_headers() -> dict[str, str]:
    cfg = load_search_config()
    headers = dict(_DEFAULT_HEADERS)
    ua = cfg.get("search", {}).get("user_agent")
    if ua:
        headers["User-Agent"] = ua
    return headers


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def enrich_query(query: str) -> str:
    """为时效性查询补充年份/「最新」。含具体版本号时不改写，避免搜索精度下降。"""
    cfg = load_search_config().get("search", {})
    if not cfg.get("auto_enrich_query", True):
        return query.strip()

    q = query.strip()
    if _VERSION_PATTERN.search(q):
        return q

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


def _query_keywords(query: str) -> list[str]:
    keywords: list[str] = []
    for m in _VERSION_PATTERN.finditer(query):
        keywords.append(m.group())
    for word in re.findall(r"[\u4e00-\u9fff]{2,}", query):
        keywords.append(word)
    for word in re.findall(r"[a-zA-Z]{3,}", query):
        keywords.append(word.lower())
    return keywords


def results_match_query(results: list[SearchResult], query: str) -> bool:
    """判断搜索结果是否与查询相关（用于 Bing 反爬降级检测）。"""
    if not results:
        return False
    keywords = _query_keywords(query)
    if not keywords:
        return True
    blob = " ".join(f"{r.title} {r.snippet}" for r in results[:5]).lower()
    hits = sum(1 for kw in keywords if kw.lower() in blob)
    return hits >= min(2, len(keywords))


def _try_python_docs(query: str, timeout: float) -> SearchResult | None:
    """Python 版本新特性：直接抓取官方 whatsnew 文档。"""
    if "python" not in query.lower() and "新特性" not in query and "whats new" not in query.lower():
        return None
    match = _PYTHON_VERSION_RE.search(query) or _VERSION_PATTERN.search(query)
    if not match:
        return None
    version = match.group(1) if match.lastindex else match.group(0)
    urls = [
        f"https://docs.python.org/zh-cn/3/whatsnew/{version}.html",
        f"https://docs.python.org/3/whatsnew/{version}.html",
    ]
    for url in urls:
        try:
            resp = shared_http_client().get(
                url, headers=_request_headers(), timeout=timeout
            )
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            h1 = soup.select_one("h1")
            title = _clean(h1.get_text()) if h1 else f"Python {version} 新特性"
            snippet_el = soup.select_one("div.body > p") or soup.select_one("p")
            snippet = _clean(snippet_el.get_text()[:400]) if snippet_el else ""
            return SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                engine="docs.python.org",
            )
        except Exception as exc:
            logger.debug("Python 文档抓取失败 {}: {}", url, exc)
    return None


def search_bing(query: str, max_results: int = 5, timeout: float = 15) -> list[SearchResult]:
    url = (
        f"https://cn.bing.com/search?q={quote_plus(query)}"
        f"&count={max_results}&setlang=zh-Hans&mkt=zh-CN"
    )
    resp = shared_http_client().get(
        url, headers=_request_headers(), timeout=timeout
    )
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
    url = f"https://www.baidu.com/s?wd={quote_plus(query)}&rn={max_results}"
    resp = shared_http_client().get(
        url, headers=_request_headers(), timeout=timeout
    )
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


def _dedupe_results(results: list[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    out: list[SearchResult] = []
    for r in results:
        key = r.url or r.title
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _merge_with_docs(results: list[SearchResult], query: str, timeout: float) -> list[SearchResult]:
    doc = _try_python_docs(query, timeout)
    if doc:
        return _dedupe_results([doc, *results])
    return results


def _search_one(name: str, query: str, max_results: int, timeout: float) -> list[SearchResult]:
    if name == "bing":
        return search_bing(query, max_results, timeout)
    return search_baidu(query, max_results, timeout)


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
    lines.append("【内部检索数据 — 请阅读后汇总为自然语言回复，勿向用户原文粘贴本段内容】")
    lines.append(
        f"【重要】以下为用户搜索工具返回的实时网页摘要，回答时必须优先依据这些内容，"
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

    if engine == "auto":
        if _HAS_CJK.search(original_query):
            engines = ["baidu", "bing"]
        else:
            engines = ["bing", "baidu"]
    else:
        engines = [engine]

    errors: list[str] = []
    collected: list[SearchResult] = []

    for name in engines:
        try:
            results = _search_one(name, enriched, max_results, timeout)
            if name == "bing" and results and not results_match_query(results, original_query):
                logger.warning("Bing 结果与查询不匹配，跳过: {}", original_query)
                errors.append(f"{name}: 结果不相关（可能反爬）")
                continue
            if results:
                collected = _merge_with_docs(results, original_query, timeout)
                return format_results(collected[:max_results], original_query, enriched)
            errors.append(f"{name}: 无结果")
        except Exception as exc:
            logger.warning("搜索失败 {}: {}", name, exc)
            errors.append(f"{name}: {exc}")

    doc_only = _try_python_docs(original_query, timeout)
    if doc_only:
        return format_results([doc_only], original_query, enriched)

    return "搜索失败。\n" + "\n".join(errors)
