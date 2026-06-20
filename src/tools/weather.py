"""中国天气网（weather.com.cn）天气预报：当天 / 7 天，返回精简 HTML。"""

from __future__ import annotations

import re
from typing import Any, Literal
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from src.infra.config import load_search_config, load_weather_config

WeatherRange = Literal["1d", "7d"]

_CITY_CODE_RE = re.compile(r"^101\d{6}$")
_TODAY_HINT_RE = re.compile(r"今天|今日|当天|今儿|今个", re.IGNORECASE)
_7D_HINT_RE = re.compile(r"7\s*天|七天|一周|本周|7\s*日", re.IGNORECASE)

WEATHER_URLS: dict[WeatherRange, str] = {
    "1d": "https://www.weather.com.cn/weather1d/{code}.shtml",
    "7d": "https://www.weather.com.cn/weather/{code}.shtml",
}

WEATHER_RANGE_LABELS: dict[WeatherRange, str] = {
    "1d": "当天预报",
    "7d": "7天预报",
}

_CURVE_SCRIPT_KEYS = ("hour3data", "biggt", "curve")
_EMBED_SCRIPTS = (
    "https://i.tq121.com.cn/j/jquery-1.8.2.js",
    "https://i.tq121.com.cn/j/core.js",
)


def _default_headers() -> dict[str, str]:
    cfg = load_search_config().get("search", {})
    ua = cfg.get(
        "user_agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    )
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.weather.com.cn/",
    }


def _normalize_city_code(code: str) -> str | None:
    c = (code or "").strip()
    if _CITY_CODE_RE.fullmatch(c):
        return c
    return None


def normalize_weather_range(value: str | None) -> WeatherRange:
    v = (value or "").strip().lower()
    if v in {"1d", "1", "today", "today1d"}:
        return "1d"
    return "7d"


def detect_weather_range(text: str) -> WeatherRange:
    """根据用户文本识别当天或 7 天预报，默认 7 天。"""
    body = (text or "").strip()
    if not body:
        return "7d"
    if _TODAY_HINT_RE.search(body):
        return "1d"
    if _7D_HINT_RE.search(body):
        return "7d"
    return "7d"


def parse_weather_slash_args(args: str) -> tuple[str, WeatherRange]:
    """解析 /weather 后的参数，返回 (city_code, range_type)。"""
    text = (args or "").strip()
    if not text:
        return "", "7d"
    if _CITY_CODE_RE.fullmatch(text):
        return text, "7d"

    code = ""
    rest_parts: list[str] = []
    for part in text.split():
        if _CITY_CODE_RE.fullmatch(part):
            code = part
        else:
            rest_parts.append(part)
    rest = " ".join(rest_parts) if rest_parts else text
    return code, detect_weather_range(rest)


def weather_page_url(city_code: str, range_type: WeatherRange) -> str:
    return WEATHER_URLS[range_type].format(code=city_code)


def _element_children(parent: Any) -> list[Any]:
    return [c for c in parent.children if getattr(c, "name", None)]


def _is_day_night_block(node: Any) -> bool:
    if node is None or node.name != "div":
        return False
    classes = node.get("class") or []
    if "t" not in classes:
        return False
    for h1 in node.select("h1"):
        text = h1.get_text(strip=True)
        if "白天" in text or "夜间" in text:
            return True
    return False


def _find_day_night_block(soup: BeautifulSoup) -> Any | None:
    """#today 下第 4 个子元素 div.t（白天 + 夜晚）。"""
    today = soup.find(id="today")
    if today is None:
        return soup.select_one("div#today div.t, div.today div.t")

    children = _element_children(today)
    if len(children) >= 4 and _is_day_night_block(children[3]):
        return children[3]

    for node in today.select("div.t"):
        if _is_day_night_block(node):
            return node
    return None


def _find_curve_block(soup: BeautifulSoup) -> tuple[Any | None, Any | None]:
    curve = soup.find(id="curve")
    if curve is None:
        return None, None

    script = curve.find_next_sibling("script")
    if script is None or not (script.string or "").strip():
        return curve, None
    body = script.string or ""
    if not any(key in body for key in _CURVE_SCRIPT_KEYS):
        return curve, None
    return curve, script


def _find_7d_forecast_block(soup: BeautifulSoup) -> Any | None:
    """div#7d.c7d，不含内部的 #curve 与 .livezs。"""
    box = soup.find(id="7d")
    if box is None:
        for div in soup.find_all("div", class_=lambda c: c and "c7d" in c):
            box = div
            break
    if box is None:
        return None

    clone_soup = BeautifulSoup(str(box), "html.parser")
    clone = clone_soup.find(id="7d") or clone_soup.find("div")
    if clone is None:
        return None

    for el in clone.select("#curve, div.livezs, script"):
        el.decompose()
    return clone


def _append_curve_and_live(
    soup: BeautifulSoup,
    parts: list[str],
    missing: list[str],
) -> None:
    curve, curve_script = _find_curve_block(soup)
    if curve is not None:
        parts.append(str(curve))
        if curve_script is not None:
            parts.append(str(curve_script))
    else:
        missing.append("div#curve")

    live = soup.select_one("div.livezs")
    if live is not None:
        parts.append(str(live))
    else:
        missing.append("div.livezs")


def _collect_stylesheets(soup: BeautifulSoup) -> list[str]:
    hrefs: list[str] = []
    seen: set[str] = set()
    for link in soup.find_all("link", rel="stylesheet"):
        href = str(link.get("href", "")).strip()
        if href and href not in seen:
            seen.add(href)
            hrefs.append(href)
    return hrefs


