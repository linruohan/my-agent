from __future__ import annotations

import stat

import pytest

from src.tools.file.advanced import (
    create_symlink_impl,
    read_file_bytes_impl,
    stream_read_file_impl,
    write_local_file_locked_impl,
)
from src.tools.file.meta import get_path_info_impl, set_file_attributes_impl
from src.tools.file.ops import (
    copy_path_impl,
    create_directory_impl,
    create_file_impl,
    delete_path_impl,
    move_path_impl,
    remove_directory_impl,
    rename_path_impl,
    write_local_file_impl,
)
from src.tools.file.path import PathNotAllowedError, resolve_path


class TestLifecycle:
    def test_create_and_read(self, fs_env):
        target = fs_env / "new.txt"
        msg = create_file_impl(str(target), content="hello world")
        assert "已创建" in msg
        assert target.read_text(encoding="utf-8") == "hello world"

    def test_write_overwrite_and_append(self, fs_env):
        f = fs_env / "log.txt"
        create_file_impl(str(f), "line1\n")
        write_local_file_impl(str(f), "line2\n", mode="append")
        content = f.read_text(encoding="utf-8")
        assert "line1" in content and "line2" in content
        write_local_file_impl(str(f), "replaced", mode="overwrite")
        assert f.read_text(encoding="utf-8") == "replaced"

    def test_create_directory(self, fs_env):
        d = fs_env / "sub" / "nested"
        msg = create_directory_impl(str(d))
        assert d.is_dir()
        assert "已创建目录" in msg

    def test_copy_move_rename(self, fs_env):
        src = fs_env / "copy_src.txt"
        create_file_impl(str(src), "copy me")
        dst = fs_env / "copy_dst.txt"
        assert "已复制" in copy_path_impl(str(src), str(dst))
        assert dst.exists()
        assert "重命名" in rename_path_impl(str(dst), "renamed.txt")
        assert (fs_env / "renamed.txt").exists()

    def test_move(self, fs_env):
        src = fs_env / "move_me.txt"
        create_file_impl(str(src), "move")
        dst = fs_env / "data" / "moved.txt"
        assert "已移动" in move_path_impl(str(src), str(dst))
        assert dst.exists()
        assert not src.exists()

    def test_soft_delete(self, fs_env, tmp_path, monkeypatch):
        import src.tools.file.ops as ops_mod
        import src.tools.file.path as path_mod

        trash = tmp_path / "trash"
        trash.mkdir(exist_ok=True)
        monkeypatch.setattr(path_mod, "trash_directory", lambda: trash)
        monkeypatch.setattr(ops_mod, "trash_directory", lambda: trash)

        f = fs_env / "data" / "notes.txt"
        assert f.exists()
        msg = delete_path_impl(str(f), permanent=False)
        assert "回收站" in msg
        assert not f.exists()
        assert any(trash.iterdir())

    def test_permanent_delete(self, fs_env):
        f = fs_env / "to_delete.txt"
        create_file_impl(str(f), "bye")
        msg = delete_path_impl(str(f), permanent=True)
        assert "永久删除" in msg
        assert not f.exists()

    def test_remove_empty_directory(self, fs_env):
        d = fs_env / "empty_dir"
        d.mkdir()
        msg = remove_directory_impl(str(d), recursive=False)
        assert "删除" in msg
        assert not d.exists()


class TestMetadata:
    def test_get_path_info(self, fs_env):
        f = fs_env / "info_test.txt"
        create_file_impl(str(f), "info")
        info = get_path_info_impl(str(f))
        assert "绝对路径" in info
        assert "修改时间" in info
        assert "扩展名" in info

    def test_set_readonly(self, fs_env):
        f = fs_env / "readonly_test.txt"
        create_file_impl(str(f), "data")
        msg = set_file_attributes_impl(str(f), readonly=True)
        assert "只读" in msg
        assert not (f.stat().st_mode & stat.S_IWRITE)
        set_file_attributes_impl(str(f), readonly=False)
        assert f.stat().st_mode & stat.S_IWRITE


class TestAdvanced:
    def test_read_file_bytes(self, fs_env):
        f = fs_env / "bytes.txt"
        f.write_bytes(b"0123456789abcdef")
        result = read_file_bytes_impl(str(f), offset=4, length=4)
        assert "偏移: 4" in result
        assert "5678" in result or "预览" in result

    def test_stream_read(self, fs_env):
        f = fs_env / "stream.txt"
        f.write_text("line1\nline2\nline3\n", encoding="utf-8")
        result = stream_read_file_impl(str(f), chunk_lines=2, start_line=1)
        assert "流式读取" in result
        assert "line1" in result

    def test_write_with_lock(self, fs_env):
        f = fs_env / "locked.txt"
        msg = write_local_file_locked_impl(str(f), "locked content")
        assert "写入" in msg
        assert f.read_text(encoding="utf-8") == "locked content"

    def test_symlink(self, fs_env):
        target = fs_env / "target.txt"
        create_file_impl(str(target), "link me")
        link = fs_env / "link.txt"
        if link.exists():
            link.unlink()
        try:
            msg = create_symlink_impl(str(target), str(link))
        except OSError as exc:
            if getattr(exc, "winerror", None) == 1314:
                pytest.skip("需要管理员权限或开发者模式才能创建符号链接")
            raise
        assert "符号链接" in msg
        assert link.is_symlink()


class TestSecurity:
    def test_write_outside_allowed(self, tmp_path, monkeypatch):
        import src.tools.file.path as path_mod

        allowed = tmp_path / "allowed"
        allowed.mkdir()
        monkeypatch.setattr(path_mod, "get_search_roots", lambda: [allowed])
        outside = tmp_path / "outside.txt"
        with pytest.raises(PathNotAllowedError):
            create_file_impl(str(outside), "hack")

    def test_resolve_path(self, fs_env):
        p = resolve_path(str(fs_env / "data"))
        assert p.is_dir()
