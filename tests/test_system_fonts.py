"""系统字体枚举测试。"""

from __future__ import annotations

from src.ui.prefs.system_fonts import css_font_family, normalize_font_id


def test_normalize_font_id_legacy():
    assert normalize_font_id("lxgw-wenkai-gb") == "system"
    assert normalize_font_id("") == "system"
    assert normalize_font_id("Segoe UI") == "Segoe UI"


def test_css_font_family_system():
    family, mono = css_font_family("system")
    assert "Segoe UI" in family
    assert "Cascadia Code" in mono


def test_css_font_family_named():
    family, mono = css_font_family("Microsoft YaHei")
    assert '"Microsoft YaHei"' in family
    assert '"Microsoft YaHei"' in mono
