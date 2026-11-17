"""Gitignore-style matching for git_versioning_ignore."""
import pytest

from app.utils.pathignore import compile_ignore_rules, path_is_ignored


def _ignored(patterns: str, rel_path: str, is_dir: bool) -> bool:
    return path_is_ignored(rel_path, is_dir, compile_ignore_rules(patterns))


class TestPlainName:
    """A pattern with no slash matches that name at any depth."""

    def test_top_level_name(self):
        assert _ignored("__pycache__", "__pycache__", is_dir=True)
        assert _ignored("__pycache__", "__pycache__", is_dir=False)
        assert not _ignored("__pycache__", "__pycache__2", is_dir=True)
        assert not _ignored("__pycache__", "configuration.yaml", is_dir=False)

    def test_nested_name_at_any_depth(self):
        assert _ignored(
            "__pycache__",
            "custom_components/foo/__pycache__",
            is_dir=True,
        )
        assert _ignored(
            "__pycache__",
            "custom_components/foo/__pycache__/mod.pyc",
            is_dir=False,
        )
        assert not _ignored(
            "__pycache__",
            "custom_components/foo/__init__.py",
            is_dir=False,
        )


class TestAnchoredPath:
    def test_slash_anchors_pattern_at_config_root(self):
        patterns = "custom_components/foo"
        assert _ignored(patterns, "custom_components/foo", is_dir=True)
        assert _ignored(patterns, "custom_components/foo/__init__.py", is_dir=False)
        assert not _ignored(patterns, "custom_components/bar", is_dir=True)
        assert not _ignored(
            patterns,
            "packages/custom_components/foo",
            is_dir=True,
        )
        assert not _ignored(
            patterns,
            "packages/custom_components/foo/__init__.py",
            is_dir=False,
        )

    def test_leading_slash_is_only_an_anchor(self):
        assert _ignored("/tts", "tts", is_dir=True)
        assert not _ignored("/tts", "voice/tts", is_dir=True)


class TestDoubleStar:
    def test_matches_any_number_of_directories_including_zero(self):
        patterns = "**/__pycache__"
        assert _ignored(patterns, "__pycache__", is_dir=True)
        assert _ignored(patterns, "custom_components/foo/__pycache__", is_dir=True)
        assert _ignored(
            patterns,
            "custom_components/foo/__pycache__/mod.pyc",
            is_dir=False,
        )
        assert not _ignored(patterns, "custom_components/foo/__init__.py", is_dir=False)

    def test_star_star_between_names(self):
        patterns = "esphome/**/.git"
        assert _ignored(patterns, "esphome/.git", is_dir=True)
        assert _ignored(patterns, "esphome/heater/.git", is_dir=True)
        assert _ignored(patterns, "esphome/room/heater/.git", is_dir=True)
        assert _ignored(patterns, "esphome/heater/.git/config", is_dir=False)
        assert not _ignored(patterns, "esphome/heater/.gitignore", is_dir=False)
        assert not _ignored(patterns, "esphome/heater/device.yaml", is_dir=False)
        assert not _ignored(patterns, "other/esphome/heater/.git", is_dir=True)


class TestTrailingSlash:
    def test_directories_only_at_any_depth(self):
        patterns = "tts/"
        assert _ignored(patterns, "tts", is_dir=True)
        assert _ignored(patterns, "voice/tts", is_dir=True)
        assert _ignored(patterns, "tts/hello.mp3", is_dir=False)
        assert _ignored(patterns, "voice/tts/hello.mp3", is_dir=False)
        assert not _ignored(patterns, "tts", is_dir=False)
        assert not _ignored(patterns, "voice/tts", is_dir=False)
        assert not _ignored(patterns, "tts_backup.txt", is_dir=False)


class TestFileGlob:
    def test_file_glob_matches_at_any_depth(self):
        patterns = "*.mp3"
        assert _ignored(patterns, "song.mp3", is_dir=False)
        assert _ignored(patterns, "tts/song.mp3", is_dir=False)
        assert _ignored(patterns, "a/b/song.mp3", is_dir=False)
        assert not _ignored(patterns, "song.mp3.bak", is_dir=False)
        assert not _ignored(patterns, "song.wav", is_dir=False)
        assert not _ignored(patterns, "song.MP3", is_dir=False)


class TestPatternList:
    def test_trims_whitespace_and_skips_empty_entries(self):
        rules = compile_ignore_rules("  **/__pycache__ , , **/.git , tts/ , *.mp3  ")
        assert len(rules) == 4
        assert path_is_ignored(
            "custom_components/foo/__pycache__/a.pyc",
            False,
            rules,
        )
        assert path_is_ignored("esphome/heater/.git", True, rules)
        assert path_is_ignored("voice/tts", True, rules)
        assert path_is_ignored("sounds/song.mp3", False, rules)
        assert not path_is_ignored("automations.yaml", False, rules)

    @pytest.mark.parametrize("raw", ["", "   ", " , , ", None])
    def test_empty_list_matches_nothing(self, raw):
        rules = compile_ignore_rules(raw)
        assert rules == ()
        assert not path_is_ignored("custom_components/foo/__pycache__", True, rules)
        assert not path_is_ignored("song.mp3", False, rules)


class TestDocumentedExample:
    def test_example_from_the_add_on_option(self):
        patterns = "**/__pycache__, **/.git, tts/, *.mp3"
        assert _ignored(patterns, "custom_components/foo/__pycache__", True)
        assert _ignored(patterns, "esphome/heater/.git", True)
        assert _ignored(patterns, "esphome/heater/.git/HEAD", False)
        assert _ignored(patterns, "tts", True)
        assert not _ignored(patterns, "tts", False)
        assert _ignored(patterns, "sounds/alert.mp3", False)
        assert not _ignored(patterns, "esphome/heater/device.yaml", False)
        assert not _ignored(patterns, "configuration.yaml", False)
