"""将中国天气网页面数据渲染为自包含的美观 HTML。"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from src.tools.weather.icons import icon_sprite_html, icon_sprite_url

WeatherRange = Literal["1d", "7d"]

_HOUR3DATA_RE = re.compile(r"var\s+hour3data\s*=\s*(\{[\s\S]*?\});")
_OBSERVE24_RE = re.compile(r"var\s+observe24h_data\s*=\s*(\{[\s\S]*?\});")
_WEATHER_BASE = "https://www.weather.com.cn/"


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
class LiveSnapshot:
    time_label: str = ""
    temp: str = ""
    humidity: str = ""
    wind: str = ""
    aqi_value: str = ""
    aqi_level: str = ""
    traffic_limit: str = ""


@dataclass
class WeatherView:
    location: str
    range_type: WeatherRange
    source_url: str
    live: LiveSnapshot | None = None
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


def _parse_observe24h(soup: BeautifulSoup) -> LiveSnapshot | None:
    raw = ""
    for script in soup.find_all("script"):
        body = script.string or ""
        if "observe24h_data" not in body:
            continue
        match = _OBSERVE24_RE.search(body)
        if match:
            raw = match.group(1)
            break
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    od = data.get("od") or {}
    rows = od.get("od2") or []
    if not rows or not isinstance(rows[0], dict):
        return None
    row = rows[0]
    od0 = str(od.get("od0") or "")
    hour = str(row.get("od21") or "")
    if len(od0) >= 10:
        time_label = f"{od0[8:10]}:{od0[10:12] if len(od0) >= 12 else '00'} 实况"
    elif hour:
        time_label = f"{hour.zfill(2)}:00 实况"
    else:
        time_label = "实况"
    temp = str(row.get("od22") or "").strip()
    if temp and not temp.endswith("℃"):
        temp = f"{temp}℃"
    humidity = str(row.get("od27") or "").strip()
    humidity_text = f"相对湿度 {humidity}%" if humidity else ""
    wind_dir = str(row.get("od24") or "").strip()
    wind_lvl = str(row.get("od25") or "").strip()
    wind = " ".join(x for x in (wind_dir, f"{wind_lvl}级" if wind_lvl else "") if x)
    return LiveSnapshot(
        time_label=time_label,
        temp=temp,
        humidity=humidity_text,
        wind=wind,
    )


def _pick_day_night_periods(periods: list[PeriodForecast]) -> list[PeriodForecast]:
    day: PeriodForecast | None = None
    night: PeriodForecast | None = None
    for p in periods:
        if "白天" in p.label and day is None:
            day = p
        elif "夜间" in p.label and night is None:
            night = p
    if day or night:
        return [p for p in (day, night) if p]
    return periods[:2]


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
        view.live = _parse_observe24h(soup)

    if range_type == "1d":
        block = soup.find(id="today")
        candidates: list[PeriodForecast] = []
        if block:
            for li in block.select("div.t > ul > li"):
                period = _parse_period_li(li)
                if period and period.label:
                    candidates.append(period)
        if not candidates:
            for li in soup.select("div.t > ul > li"):
                period = _parse_period_li(li)
                if period and period.label and ("白天" in period.label or "夜间" in period.label):
                    candidates.append(period)
        view.day_periods = _pick_day_night_periods(candidates)
    else:
        box = soup.find(id="7d")
        if box:
            for li in box.select("ul.t li"):
                day = _parse_daily_li(li)
                if day:
                    view.daily.append(day)

    return view


def _merge_live_snapshot(base: LiveSnapshot | None, extra: LiveSnapshot | None) -> LiveSnapshot | None:
    if not base and not extra:
        return None
    if not base:
        return extra
    if not extra:
        return base
    return LiveSnapshot(
        time_label=extra.time_label or base.time_label,
        temp=extra.temp or base.temp,
        humidity=extra.humidity or base.humidity,
        wind=extra.wind or base.wind,
        aqi_value=extra.aqi_value or base.aqi_value,
        aqi_level=extra.aqi_level or base.aqi_level,
        traffic_limit=extra.traffic_limit or base.traffic_limit,
    )


def _icon_img(code: str, *, alt: str = "", size: int = 48) -> str:
    return icon_sprite_html(code, size=size, alt=alt)


def _render_sk_panel(live: LiveSnapshot | None) -> str:
    if not live or not (live.temp or live.humidity or live.wind):
        return ""
    metrics: list[str] = []
    if live.humidity:
        metrics.append(
            f'<div class="wx-sk-metric"><span class="wx-sk-ico wx-ico-hum">💧</span>'
            f"<span>{html.escape(live.humidity)}</span></div>"
        )
    if live.wind:
        metrics.append(
            f'<div class="wx-sk-metric"><span class="wx-sk-ico wx-ico-wind">🌬</span>'
            f"<span>{html.escape(live.wind)}</span></div>"
        )
    if live.traffic_limit:
        metrics.append(
            f'<div class="wx-sk-metric"><span class="wx-sk-ico wx-ico-car">🚗</span>'
            f"<span>{html.escape(live.traffic_limit)}</span></div>"
        )
    if live.aqi_value or live.aqi_level:
        aqi_text = f"{live.aqi_value}{live.aqi_level}" if live.aqi_value and live.aqi_level else (
            live.aqi_value or live.aqi_level
        )
        metrics.append(
            f'<div class="wx-sk-metric wx-sk-aqi"><span class="wx-sk-ico wx-ico-aqi">🍃</span>'
            f"<span>{html.escape(aqi_text)}</span></div>"
        )
    return (
        '<article class="wx-today-col wx-sk">'
        f'<div class="wx-sk-time">{html.escape(live.time_label or "实况")}</div>'
        '<div class="wx-sk-main">'
        '<div class="wx-sk-therm" aria-hidden="true">'
        '<svg viewBox="0 0 24 64" width="28" height="64">'
        '<rect x="9" y="4" width="6" height="44" rx="3" fill="rgba(255,255,255,.45)"/>'
        '<circle cx="12" cy="52" r="9" fill="#fff"/>'
        '<rect x="10.5" y="12" width="3" height="32" rx="1.5" fill="#fff"/>'
        "</svg></div>"
        f'<div class="wx-sk-temp">{html.escape(live.temp or "—")}</div>'
        "</div>"
        f'<div class="wx-sk-metrics">{"".join(metrics)}</div>'
        "</article>"
    )


def _render_period_column(p: PeriodForecast, tone: str) -> str:
    meta_parts = []
    if p.wind:
        meta_parts.append(p.wind if p.wind.startswith("<") else f"≈ {p.wind}")
    if p.extra:
        meta_parts.append(p.extra)
    meta = " · ".join(meta_parts)
    return (
        f'<article class="wx-today-col wx-period-col wx-{tone}">'
        f'<div class="wx-period-label">{html.escape(p.label)}</div>'
        f'<div class="wx-period-icon">{_icon_img(p.icon_code, alt=p.weather, size=52)}</div>'
        f'<div class="wx-period-wea">{html.escape(p.weather)}</div>'
        f'<div class="wx-period-temp">{html.escape(p.temp or "—")}</div>'
        f'<div class="wx-period-meta">{html.escape(meta)}</div>'
        "</article>"
    )


def _render_today_board(live: LiveSnapshot | None, periods: list[PeriodForecast]) -> str:
    cols: list[str] = []
    sk = _render_sk_panel(live)
    if sk:
        cols.append(sk)
    tones = ["day", "night"]
    for idx, p in enumerate(periods[:2]):
        cols.append(_render_period_column(p, tones[idx] if idx < len(tones) else "day"))
    if not cols:
        return ""
    n = len(cols)
    style = f' style="grid-template-columns:repeat({n},minmax(0,1fr))"'
    return (
        f'<section id="today" class="wx-section wx-main">'
        f'<div class="wx-today-board"{style}>{"".join(cols)}</div>'
        "</section>"
    )


def _render_period_cards(periods: list[PeriodForecast], live: LiveSnapshot | None = None) -> str:
    if not periods and not live:
        return ""
    board = _render_today_board(live, periods)
    if board:
        return board
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
    return f'<section id="today" class="wx-section wx-main"><div class="wx-period-grid">{"".join(cards)}</div></section>'


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
    return f'<section id="7d" class="wx-section wx-main"><div class="wx-day-row">{"".join(cards)}</div></section>'


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
        '<section id="curve" class="wx-section wx-curve">'
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
        '<div class="livezs wx-section">'
        '<h2 class="wx-title">生活指数</h2>'
        f'<div class="wx-life-grid">{"".join(cards)}</div>'
        "</div>"
    )


_WX_STYLES = """
:root{
  color-scheme:light dark;
  --wx-bg:var(--bg-chat,#f4f7fb);
  --wx-fg:var(--fg,#1f2937);
  --wx-fg-muted:var(--fg-muted,#64748b);
  --wx-card-bg:var(--assistant-bubble-bg,#fff);
  --wx-card-border:var(--assistant-bubble-border,#d4d4d4);
  --wx-link:var(--link,#0369a1);
  --wx-accent-temp:var(--info,#2563eb);
  --wx-accent-low:var(--success,#16a34a);
  --wx-chip-bg:color-mix(in srgb,var(--info,#0ea5e9) 14%,var(--wx-card-bg));
  --wx-chip-fg:var(--wx-accent-temp);
  --wx-sk-bg:linear-gradient(165deg,#fdba74 0%,#f97316 42%,#ea580c 100%);
  --wx-sk-fg:#fff;
  --wx-sk-fg-soft:rgba(255,255,255,.92);
  --wx-sk-aqi-fg:#ecfccb;
}
:root[data-theme-mode="dark"]{
  --wx-chip-fg:var(--link,#93c5fd);
  --wx-chip-bg:color-mix(in srgb,var(--link,#93c5fd) 22%,var(--wx-card-bg));
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme-mode="light"]){
    --wx-chip-fg:var(--link,#93c5fd);
    --wx-chip-bg:color-mix(in srgb,var(--link,#93c5fd) 22%,var(--wx-card-bg));
  }
}
body{margin:0;padding:12px;background:var(--wx-bg);color:var(--wx-fg);font-family:"Microsoft YaHei",system-ui,sans-serif;}
.wx-wrap{max-width:600px;margin:0 auto;}
.wx-header{margin-bottom:14px;}
.wx-header h1{margin:0 0 4px;font-size:18px;font-weight:700;color:var(--wx-fg);}
.wx-header p{margin:0;font-size:12px;color:var(--wx-fg-muted);}
.wx-header a{color:var(--wx-link);text-decoration:none;}
.wx-section{margin-bottom:16px;}
.wx-title{margin:0 0 10px;font-size:15px;font-weight:600;color:var(--wx-fg);}
.wx-period-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;}
.wx-today-board{display:grid;grid-template-columns:1.15fr 1fr 1fr;gap:0;background:var(--wx-card-bg);border:1px solid var(--wx-card-border);border-radius:12px;overflow:hidden;min-height:220px;}
.wx-today-col{padding:14px 12px;border-right:1px solid var(--wx-card-border);display:flex;flex-direction:column;align-items:center;text-align:center;}
.wx-today-col:last-child{border-right:none;}
.wx-sk{align-items:stretch;text-align:left;background:var(--wx-sk-bg);border-right:1px solid rgba(0,0,0,.12);}
.wx-sk-time{font-size:12px;color:var(--wx-sk-fg-soft);margin-bottom:8px;font-weight:500;}
.wx-sk-main{display:flex;align-items:center;gap:10px;margin-bottom:12px;}
.wx-sk-temp{font-size:42px;font-weight:800;color:var(--wx-sk-fg);line-height:1;letter-spacing:-.02em;text-shadow:0 1px 2px rgba(0,0,0,.18);}
.wx-sk-therm{flex-shrink:0;filter:drop-shadow(0 1px 2px rgba(0,0,0,.15));}
.wx-sk-metrics{display:grid;grid-template-columns:1fr 1fr;gap:8px 10px;width:100%;font-size:11px;color:var(--wx-sk-fg-soft);font-weight:500;}
.wx-sk-metric{display:flex;align-items:flex-start;gap:4px;line-height:1.35;}
.wx-sk-ico{flex-shrink:0;font-size:12px;opacity:.95;}
.wx-sk-aqi span:last-child{color:var(--wx-sk-aqi-fg);font-weight:700;text-shadow:0 1px 1px rgba(0,0,0,.2);}
.wx-period-col{justify-content:flex-start;padding-top:18px;background:var(--wx-card-bg);}
.wx-period-label{font-size:13px;color:color-mix(in srgb,var(--wx-fg) 72%,var(--wx-fg-muted));margin-bottom:8px;font-weight:500;}
.wx-period-icon{margin:4px 0 8px;}
.wx-period-wea{font-size:15px;font-weight:700;margin-bottom:6px;color:var(--wx-fg);}
.wx-period-temp{font-size:34px;font-weight:800;color:var(--wx-fg);line-height:1;margin-bottom:8px;}
.wx-period-meta{font-size:11px;color:color-mix(in srgb,var(--wx-fg) 65%,var(--wx-fg-muted));line-height:1.5;}
.wx-period-col.wx-day{background:var(--wx-card-bg);}
.wx-period-col.wx-night{background:var(--wx-card-bg);}
.wx-period{border-radius:12px;padding:12px 14px;border:1px solid var(--wx-card-border);}
.wx-day{background:var(--wx-card-bg);color:var(--wx-fg);}
.wx-night{background:var(--wx-card-bg);color:var(--wx-fg);}
.wx-period-head{display:flex;align-items:center;justify-content:space-between;gap:8px;}
.wx-period-head h3{margin:0;font-size:16px;font-weight:700;}
.wx-wea{margin:10px 0 4px;font-size:20px;font-weight:700;}
.wx-temp{margin:0;font-size:28px;font-weight:800;letter-spacing:-.02em;}
.wx-meta{margin:8px 0 0;font-size:12px;opacity:.85;}
.wx-icon{display:inline-block;flex-shrink:0;vertical-align:middle;}
.wx-icon-sprite-wrap{line-height:0;}
.wx-icon-sprite{display:block;}
.wx-day-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(72px,1fr));gap:8px;}
.wx-day-card{background:var(--wx-card-bg);border:1px solid var(--wx-card-border);border-radius:10px;padding:8px 6px;text-align:center;}
.wx-day-label{font-size:11px;color:var(--wx-fg-muted);margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.wx-day-card .wx-icon{margin:0 auto 4px;display:block;}
.wx-day-wea{font-size:12px;font-weight:600;margin-bottom:2px;color:var(--wx-fg);}
.wx-day-temp{font-size:13px;font-weight:700;color:color-mix(in srgb,var(--wx-accent-low) 80%,var(--wx-fg));}
.wx-day-wind{font-size:10px;color:var(--wx-fg-muted);margin-top:2px;}
.wx-hour-row{display:flex;gap:6px;overflow-x:auto;padding-bottom:4px;}
.wx-hour{flex:0 0 68px;background:var(--wx-card-bg);border:1px solid var(--wx-card-border);border-radius:8px;padding:6px 4px;text-align:center;}
.wx-hour-time{font-size:10px;color:var(--wx-fg-muted);margin-bottom:2px;white-space:nowrap;}
.wx-hour .wx-icon{margin:0 auto 2px;display:block;}
.wx-hour-wea{font-size:10px;margin-bottom:2px;color:var(--wx-fg);}
.wx-hour-temp{font-size:12px;font-weight:700;color:color-mix(in srgb,var(--wx-accent-temp) 75%,var(--wx-fg));}
.wx-life-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;}
.wx-life{background:var(--wx-card-bg);border:1px solid var(--wx-card-border);border-radius:10px;padding:10px;min-height:88px;}
.wx-life-level{display:inline-block;font-size:10px;font-weight:700;color:var(--wx-chip-fg);background:var(--wx-chip-bg);border-radius:999px;padding:1px 6px;margin-bottom:4px;}
.wx-life-name{font-size:13px;font-weight:700;margin-bottom:3px;line-height:1.3;color:var(--wx-fg);}
.wx-life-tip{font-size:11px;line-height:1.4;color:color-mix(in srgb,var(--wx-fg) 70%,var(--wx-fg-muted));display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;}
@media (max-width:480px){.wx-period-grid{grid-template-columns:1fr;}.wx-life-grid{grid-template-columns:repeat(2,minmax(0,1fr));}.wx-today-board{grid-template-columns:1fr !important;}.wx-today-col{border-right:none;border-bottom:1px solid var(--wx-card-border);}.wx-sk{border-right:none;border-bottom:1px solid rgba(0,0,0,.12);}.wx-today-col:last-child{border-bottom:none;}}
"""


def _abs_url(url: str, *, base: str = _WEATHER_BASE) -> str:
    u = (url or "").strip()
    if not u or u.startswith("#") or u.startswith("data:") or u.startswith("javascript:"):
        return u
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://") or u.startswith("https://"):
        return u
    return urljoin(base, u)


def _absolutize_fragment(root: Tag, *, page_url: str) -> None:
    for el in root.find_all(True):
        for attr in ("src", "href", "data-src"):
            val = el.get(attr)
            if val:
                el[attr] = _abs_url(val, base=page_url)


def _strip_curve_and_livezs(root: Tag) -> None:
    for sub in list(root.find_all(id="curve")):
        sub.decompose()
    for sub in list(root.find_all("div", class_=lambda c: c and "livezs" in c)):
        sub.decompose()


def _clone_tag(node: Tag | None) -> Tag | None:
    if node is None:
        return None
    frag = BeautifulSoup(str(node), "html.parser")
    tag_id = node.get("id")
    if tag_id:
        return frag.find(id=tag_id)
    return frag.find(node.name) or frag.div


def extract_main_section(soup: BeautifulSoup, range_type: WeatherRange, *, page_url: str) -> str:
    """提取 #today / #7d，并移除内嵌的 #curve、div.livezs。"""
    block_id = "today" if range_type == "1d" else "7d"
    node = soup.find(id=block_id)
    if not node:
        return ""
    clone = _clone_tag(node)
    if not clone:
        return ""
    _strip_curve_and_livezs(clone)
    _absolutize_fragment(clone, page_url=page_url)
    return str(clone)


def extract_livezs_section(soup: BeautifulSoup, *, page_url: str) -> str:
    """提取 div.livezs 生活指数区块（仅用于解析校验）。"""
    node = soup.select_one("div.livezs")
    if not node:
        return ""
    clone = _clone_tag(node)
    if not clone:
        return ""
    _absolutize_fragment(clone, page_url=page_url)
    return str(clone)


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
        body_parts.append(_render_period_cards(view.day_periods, view.live))
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


def build_weather_page_html(
    html: str,
    range_type: WeatherRange,
    *,
    page_url: str,
    sk_live: LiveSnapshot | None = None,
) -> dict[str, Any]:
    view = parse_weather_view(html, range_type, page_url=page_url)
    if range_type == "1d" and sk_live:
        view.live = _merge_live_snapshot(view.live, sk_live)
    has_content = (
        view.live
        or view.day_periods
        or view.daily
        or view.hours
        or view.life_indices
    )
    if not has_content:
        return {"ok": False, "error": "未能解析天气预报数据"}
    return {"ok": True, "html": render_weather_html(view)}
