"""中国天气网（weather.com.cn）天气预报：当天 / 7 天，返回美化 HTML。"""

from __future__ import annotations

import re
from typing import Any, Literal

import httpx
from loguru import logger

from src.infra.config import load_search_config, load_weather_config
from src.tools.weather.render import build_weather_page_html

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
    """获取天气预报美化 HTML。"""
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

    rendered = build_weather_page_html(raw_html, resolved_range, page_url=page_url)
    if not rendered.get("ok"):
        return str(rendered.get("error", "解析天气预报失败"))

    return str(rendered.get("html", ""))
