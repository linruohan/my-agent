"""weather 工具测试。"""

from __future__ import annotations

from src.tools.weather import (
    _normalize_city_code,
    detect_weather_range,
    normalize_weather_range,
    parse_weather_slash_args,
    weather_page_url,
)
from src.tools.weather.live import aqi_level_label, parse_sk_live
from src.tools.weather_render import build_weather_page_html, icon_url, parse_weather_view
from src.tools.weather_icons import icon_position, icon_sprite_html

SAMPLE_SK = (
    'var dataSK={"temp":"22.8","SD":"76%","WD":"西北风","WS":"1级","time":"08:50",'
    '"aqi":"20","limitnumber":"不限行"};'
)

SAMPLE_1D_HTML = """
<html><head><title>西安天气预报</title></head><body>
<div class="crumbs"><a>陕西</a><a>西安</a><a>城区</a></div>
<div id="today" class="today clearfix">
<div class="t">
<ul class="clearfix">
<li><h1>20日白天</h1><big class="jpg80 d08"></big><p class="wea">中雨</p>
<p class="tem"><span>26</span><em>°C</em></p><p class="win"><span>&lt;3级</span></p>
<p class="sun sunUp"><span>日出 05:32</span></p></li>
<li><h1>20日夜间</h1><big class="jpg80 n07"></big><p class="wea">小雨</p>
<p class="tem"><span>20</span><em>°C</em></p><p class="win"><span>&lt;3级</span></p>
<p class="sun sunDown"><span>日落 19:59</span></p></li>
</ul></div>
<div class="curve_livezs" id="curve"><div class="time"></div><div class="wpic"></div><div class="biggt" id="biggt"></div><div class="tem"></div><div class="winf"></div><div class="winl"></div></div>
<script>var hour3data={"1d":["20日11时,d08,中雨,25℃,西风,<3级,3"]};</script>
<script>var observe24h_data={"od":{"od0":"202606200800","od1":"西安","od2":[{"od21":"08","od22":"22.8","od23":"333","od24":"西北风","od25":"1","od26":"0","od27":"76","od28":""}]}};</script>
</div>
<div class="livezs"><ul><li><span>极易发</span><em>感冒指数</em><p>极易感冒。</p></li></ul></div>
</body></html>
"""

SAMPLE_7D_HTML = """
<html><head><title>西安天气预报</title></head><body>
<div class="crumbs"><a>陕西</a><a>西安</a></div>
<div id="7d" class="c7d"><ul class="t clearfix">
<li><h1>20日（今天）</h1><big class="d08"></big><p class="wea">中雨</p>
<p class="tem"><span>26℃</span>/<i>20℃</i></p><p class="win"><i>&lt;3级</i></p></li>
<li><h1>21日（明天）</h1><big class="d07"></big><p class="wea">小雨</p>
<p class="tem"><span>20℃</span>/<i>15℃</i></p></li>
</ul>
<div class="curve_livezs" id="curve"><div class="time"></div><div class="wpic"></div><div class="biggt" id="biggt"></div><div class="tem"></div><div class="winf"></div><div class="winl"></div></div>
<script>var hour3data={"7d":[["21日11时,d07,小雨,18℃,北风,<3级,3"]]};</script>
<div class="livezs"><ul><li><span>较不宜</span><em>运动指数</em><p>有降水。</p></li></ul></div>
</div>
</body></html>
"""


def test_normalize_city_code():
    assert _normalize_city_code("101110101") == "101110101"
    assert _normalize_city_code("abc") is None


def test_detect_weather_range():
    assert detect_weather_range("天气预报") == "7d"
    assert detect_weather_range("7天天气") == "7d"
    assert detect_weather_range("今天天气") == "1d"


def test_parse_weather_slash_args():
    assert parse_weather_slash_args("今天") == ("", "1d")
    assert parse_weather_slash_args("101110101 今天") == ("101110101", "1d")


