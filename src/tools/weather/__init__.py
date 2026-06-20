"""天气预报工具包。"""

from src.tools.weather.core import (
    WeatherRange,
    WEATHER_RANGE_LABELS,
    WEATHER_URLS,
    _normalize_city_code,
    detect_weather_range,
    fetch_weather_page,
    get_weather_forecast_impl,
    normalize_weather_range,
    parse_weather_slash_args,
    weather_page_url,
)
from src.tools.weather.icons import icon_position, icon_sprite_html, icon_sprite_url
from src.tools.weather.render import build_weather_page_html, icon_url, parse_weather_view
from src.tools.weather.tools import WEATHER_TOOLS, get_weather_forecast

__all__ = [
    "WeatherRange",
    "WEATHER_RANGE_LABELS",
    "WEATHER_URLS",
    "WEATHER_TOOLS",
    "_normalize_city_code",
    "build_weather_page_html",
    "detect_weather_range",
    "fetch_weather_page",
    "get_weather_forecast",
    "get_weather_forecast_impl",
    "icon_position",
    "icon_sprite_html",
    "icon_sprite_url",
    "icon_url",
    "normalize_weather_range",
    "parse_weather_slash_args",
    "parse_weather_view",
    "weather_page_url",
]
