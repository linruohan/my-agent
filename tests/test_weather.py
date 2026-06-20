"""weather 工具测试。"""

from __future__ import annotations

from src.tools.weather import (
    _normalize_city_code,
    build_embed_html,
    detect_weather_range,
    extract_7d_weather_html,
    extract_today_weather_html,
    normalize_weather_range,
    parse_weather_slash_args,
    weather_page_url,
)

SAMPLE_7D_HTML = """
<html><head>
<link rel="stylesheet" href="https://i.tq121.com.cn/c/weather2015/bluesky/c_7d.css"/>
</head><body>
<div id="7d" class="c7d">
<ul class="t clearfix">
<li><h1>20日（今天）</h1><p class="wea">中雨</p></li>
<li><h1>21日（明天）</h1><p class="wea">小雨</p></li>
</ul>
<div class="curve_livezs" id="curve"><div class="tem"></div></div>
<script>var hour3data={"7d":[]};</script>
<div class="livezs curve_livezs">
<ul class="clearfix"><li><em>运动指数</em><p>较不宜</p></li></ul>
</div>
</div>
</body></html>
"""

SAMPLE_1D_HTML = """
<html><head>
<link rel="stylesheet" href="https://i.tq121.com.cn/c/weather2019/weather1d.css"/>
</head><body>
<div id="today" class="today clearfix">
<input id="hidden_title" type="hidden" value=""/>
<input id="update_time" type="hidden" value=""/>
<input id="fc_24h_internal_update_time" type="hidden" value=""/>
<div class="t">
<ul class="clearfix">
<li><h1>20日白天</h1><p class="wea">中雨</p><p class="tem"><span>26</span><em>°C</em></p></li>
<li><h1>20日夜间</h1><p class="wea">小雨</p><p class="tem"><span>20</span><em>°C</em></p></li>
</ul>
</div>
<input id="fc_3h_internal_update_time" type="hidden" value=""/>
<div class="curve_livezs" id="curve"><div class="tem"></div></div>
<script>var hour3data={"1d":["20日11时,d02,阴,25℃"]};</script>
</div>
<div class="left-div"><div class="livezs">
<ul class="clearfix"><li><em>感冒指数</em><p>极易感冒</p></li></ul>
</div></div>
</body></html>
"""


def test_normalize_city_code():
    assert _normalize_city_code("101110101") == "101110101"
    assert _normalize_city_code("abc") is None


def test_detect_weather_range():
    assert detect_weather_range("天气预报") == "7d"
    assert detect_weather_range("7天天气") == "7d"
    assert detect_weather_range("今天天气") == "1d"
    assert detect_weather_range("今日预报") == "1d"
    assert detect_weather_range("当天天气怎么样") == "1d"


def test_parse_weather_slash_args():
    assert parse_weather_slash_args("") == ("", "7d")
    assert parse_weather_slash_args("101110101") == ("101110101", "7d")
    assert parse_weather_slash_args("今天") == ("", "1d")
    assert parse_weather_slash_args("7天") == ("", "7d")
    assert parse_weather_slash_args("101110101 今天") == ("101110101", "1d")


def test_weather_page_url():
    assert weather_page_url("101110101", "1d").endswith("/weather1d/101110101.shtml")
    assert weather_page_url("101110101", "7d").endswith("/weather/101110101.shtml")


def test_extract_today_weather_html():
    result = extract_today_weather_html(
        SAMPLE_1D_HTML,
        page_url="https://www.weather.com.cn/weather1d/101110101.shtml",
    )
    assert result["ok"] is True
    html = result["html"]
    assert "20日白天" in html
    assert "20日夜间" in html
    assert 'id="curve"' in html
    assert "hour3data" in html
    assert "感冒指数" in html
    assert "weather1d.css" in html
    assert "<base" in html


def test_extract_7d_weather_html():
    result = extract_7d_weather_html(
        SAMPLE_7D_HTML,
        page_url="https://www.weather.com.cn/weather/101110101.shtml",
    )
    assert result["ok"] is True
    html = result["html"]
    assert 'id="7d"' in html
    assert "20日（今天）" in html
    assert 'id="curve"' in html
    assert "hour3data" in html
    assert "运动指数" in html
    assert html.count('id="curve"') == 1
    assert html.count("运动指数") == 1
    assert "c_7d.css" in html


def test_build_embed_html():
    html = build_embed_html(
        ["<div>test</div>"],
        css_hrefs=["https://example.com/a.css"],
        script_srcs=["https://example.com/a.js"],
        page_url="https://www.weather.com.cn/weather/101110101.shtml",
    )
    assert "test</div>" in html
    assert "a.css" in html
    assert "a.js" in html


def test_normalize_weather_range():
    assert normalize_weather_range("1d") == "1d"
    assert normalize_weather_range("7d") == "7d"
    assert normalize_weather_range("") == "7d"