def build_embed_html(
    body_parts: list[str],
    *,
    css_hrefs: list[str],
    script_srcs: list[str],
    page_url: str,
) -> str:
    base = urljoin(page_url, "/")
    css_links = "\n".join(f'<link rel="stylesheet" href="{href}">' for href in css_hrefs)
    scripts = "\n".join(f'<script src="{src}"></script>' for src in script_srcs)
    body = "\n".join(body_parts)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f'<base href="{base}">\n'
        f"{css_links}\n"
        "<style>\n"
        "body{margin:0;padding:12px;background:#fff;color:#333;"
        'font-family:"Microsoft YaHei",sans-serif;}\n'
        ".weather-snippet{max-width:680px;}\n"
        ".weather-snippet>*{margin-bottom:18px;}\n"
        ".weather-snippet .right,.weather-snippet div.right{display:none!important;}\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        '<div class="weather-snippet">\n'
        f"{body}\n"
        "</div>\n"
        f"{scripts}\n"
        "</body>\n"
        "</html>"
    )


def extract_today_weather_html(html: str, *, page_url: str) -> dict[str, Any]:
    """提取当天页：div.t:nth-child(4)、#curve、.livezs。"""
    soup = BeautifulSoup(html, "html.parser")
    parts: list[str] = []
    missing: list[str] = []

    day_night = _find_day_night_block(soup)
    if day_night is not None:
        parts.append(str(day_night))
    else:
        missing.append("div.t:nth-child(4)")

    _append_curve_and_live(soup, parts, missing)

    if not parts:
        return {"ok": False, "error": "未能提取当天天气预报内容", "missing": missing}

    embed = build_embed_html(
        parts,
        css_hrefs=_collect_stylesheets(soup),
        script_srcs=list(_EMBED_SCRIPTS),
        page_url=page_url,
    )
    return {"ok": True, "html": embed, "missing": missing}


def extract_7d_weather_html(html: str, *, page_url: str) -> dict[str, Any]:
    """提取 7 天页：div#7d.c7d、#curve、.livezs。"""
    soup = BeautifulSoup(html, "html.parser")
    parts: list[str] = []
    missing: list[str] = []

    box = _find_7d_forecast_block(soup)
    if box is not None:
        parts.append(str(box))
    else:
        missing.append("div#7d.c7d")

    _append_curve_and_live(soup, parts, missing)

    if not parts:
        return {"ok": False, "error": "未能提取 7 天天气预报内容", "missing": missing}

    embed = build_embed_html(
        parts,
        css_hrefs=_collect_stylesheets(soup),
        script_srcs=list(_EMBED_SCRIPTS),
        page_url=page_url,
    )
    return {"ok": True, "html": embed, "missing": missing}


def extract_weather_html(html: str, range_type: WeatherRange, *, page_url: str) -> dict[str, Any]:
    if range_type == "1d":
        return extract_today_weather_html(html, page_url=page_url)
    return extract_7d_weather_html(html, page_url=page_url)


def prepare_html_for_embed(html: str, *, page_url: str) -> str:
    """兼容旧接口：默认按当天页提取。"""
    result = extract_today_weather_html(html, page_url=page_url)
    if result.get("ok"):
        return str(result["html"])
    return html


def fetch_weather_page(
    city_code: str,
    range_type: WeatherRange = "7d",
    *,
    timeout: float = 20.0,
) -> dict[str, Any]:
    code = _normalize_city_code(city_code)
    if not code:
        return {"ok": False, "error": f"无效的城市代码: {city_code}"}

    url = weather_page_url(code, range_type)
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            headers=_default_headers(),
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
                resp.encoding = getattr(resp, "apparent_encoding", None) or "utf-8"
            html = resp.text
    except Exception as exc:
        logger.warning("[weather] 抓取失败 {}: {}", url, exc)
        return {"ok": False, "error": f"抓取天气预报失败: {exc}", "url": url}

    return {
        "ok": True,
        "url": url,
        "html": html,
        "city_code": code,
        "range_type": range_type,
    }


def get_weather_forecast_impl(
    city_code: str | None = None,
    range_type: str = "7d",
    query_text: str = "",
) -> str:
    """获取天气预报精简 HTML。"""
    cfg = load_weather_config()
    code = _normalize_city_code(city_code or "") or _normalize_city_code(str(cfg.get("city_code", "")))
    if not code:
        return "未配置有效的 city_code，请在 config/weather.yaml 中设置。"

    resolved_range = normalize_weather_range(range_type)
    if query_text.strip():
        resolved_range = detect_weather_range(query_text)

    timeout = float(cfg.get("request_timeout", 20))
    fetched = fetch_weather_page(code, resolved_range, timeout=timeout)
    if not fetched.get("ok"):
        return str(fetched.get("error", "获取天气预报失败"))

    page_url = str(fetched.get("url", ""))
    raw_html = str(fetched.get("html", ""))
    if not raw_html.strip():
        return "页面内容为空，请稍后重试。"

    extracted = extract_weather_html(raw_html, resolved_range, page_url=page_url)
    if not extracted.get("ok"):
        return str(extracted.get("error", "解析天气预报失败"))

    missing = extracted.get("missing") or []
    if missing:
        logger.warning("[weather] 部分区块未找到: {}", missing)

    return str(extracted.get("html", ""))
