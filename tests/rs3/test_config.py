"""Tests for RS3Config loading and defaults."""

from __future__ import annotations

from pathlib import Path

import pytest

from openjarvis.rs3.config import RS3Config


class TestRS3ConfigDefaults:
    def test_default_returns_instance(self):
        cfg = RS3Config.default()
        assert isinstance(cfg, RS3Config)

    def test_default_rsn(self):
        assert RS3Config.default().player.rsn == "YourRSN"

    def test_default_model(self):
        assert RS3Config.default().llm.model == "claude-sonnet-4-6"

    def test_default_honorific(self):
        assert RS3Config.default().player.honorific == "sir"

    def test_db_path_is_path_object(self):
        cfg = RS3Config.default()
        assert isinstance(cfg.db_path, Path)


class TestRS3ConfigFromYaml:
    def test_load_project_config(self):
        cfg_path = Path("config.yaml")
        if not cfg_path.exists():
            pytest.skip("config.yaml not in working directory")
        cfg = RS3Config.from_yaml(cfg_path)
        assert cfg.llm.model == "claude-sonnet-4-6"

    def test_load_custom_yaml(self, tmp_path: Path):
        yaml_content = """
player:
  rsn: "TestPlayer"
  honorific: "madam"
llm:
  model: "claude-opus-4-7"
  max_tokens: 800
"""
        f = tmp_path / "test_config.yaml"
        f.write_text(yaml_content)
        cfg = RS3Config.from_yaml(f)
        assert cfg.player.rsn == "TestPlayer"
        assert cfg.player.honorific == "madam"
        assert cfg.llm.model == "claude-opus-4-7"
        assert cfg.llm.max_tokens == 800

    def test_partial_yaml_uses_defaults(self, tmp_path: Path):
        f = tmp_path / "partial.yaml"
        f.write_text("player:\n  rsn: Partial\n")
        cfg = RS3Config.from_yaml(f)
        assert cfg.player.rsn == "Partial"
        assert cfg.llm.model == "claude-sonnet-4-6"  # default preserved

    def test_empty_yaml_uses_all_defaults(self, tmp_path: Path):
        f = tmp_path / "empty.yaml"
        f.write_text("")
        cfg = RS3Config.from_yaml(f)
        assert cfg.player.rsn == "YourRSN"