def test_weather_page_url():
    assert weather_page_url("101110101", "1d").endswith("/weather1d/101110101.shtml")
    assert weather_page_url("101110101", "7d").endswith("/weather/101110101.shtml")


def test_icon_url():
    assert icon_url("d08").endswith("/blue80.png")


def test_icon_position():
    assert icon_position("d08") == "-640px 0"
    assert icon_position("n07") == "-560px -320px"
    assert icon_position("d00") == "0 0"
    # 坐标始终为 80px 网格原值，缩放由 transform 处理
    assert icon_position("d08", size=40) == "-640px 0"


def test_icon_sprite_html():
    html_out = icon_sprite_html("d08", size=48, alt="中雨")
    assert "blue80.png" in html_out
    assert "wx-icon-sprite" in html_out
    assert 'data-code="d08"' in html_out
    assert "transform:scale" in html_out


def test_parse_weather_view_1d():
    view = parse_weather_view(
        SAMPLE_1D_HTML,
        "1d",
        page_url="https://www.weather.com.cn/weather1d/101110101.shtml",
    )
    assert len(view.day_periods) == 2
    assert view.day_periods[0].weather == "中雨"
    assert view.live is not None
    assert view.live.temp == "22.8℃"
    assert view.hours[0].temp == "25℃"
    assert view.life_indices[0].name == "感冒指数"


def test_parse_sk_live():
    live = parse_sk_live(SAMPLE_SK)
    assert live is not None
    assert live.temp == "22.8℃"
    assert live.humidity == "相对湿度 76%"
    assert live.wind == "西北风 1级"
    assert live.aqi_value == "20"
    assert live.aqi_level == "优"
    assert live.traffic_limit == "不限行"
    assert live.time_label == "08:50 实况"


def test_aqi_level_label():
    assert aqi_level_label("20") == "优"
    assert aqi_level_label("80") == "良"
    assert aqi_level_label("120") == "轻度"


def test_build_weather_page_html_1d():
    sk = parse_sk_live(SAMPLE_SK)
    result = build_weather_page_html(
        SAMPLE_1D_HTML,
        "1d",
        page_url="https://www.weather.com.cn/weather1d/101110101.shtml",
        sk_live=sk,
    )
    assert result["ok"] is True
    page = result["html"]
    assert 'id="today"' in page
    assert 'id="curve"' in page
    assert "wx-today-board" in page
    assert "wx-sk-temp" in page
    assert "22.8" in page
    assert "相对湿度" in page
    assert "不限行" in page
    assert "20优" in page
    assert "20日白天" in page
    assert "20日11时" in page
    assert "感冒指数" in page
    assert 'class="livezs' in page
    assert "wx-period-grid" in page
    assert "blue80.png" in page
    assert "逐小时预报" in page
    assert "生活指数" in page
    assert "--wx-bg" in page


def test_build_weather_page_html_7d():
    result = build_weather_page_html(
        SAMPLE_7D_HTML,
        "7d",
        page_url="https://www.weather.com.cn/weather/101110101.shtml",
    )
    assert result["ok"] is True
    page = result["html"]
    assert 'id="7d"' in page
    assert 'id="curve"' in page
    assert "20日（今天）" in page
    assert "21日11时" in page
    assert "运动指数" in page
    assert "wx-day-card" in page


def test_extract_main_strips_curve_and_livezs():
    from bs4 import BeautifulSoup

    from src.tools.weather.render import extract_livezs_section, extract_main_section

    soup = BeautifulSoup(SAMPLE_7D_HTML, "html.parser")
    main = extract_main_section(
        soup,
        "7d",
        page_url="https://www.weather.com.cn/weather/101110101.shtml",
    )
    assert 'id="7d"' in main
    assert 'id="curve"' not in main
    assert "livezs" not in main
    livezs = extract_livezs_section(soup, page_url="https://www.weather.com.cn/weather/101110101.shtml")
    assert "运动指数" in livezs


def test_normalize_weather_range():
    assert normalize_weather_range("1d") == "1d"
    assert normalize_weather_range("") == "7d"
