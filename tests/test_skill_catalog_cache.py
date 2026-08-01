"""Skill 目录 mtime 缓存测试。"""

from __future__ import annotations

from src.ui.skill import catalog


def test_scan_skills_reuses_cache(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    skill_dir = skills_root / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Demo\nhello\n", encoding="utf-8")

    monkeypatch.setattr(catalog, "get_skill_dirs", lambda: [skills_root])
    catalog.invalidate_skill_catalog_cache()

    first = catalog.scan_skills()
    assert len(first) == 1
    assert first[0]["name"] == "demo"
    assert catalog._skills_cache is not None
    cached_id = id(catalog._skills_cache)

    second = catalog.scan_skills()
    assert second[0]["name"] == "demo"
    assert id(catalog._skills_cache) == cached_id

    (skill_dir / "SKILL.md").write_text("updated skill body\n", encoding="utf-8")
    third = catalog.scan_skills()
    assert third[0]["desc"] == "updated skill body"
    assert id(catalog._skills_cache) != cached_id


def test_invalidate_skill_catalog_cache(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    monkeypatch.setattr(catalog, "get_skill_dirs", lambda: [skills_root])
    catalog.invalidate_skill_catalog_cache()
    catalog.scan_skills()
    assert catalog._skills_cache is not None
    catalog.invalidate_skill_catalog_cache()
    assert catalog._skills_cache is None
