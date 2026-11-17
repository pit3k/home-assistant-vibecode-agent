"""git_versioning_ignore is applied when the shadow repo is copied and committed."""
import asyncio
import os
from pathlib import Path

import git
import pytest


def _manager(tmp_path, monkeypatch, ignore=""):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path))
    monkeypatch.setenv("GIT_VERSIONING_AUTO", "true")
    monkeypatch.setenv("GIT_VERSIONING_IGNORE", ignore)
    monkeypatch.setenv("MAX_BACKUPS", "30")
    from app.services.git_manager import GitManager

    manager = GitManager()
    assert manager.repo is not None
    return manager


def _write(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _layout(root: Path) -> None:
    _write(root / "configuration.yaml", "homeassistant:\n")
    _write(root / "secrets.yaml", "token: secret\n")
    _write(root / ".storage" / "core.entity_registry", "{}\n")
    _write(root / "www" / "index.html", "<html></html>\n")
    _write(root / "__pycache__" / "top.pyc", "top\n")
    _write(root / "custom_components" / "foo" / "__init__.py", "COMPONENT = 1\n")
    _write(root / "custom_components" / "foo" / "__pycache__" / "mod.pyc", "payload\n")
    _write(root / "esphome" / "heater" / "device.yaml", "esphome:\n")
    _write(root / "esphome" / "heater" / ".git" / "HEAD", "ref: refs/heads/main\n")
    _write(root / "esphome" / "heater" / ".git" / "config", "[core]\n")
    _write(root / "tts" / "hello.mp3", "audio\n")
    _write(root / "tts" / "notes.txt", "notes\n")
    _write(root / "notes" / "tts", "this is a file named tts\n")
    _write(root / "voice" / "tts" / "clip.mp3", "clip\n")
    _write(root / "sounds" / "song.mp3", "song\n")
    _write(root / "sounds" / "keep.wav", "wav\n")


def _shadow_files(root: Path) -> set[str]:
    shadow = root / "ha_vibecode_git"
    found = set()
    for dirpath, dirnames, filenames in os.walk(shadow):
        if Path(dirpath) == shadow and ".git" in dirnames:
            dirnames.remove(".git")
        for name in filenames:
            found.add((Path(dirpath) / name).relative_to(shadow).as_posix())
    return found


EXAMPLE = "**/__pycache__, **/.git, tts/, *.mp3"


class TestBuiltinExclusionsUnchanged:
    def test_empty_option_keeps_today_include_decisions(self, tmp_path, monkeypatch):
        manager = _manager(tmp_path, monkeypatch, ignore="")
        included = {
            "configuration.yaml": False,
            "automations.yaml": False,
            "custom_components/foo/__init__.py": False,
            "custom_components/foo/__pycache__": True,
            "custom_components/foo/__pycache__/mod.pyc": False,
            "esphome/heater/.git": True,
            "esphome/heater/.git/HEAD": False,
            "esphome/heater/device.yaml": False,
            "tts/hello.mp3": False,
            "sounds/song.mp3": False,
            "custom_components/foo/node_modules": True,
        }
        excluded = {
            ".git": True,
            "ha_vibecode_git": True,
            ".storage": True,
            ".storage/core.entity_registry": False,
            ".cache": True,
            "www": True,
            "media": True,
            "backups": True,
            "node_modules": True,
            "__pycache__": True,
            "secrets.yaml": False,
            "home-assistant.log": False,
            "home-assistant_v2.db": False,
        }
        for rel, is_dir in included.items():
            assert manager._should_include_path(rel, is_dir), rel
        for rel, is_dir in excluded.items():
            assert not manager._should_include_path(rel, is_dir), rel

    def test_empty_option_still_copies_nested_caches(self, tmp_path, monkeypatch):
        _layout(tmp_path)
        manager = _manager(tmp_path, monkeypatch, ignore="")
        manager._sync_config_to_shadow()
        copied = _shadow_files(tmp_path)

        assert "configuration.yaml" in copied
        assert "custom_components/foo/__init__.py" in copied
        assert "custom_components/foo/__pycache__/mod.pyc" in copied
        assert "esphome/heater/.git/HEAD" in copied
        assert "esphome/heater/device.yaml" in copied
        assert "tts/hello.mp3" in copied
        assert "sounds/song.mp3" in copied
        assert "secrets.yaml" not in copied
        assert ".storage/core.entity_registry" not in copied
        assert "www/index.html" not in copied
        assert "__pycache__/top.pyc" not in copied


class TestIgnoreOption:
    def test_patterns_are_added_to_builtins(self, tmp_path, monkeypatch):
        manager = _manager(tmp_path, monkeypatch, ignore=f"  {EXAMPLE}  ")
        assert not manager._should_include_path(
            "custom_components/foo/__pycache__", True
        )
        assert not manager._should_include_path(
            "custom_components/foo/__pycache__/mod.pyc", False
        )
        assert not manager._should_include_path("esphome/heater/.git", True)
        assert not manager._should_include_path("esphome/heater/.git/HEAD", False)
        assert not manager._should_include_path("tts", True)
        assert manager._should_include_path("tts", False)
        assert not manager._should_include_path("tts/hello.mp3", False)
        assert not manager._should_include_path("sounds/song.mp3", False)
        assert manager._should_include_path("custom_components/foo/__init__.py", False)
        assert manager._should_include_path("esphome/heater/device.yaml", False)
        assert manager._should_include_path("configuration.yaml", False)
        # Built-ins still apply even though they are not in the option.
        assert not manager._should_include_path("secrets.yaml", False)
        assert not manager._should_include_path(".storage", True)
        assert not manager._should_include_path("www/index.html", False)

    def test_sync_does_not_copy_ignored_paths(self, tmp_path, monkeypatch):
        _layout(tmp_path)
        manager = _manager(tmp_path, monkeypatch, ignore=EXAMPLE)
        manager._sync_config_to_shadow()
        copied = _shadow_files(tmp_path)

        assert copied == {
            "configuration.yaml",
            "custom_components/foo/__init__.py",
            "esphome/heater/device.yaml",
            "notes/tts",
            "sounds/keep.wav",
        }
        assert (tmp_path / "custom_components" / "foo" / "__pycache__" / "mod.pyc").is_file()
        assert (tmp_path / "esphome" / "heater" / ".git" / "HEAD").is_file()

    def test_previously_tracked_paths_stop_being_tracked(self, tmp_path, monkeypatch):
        _layout(tmp_path)
        tracked = [
            "custom_components/foo/__pycache__/mod.pyc",
            "sounds/song.mp3",
            "tts/hello.mp3",
            "tts/notes.txt",
            "voice/tts/clip.mp3",
        ]
        first = _manager(tmp_path, monkeypatch, ignore="")
        first_hash = asyncio.run(first.commit_changes("before ignore", force=True))
        assert first_hash
        full_first = first.repo.head.commit.hexsha
        for rel in tracked:
            first.repo.git.cat_file("-e", f"{full_first}:{rel}")
        # Git will not store a nested .git directory, but the copy still
        # lands in the worktree until an ignore pattern drops it.
        shadow_git = tmp_path / "ha_vibecode_git" / "esphome" / "heater" / ".git" / "HEAD"
        assert shadow_git.is_file()
        assert "esphome/heater/.git/HEAD" not in first.repo.git.ls_files().splitlines()

        second = _manager(tmp_path, monkeypatch, ignore=EXAMPLE)
        second_hash = asyncio.run(second.commit_changes("apply ignore", force=True))
        assert second_hash
        assert second_hash != first_hash

        shadow = tmp_path / "ha_vibecode_git"
        assert "payload" in second.repo.git.show(
            f"{full_first}:custom_components/foo/__pycache__/mod.pyc"
        )
        for rel in tracked:
            assert not (shadow / rel).exists()
            second.repo.git.cat_file("-e", f"{full_first}:{rel}")
            with pytest.raises(git.exc.GitCommandError):
                second.repo.git.cat_file("-e", f"HEAD:{rel}")
        assert not shadow_git.exists()
        # The real config is untouched.
        assert (tmp_path / "custom_components" / "foo" / "__pycache__" / "mod.pyc").is_file()
        assert (tmp_path / "esphome" / "heater" / ".git" / "HEAD").is_file()
        assert "homeassistant:" in second.repo.git.show("HEAD:configuration.yaml")
        assert int(second.repo.git.rev_list("--count", "HEAD")) == 2


def test_health_reports_ignore_option(monkeypatch):
    monkeypatch.setenv("GIT_VERSIONING_IGNORE", EXAMPLE)
    from app.main import health

    data = asyncio.run(health())
    assert data["git_versioning_ignore"] == EXAMPLE
