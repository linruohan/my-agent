"""天气意图识别测试。"""

from __future__ import annotations

from src.ui.input_intent import (
    INTENT_SLASH_WEATHER,
    INTENT_WEATHER,
    parse_slash_command,
    resolve_input_intent,
)


def test_slash_weather():
    intent = parse_slash_command("/weather")
    assert intent is not None
    assert intent.kind == INTENT_SLASH_WEATHER
    assert intent.weather_range == "7d"

    intent2 = parse_slash_command("/weather 101110101")
    assert intent2 is not None
    assert intent2.weather_city_code == "101110101"
    assert intent2.weather_range == "7d"

    intent3 = parse_slash_command("/weather 今天")
    assert intent3 is not None
    assert intent3.weather_range == "1d"

    intent4 = parse_slash_command("/weather 7天")
    assert intent4 is not None
    assert intent4.weather_range == "7d"


def test_weather_keyword():
    intent = resolve_input_intent("天气预报", [], llm=None)
    assert intent.kind == INTENT_WEATHER
    assert intent.weather_range == "7d"

    intent2 = resolve_input_intent("今天天气怎么样", [], llm=None)
    assert intent2.kind == INTENT_WEATHER
    assert intent2.weather_range == "1d"
