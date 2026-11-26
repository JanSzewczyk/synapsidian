"""The morning run's sources (D162): the `morning_sources` option, `email` as a core task source,
the `sources` reference and synapsidian-work's hand-off."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from conftest import CORE, ROOT, WORK, install_work_extension
from synapsidianlib import config, schema

EMAIL_TASK = {
    "type": "task",
    "created": "2026-11-26",
    "summary": "Alex asked for the report",
    "id": "T1",
    "status": "todo",
    "priority": "medium",
    "source": "email",
    "source_link": "https://mail.example.com/thread/1",
}


@pytest.fixture
def no_saved_options(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Never read the developer's real settings.json."""
    monkeypatch.setenv("SYNAPSIDIAN_SETTINGS_FILE", str(tmp_path / "no-settings.json"))
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_MORNING_SOURCES", raising=False)


def test_the_option_is_declared_as_an_optional_list():
    manifest = json.loads((CORE / ".claude-plugin" / "plugin.json").read_text())
    option = manifest["userConfig"]["morning_sources"]
    assert option["type"] == "string" and option["multiple"] is True
    assert option["required"] is False and "default" not in option


@pytest.mark.parametrize("raw", ['["mail"]', "mail", "mail,\n", " mail "])
def test_morning_sources_reads_every_spelling(raw, no_saved_options, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_MORNING_SOURCES", raw)
    assert config.option_list("morning_sources") == ["mail"]


@pytest.mark.parametrize("raw", ["", "  ", "${user_config.morning_sources}", "[]"])
def test_an_empty_or_unsubstituted_option_turns_every_source_off(raw, no_saved_options, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_MORNING_SOURCES", raw)
    assert config.option_list("morning_sources") == []


def test_the_option_falls_back_to_settings_json(tmp_path, monkeypatch, no_saved_options):
    settings = tmp_path / "settings.json"
    options = {"options": {"morning_sources": ["mail"]}}
    settings.write_text(json.dumps({"pluginConfigs": {"synapsidian@synapsidian": options}}))
    monkeypatch.setenv("SYNAPSIDIAN_SETTINGS_FILE", str(settings))
    assert config.option_list("morning_sources") == ["mail"]


def test_email_is_a_core_task_source_with_or_without_the_work_extension(vault):
    core = schema.load(vault)
    assert "email" in core.fields_for("task")["source"].enum
    assert not [i for i in schema.validate(EMAIL_TASK, "Tasks/T1 Send the report.md", core) if "`source`" in i]

    work = schema.load(install_work_extension(vault))
    values = work.fields_for("task")["source"].enum
    assert values.count("email") == 1 and {"slack", "jira", "github"} <= set(values)
    assert not [i for i in schema.validate(EMAIL_TASK, "Tasks/T1 Send the report.md", work) if "`source`" in i]


def test_ref_sources_prints_the_contract_and_the_design_copy_is_gone():
    proc = subprocess.run([str(CORE / "bin" / "synapsidian"), "ref", "sources"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "## Source: `mail`" in proc.stdout and "## Filing asks as tasks" in proc.stdout
    assert "per source" in proc.stdout and "Implementation" not in proc.stdout
    assert not (ROOT / "references" / "morning-sources.md").exists()


def test_work_hands_mail_to_the_core_when_it_is_on():
    proc = subprocess.run([str(WORK / "bin" / "synapsidian-work"), "hook", "morning"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "sources on:" in proc.stdout and "morning core-mail" in proc.stdout
    brief = (WORK / "skills" / "work-brief" / "SKILL.md").read_text()
    assert "core-mail" in brief and "synapsidian ref sources" in (WORK / "references" / "commitments.md").read_text()
    morning = (CORE / "skills" / "morning" / "SKILL.md").read_text()
    assert "${user_config.morning_sources}" in morning and "sources on: mail" in morning
