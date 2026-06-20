"""将中国天气网页面数据渲染为自包含的美观 HTML。"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from bs4 import BeautifulSoup

from src.tools.weather.icons import icon_sprite_html, icon_sprite_url

WeatherRange = Literal["1d", "7d"]

_HOUR3DATA_RE = re.compile(r"var\s+hour3data\s*=\s*(\{[\s\S]*?\});")


@dataclass
class PeriodForecast:
    label: str
    weather: str
    temp: str
    wind: str
    extra: str = ""
    icon_code: str = ""


@dataclass
class DailyForecast:
    label: str
    weather: str
    temp_high: str
    temp_low: str
    wind: str
    icon_code: str = ""


@dataclass
class LifeIndex:
    level: str
    name: str
    tip: str


@dataclass
class HourForecast:
    time: str
    weather: str
    temp: str
    wind: str
    icon_code: str = ""


@dataclass
class WeatherView:
    location: str
    range_type: WeatherRange
    source_url: str
    day_periods: list[PeriodForecast] = field(default_factory=list)
    daily: list[DailyForecast] = field(default_factory=list)
    hours: list[HourForecast] = field(default_factory=list)
    life_indices: list[LifeIndex] = field(default_factory=list)


def icon_url(code: str) -> str:
    """返回天气图标雪碧图 URL（blue80.png）。"""
    if not (code or "").strip():
        return ""
    return icon_sprite_url(code)


def _text(el: Any) -> str:
    return el.get_text(" ", strip=True) if el is not None else ""


def _icon_code(el: Any) -> str:
    if el is None:
        return ""
    for tag in el.select("big"):
        for cls in tag.get("class") or []:
            if cls.startswith(("d", "n")) and len(cls) <= 4:
                return cls.lower()
    return ""


def _extract_location(soup: BeautifulSoup) -> str:
    parts: list[str] = []
    for el in soup.select(".crumbs a, .crumbs fl"):
        t = el.get_text(strip=True)
        if t and t not in {">", "全国"}:
            parts.append(t)
    if parts:
        return " · ".join(parts)
    title = soup.title.get_text(strip=True) if soup.title else ""
    return title.split("天气预报")[0].strip() or "天气预报"


def _parse_period_li(li: Any) -> PeriodForecast | None:
    h1 = li.select_one("h1")
    wea = li.select_one("p.wea")
    if not h1 or not wea:
        return None
    tem = li.select_one("p.tem")
    temp = _text(tem).replace(" ", "")
    sun = li.select_one("p.sun")
    sky = li.select_one(".sky .txt")
    extra = _text(sun) or _text(sky)
    win = _text(li.select_one("p.win"))
    return PeriodForecast(
        label=_text(h1),
        weather=_text(wea),
        temp=temp,
        wind=win,
        extra=extra,
        icon_code=_icon_code(li),
    )


def _parse_daily_li(li: Any) -> DailyForecast | None:
    h1 = li.select_one("h1")
    wea = li.select_one("p.wea")
    if not h1 or not wea:
        return None
    tem = li.select_one("p.tem")
    high = tem.select_one("span") if tem else None
    low = tem.select_one("i") if tem else None
    high_t = _text(high)
    low_t = _text(low)
    return DailyForecast(
        label=_text(h1),
        weather=_text(wea),
        temp_high=high_t,
        temp_low=low_t,
        wind=_text(li.select_one("p.win")),
        icon_code=_icon_code(li),
    )


def _parse_live_indices(soup: BeautifulSoup) -> list[LifeIndex]:
    items: list[LifeIndex] = []
    for li in soup.select("div.livezs li"):
        name_el = li.select_one("em")
        if not name_el:
            continue
        items.append(
            LifeIndex(
                level=_text(li.select_one("span")),
                name=_text(name_el),
                tip=_text(li.select_one("p")),
            )
        )
    return items


def _parse_hour3data(soup: BeautifulSoup, range_type: WeatherRange) -> list[HourForecast]:
    raw = ""
    for script in soup.find_all("script"):
        body = script.string or ""
        if "hour3data" not in body:
            continue
        match = _HOUR3DATA_RE.search(body)
        if match:
            raw = match.group(1)
            break
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    key = "1d" if range_type == "1d" else "7d"
    rows = data.get(key) or data.get("1d") or []
    if key == "7d" and rows and isinstance(rows[0], list):
        rows = rows[0]

    hours: list[HourForecast] = []
    for row in rows:
        if not isinstance(row, str):
            continue
        parts = row.split(",")
        if len(parts) < 5:
            continue
        hours.append(
            HourForecast(
                time=parts[0],
                icon_code=parts[1].strip().lower(),
                weather=parts[2],
                temp=parts[3],
                wind=parts[4],
            )
        )
    return hours


def parse_weather_view(html: str, range_type: WeatherRange, *, page_url: str) -> WeatherView:
    soup = BeautifulSoup(html, "html.parser")
    view = WeatherView(
        location=_extract_location(soup),
        range_type=range_type,
        source_url=page_url,
        life_indices=_parse_live_indices(soup),
        hours=_parse_hour3data(soup, range_type),
    )

    if range_type == "1d":
        block = soup.find(id="today")
        if block:
            for li in block.select("div.t li"):
                period = _parse_period_li(li)
                if period:
                    view.day_periods.append(period)
        if not view.day_periods:
            for li in soup.select("div.t li"):
                period = _parse_period_li(li)
                if period and ("白天" in period.label or "夜间" in period.label):
                    view.day_periods.append(period)
    else:
        box = soup.find(id="7d")
        if box:
            for li in box.select("ul.t li"):
                day = _parse_daily_li(li)
                if day:
                    view.daily.append(day)

    return view


def _icon_img(code: str, *, alt: str = "", size: int = 48) -> str:
    return icon_sprite_html(code, size=size, alt=alt)


def _render_period_cards(periods: list[PeriodForecast]) -> str:
    if not periods:
        return ""
    cards: list[str] = []
    for p in periods:
        tone = "night" if "夜" in p.label else "day"
        meta = " · ".join(x for x in (p.wind, p.extra) if x)
        cards.append(
            f'<article class="wx-period wx-{tone}">'
            f'<div class="wx-period-head">'
            f"<h3>{html.escape(p.label)}</h3>{_icon_img(p.icon_code, alt=p.weather, size=56)}"
            f"</div>"
            f'<p class="wx-wea">{html.escape(p.weather)}</p>'
            f'<p class="wx-temp">{html.escape(p.temp or "—")}</p>'
            f'<p class="wx-meta">{html.escape(meta)}</p>'
            f"</article>"
        )
    return f'<section class="wx-section"><div class="wx-period-grid">{"".join(cards)}</div></section>'


def _render_daily_row(days: list[DailyForecast]) -> str:
    if not days:
        return ""
    cards: list[str] = []
    for d in days:
        temp = f"{d.temp_high}/{d.temp_low}" if d.temp_high and d.temp_low else d.temp_high or d.temp_low or "—"
        cards.append(
            f'<article class="wx-day-card">'
            f'<div class="wx-day-label">{html.escape(d.label)}</div>'
            f"{_icon_img(d.icon_code, alt=d.weather, size=36)}"
            f'<div class="wx-day-wea">{html.escape(d.weather)}</div>'
            f'<div class="wx-day-temp">{html.escape(temp)}</div>'
            f'<div class="wx-day-wind">{html.escape(d.wind)}</div>'
            f"</article>"
        )
    return f'<section class="wx-section"><div class="wx-day-row">{"".join(cards)}</div></section>'


def _render_hours(hours: list[HourForecast]) -> str:
    if not hours:
        return ""
    items: list[str] = []
    for h in hours:
        items.append(
            f'<div class="wx-hour">'
            f'<div class="wx-hour-time">{html.escape(h.time)}</div>'
            f"{_icon_img(h.icon_code, alt=h.weather, size=30)}"
            f'<div class="wx-hour-wea">{html.escape(h.weather)}</div>'
            f'<div class="wx-hour-temp">{html.escape(h.temp)}</div>'
            f"</div>"
        )
    return (
        '<section class="wx-section">'
        '<h2 class="wx-title">逐小时预报</h2>'
        f'<div class="wx-hour-row">{"".join(items)}</div>'
        "</section>"
    )


def _render_life(indices: list[LifeIndex]) -> str:
    if not indices:
        return ""
    cards: list[str] = []
    for item in indices:
        cards.append(
            f'<article class="wx-life">'
            f'<div class="wx-life-level">{html.escape(item.level)}</div>'
            f'<div class="wx-life-name">{html.escape(item.name)}</div>'
            f'<div class="wx-life-tip">{html.escape(item.tip)}</div>'
            f"</article>"
        )
    return (
        '<section class="wx-section">'
        '<h2 class="wx-title">生活指数</h2>'
        f'<div class="wx-life-grid">{"".join(cards)}</div>'
        "</section>"
    )


_WX_STYLES = """
:root{color-scheme:light;}
body{margin:0;padding:12px;background:#f4f7fb;color:#1f2937;font-family:"Microsoft YaHei",system-ui,sans-serif;}
.wx-wrap{max-width:600px;margin:0 auto;}
.wx-header{margin-bottom:14px;}
.wx-header h1{margin:0 0 4px;font-size:18px;font-weight:700;}
.wx-header p{margin:0;font-size:12px;color:#64748b;}
.wx-header a{color:#0369a1;text-decoration:none;}
.wx-section{margin-bottom:16px;}
.wx-title{margin:0 0 10px;font-size:15px;font-weight:600;}
.wx-period-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;}
.wx-period{border-radius:12px;padding:12px 14px;border:1px solid rgba(255,255,255,.35);}
.wx-day{background:linear-gradient(145deg,#fff7e6,#fde68a);color:#78350f;}
.wx-night{background:linear-gradient(145deg,#e0e7ff,#c7d2fe);color:#312e81;}
.wx-period-head{display:flex;align-items:center;justify-content:space-between;gap:8px;}
.wx-period-head h3{margin:0;font-size:16px;font-weight:700;}
.wx-wea{margin:10px 0 4px;font-size:20px;font-weight:700;}
.wx-temp{margin:0;font-size:28px;font-weight:800;letter-spacing:-.02em;}
.wx-meta{margin:8px 0 0;font-size:12px;opacity:.85;}
.wx-icon{display:inline-block;flex-shrink:0;vertical-align:middle;}
.wx-icon-sprite-wrap{line-height:0;}
.wx-icon-sprite{display:block;}
.wx-day-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(72px,1fr));gap:8px;}
.wx-day-card{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:8px 6px;text-align:center;}
.wx-day-label{font-size:11px;color:#64748b;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.wx-day-card .wx-icon{margin:0 auto 4px;display:block;}
.wx-day-wea{font-size:12px;font-weight:600;margin-bottom:2px;}
.wx-day-temp{font-size:13px;font-weight:700;color:#0f766e;}
.wx-day-wind{font-size:10px;color:#64748b;margin-top:2px;}
.wx-hour-row{display:flex;gap:6px;overflow-x:auto;padding-bottom:4px;}
.wx-hour{flex:0 0 68px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:6px 4px;text-align:center;}
.wx-hour-time{font-size:10px;color:#64748b;margin-bottom:2px;white-space:nowrap;}
.wx-hour .wx-icon{margin:0 auto 2px;display:block;}
.wx-hour-wea{font-size:10px;margin-bottom:2px;}
.wx-hour-temp{font-size:12px;font-weight:700;color:#0369a1;}
.wx-life-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;}
.wx-life{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:10px;min-height:88px;}
.wx-life-level{display:inline-block;font-size:10px;font-weight:700;color:#0369a1;background:#e0f2fe;border-radius:999px;padding:1px 6px;margin-bottom:4px;}
.wx-life-name{font-size:13px;font-weight:700;margin-bottom:3px;line-height:1.3;}
.wx-life-tip{font-size:11px;line-height:1.4;color:#475569;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;}
@media (max-width:480px){.wx-period-grid{grid-template-columns:1fr;}.wx-life-grid{grid-template-columns:repeat(2,minmax(0,1fr));}}
"""


def render_weather_html(view: WeatherView) -> str:
    range_label = "当天预报" if view.range_type == "1d" else "7天预报"
    body_parts = [
        '<div class="wx-wrap">',
        '<header class="wx-header">',
        f"<h1>{html.escape(view.location)} · {range_label}</h1>",
        f'<p>数据来源：<a href="{html.escape(view.source_url)}" target="_blank" rel="noopener">中国天气网</a></p>',
        "</header>",
    ]

    if view.range_type == "1d":
        body_parts.append(_render_period_cards(view.day_periods))
    else:
        body_parts.append(_render_daily_row(view.daily))

    body_parts.append(_render_hours(view.hours))
    body_parts.append(_render_life(view.life_indices))
    body_parts.append("</div>")

    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<style>{_WX_STYLES}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{''.join(body_parts)}\n"
        "</body>\n"
        "</html>"
    )


def build_weather_page_html(html: str, range_type: WeatherRange, *, page_url: str) -> dict[str, Any]:
    view = parse_weather_view(html, range_type, page_url=page_url)
    has_content = view.day_periods or view.daily or view.hours or view.life_indices
    if not has_content:
        return {"ok": False, "error": "未能解析天气预报数据"}
    return {"ok": True, "html": render_weather_html(view)}
