"""实况补充：AQI、限行等（d1.weather.com.cn/sk_2d）。"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from loguru import logger

from src.tools.weather.render import LiveSnapshot

_DATASK_RE = re.compile(r"var\s+dataSK\s*=\s*(\{[\s\S]*?\});")
_SK_URL = "https://d1.weather.com.cn/sk_2d/{code}.html"


def aqi_level_label(value: str) -> str:
    try:
        n = int(float(str(value).strip()))
    except (ValueError, TypeError):
        return ""
    if n <= 50:
        return "优"
    if n <= 100:
        return "良"
    if n <= 150:
        return "轻度"
    if n <= 200:
        return "中度"
    if n <= 300:
        return "重度"
    return "严重"


def parse_sk_live(text: str) -> LiveSnapshot | None:
    match = _DATASK_RE.search(text or "")
    if not match:
        return None
    try:
        data: dict[str, Any] = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

    temp = str(data.get("temp") or "").strip()
    if temp and not temp.endswith("℃"):
        temp = f"{temp}℃"

    sd = str(data.get("SD") or data.get("sd") or "").strip().rstrip("%")
    humidity = f"相对湿度 {sd}%" if sd else ""

    wind_dir = str(data.get("WD") or "").strip()
    wind_spd = str(data.get("WS") or "").strip()
    wind = " ".join(x for x in (wind_dir, wind_spd) if x)

    time_raw = str(data.get("time") or "").strip()
    time_label = f"{time_raw} 实况" if time_raw else "实况"

    aqi = str(data.get("aqi") or "").strip()
    aqi_level = aqi_level_label(aqi) if aqi else ""
    limit = str(data.get("limitnumber") or "").strip()

    return LiveSnapshot(
        time_label=time_label,
        temp=temp,
        humidity=humidity,
        wind=wind,
        aqi_value=aqi,
        aqi_level=aqi_level,
        traffic_limit=limit,
    )


def fetch_sk_live(
    city_code: str,
    *,
    timeout: float = 15.0,
    headers: dict[str, str] | None = None,
) -> LiveSnapshot | None:
    code = (city_code or "").strip()
    if not code:
        return None
    url = _SK_URL.format(code=code)
    h = dict(headers or {})
    h.setdefault("Referer", "https://www.weather.com.cn/")
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=h) as client:
            resp = client.get(url)
            resp.raise_for_status()
            if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
                resp.encoding = getattr(resp, "charset_encoding", None) or "utf-8"
            return parse_sk_live(resp.text)
    except Exception as exc:
        logger.warning("[weather] sk_2d 抓取失败 {}: {}", url, exc)
        return None
