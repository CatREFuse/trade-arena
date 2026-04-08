from __future__ import annotations

import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "quickstart.py"


def load_quickstart_module():
    spec = importlib.util.spec_from_file_location("trade_arena_quickstart_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def quickstart(tmp_path, monkeypatch):
    module = load_quickstart_module()
    skill_root = tmp_path / "skill"
    skill_root.mkdir()
    config_file = skill_root / "config.json"
    skill_md = skill_root / "SKILL.md"
    strategy_file = skill_root / "strategy.md"
    legacy_strategy_file = skill_root / "strategy.MD"

    monkeypatch.setattr(module, "SKILL_ROOT", skill_root)
    monkeypatch.setattr(module, "CONFIG_FILE", config_file)
    monkeypatch.setattr(module, "SKILL_MD_FILE", skill_md)
    monkeypatch.setattr(module, "STRATEGY_FILE", strategy_file)
    monkeypatch.setattr(module, "LEGACY_STRATEGY_FILE", legacy_strategy_file)

    config_file.write_text(json.dumps(module.default_config(), ensure_ascii=False), encoding="utf-8")
    skill_md.write_text(
        "---\nname: trade-arena\nversion: 1.3.0\ndescription: test\n---\n",
        encoding="utf-8",
    )
    return module


class FakeResponse:
    def __init__(self, status_code=200, payload=None, content=b""):
        self.status_code = status_code
        self._payload = payload or {}
        self.content = content

    def json(self):
        return self._payload



def test_load_config_handles_legacy_schema(quickstart):
    quickstart.CONFIG_FILE.write_text(
        json.dumps({"$schema": "https://json-schema.org", "properties": {"api_url": {}}}),
        encoding="utf-8",
    )

    config = quickstart.load_config()

    assert config["api_url"] == "stock.cocoloop.cn"
    assert config["setup_state"]["landing_last_seen_version"] == ""



def test_run_startup_gate_requires_landing_without_strategy(quickstart, monkeypatch):
    monkeypatch.setattr(
        quickstart,
        "api_request",
        lambda *args, **kwargs: FakeResponse(payload={"version": "1.3.0", "hosted_url": "https://example.com/skill.zip"}),
    )

    gate = quickstart.run_startup_gate()

    assert gate.should_run_landing is True
    assert gate.landing_reason == "missing_strategy"
    assert gate.strategy_state is not None
    assert gate.strategy_state.exists is False



def test_run_startup_gate_triggers_migration_once(quickstart, monkeypatch):
    quickstart.STRATEGY_FILE.write_text("# Strategy\n\n稳健看 A股 和 美股。\n", encoding="utf-8")
    monkeypatch.setattr(
        quickstart,
        "api_request",
        lambda *args, **kwargs: FakeResponse(payload={"version": "1.3.0", "hosted_url": "https://example.com/skill.zip"}),
    )

    first_gate = quickstart.run_startup_gate()
    assert first_gate.should_run_landing is True
    assert first_gate.landing_reason == "migration"

    quickstart.mark_landing_seen(quickstart.load_config(), "1.3.0")
    second_gate = quickstart.run_startup_gate()
    assert second_gate.should_run_landing is False



def test_apply_skill_update_preserves_config_and_strategy(quickstart, monkeypatch):
    config = quickstart.load_config()
    config["token"] = "secret-token"
    quickstart.save_config(config, announce=False)
    quickstart.STRATEGY_FILE.write_text("# Strategy\n\n原策略\n", encoding="utf-8")

    archive_buf = io.BytesIO()
    with zipfile.ZipFile(archive_buf, "w") as zf:
        zf.writestr("config.json", '{"token":"should-not-overwrite"}')
        zf.writestr("strategy.md", "# should not overwrite\n")
        zf.writestr("notes.txt", "updated")
    archive_bytes = archive_buf.getvalue()

    monkeypatch.setattr(quickstart.requests, "get", lambda *args, **kwargs: FakeResponse(content=archive_bytes))

    updated = quickstart.apply_skill_update("https://example.com/skill.zip", "1.3.0", silent=True)

    assert updated is True
    assert quickstart.load_config()["token"] == "secret-token"
    assert quickstart.STRATEGY_FILE.read_text(encoding="utf-8") == "# Strategy\n\n原策略\n"
    assert (quickstart.SKILL_ROOT / "notes.txt").read_text(encoding="utf-8") == "updated"



def test_generate_schedule_plan_uses_detected_markets(quickstart, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", "/tmp/codex-home")

    plan = quickstart.generate_schedule_plan("稳健风格，主要看A股，也会看美股。")

    assert plan.capability == "automation"
    assert any("A股增强版" in line for line in plan.market_lines)
    assert any("美股增强版" in line for line in plan.market_lines)
    assert plan.actionable_lines[0].startswith("直接对当前宿主说")
