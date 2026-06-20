"""LangChain @tool 装饰器：天气预报工具。"""

from __future__ import annotations

from langchain_core.tools import tool

from src.tools.weather.core import get_weather_forecast_impl


@tool
def get_weather_forecast(
    city_code: str = "",
    range_type: str = "7d",
    query_text: str = "",
) -> str:
    """查询中国天气网天气预报（当天或 7 天），返回页面 HTML。默认 7 天、使用 config/weather.yaml 地区。

    Args:
        city_code: 可选，中国天气网 9 位城市代码（如 101110101）；留空则用配置
        range_type: 1d（当天）或 7d（7 天），默认 7d
        query_text: 用户原文，用于识别「今天」「7天」等关键词
    """
    return get_weather_forecast_impl(city_code or None, range_type=range_type, query_text=query_text)


WEATHER_TOOLS = [get_weather_forecast]
