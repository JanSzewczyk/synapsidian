"""The documentation site in docs/ against the plugins it documents.

Fails when a skill or a `synapsidian` command has no page (or a page outlives it), when a
CHANGELOG.md heading would drop out of the changelog feeds, when a plugin's current version has no
changelog section, when an archived version in astro.config.mjs has no snapshot, or when a file
still links to the docs that moved out of docs/ (spec, research, decisions). Offline, stdlib only.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"
SITE = ROOT / "docs"
PAGES = SITE / "src" / "content" / "docs"

# The same pattern docs/src/content.config.ts uses to split CHANGELOG.md into one feed per plugin.
HEADING = r"^\[(\S+) (synapsidian(?:-work|-projects|-dock)?)\]\s*—\s*(\d{4}-\d{2}-\d{2})$"

# Add-on plugin -> its folder of pages: extensions/ for the add-ons, mods/ for the Claude Code mod.
ADDONS = {
    "synapsidian-work": "extensions/work",
    "synapsidian-projects": "extensions/projects",
    "synapsidian-dock": "mods/dock",
}


def skills(plugin: str) -> set[str]:
    folder = PLUGINS / plugin / "skills"
    return {p.parent.name for p in folder.glob("*/SKILL.md")} if folder.is_dir() else set()


def pages(folder: Path, *, skip: set[str]) -> set[str]:
    return {p.stem for p in folder.glob("*.mdx")} - skip


def test_every_core_skill_has_a_page_and_no_page_outlives_its_skill() -> None:
    assert pages(PAGES / "skills", skip={"overview"}) == skills("synapsidian")


@pytest.mark.parametrize("plugin", sorted(ADDONS))
def test_every_addon_skill_has_a_page_and_no_page_outlives_its_skill(plugin: str) -> None:
    folder = PAGES / ADDONS[plugin]
    assert (folder / "index.mdx").is_file(), f"{plugin} has no overview page"
    assert pages(folder, skip={"index"}) == skills(plugin)


def test_every_cli_command_has_a_page() -> None:
    wrapper = (PLUGINS / "synapsidian" / "bin" / "synapsidian").read_text(encoding="utf-8")
    case = re.search(r"^\s*(note \|[^)]*)\)", wrapper, re.MULTILINE)
    assert case, "the command list in bin/synapsidian moved; update this test"
    commands = {c.strip() for c in case.group(1).split("|")} | {"ref"}
    assert pages(PAGES / "cli", skip={"overview"}) == commands


def test_changelog_headings_feed_the_site() -> None:
    config = (SITE / "src" / "content.config.ts").read_text(encoding="utf-8")
    assert f"/{HEADING}/" in config, "content.config.ts and this test no longer share the heading pattern"
    headings = [
        line[3:] for line in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines() if line.startswith("## [")
    ]
    assert headings
    bad = [h for h in headings if not re.match(HEADING, h)]
    assert not bad, f"these CHANGELOG.md headings match no changelog feed: {bad}"


@pytest.mark.parametrize("plugin", ["synapsidian", *sorted(ADDONS)])
def test_each_plugins_current_version_has_a_changelog_section(plugin: str) -> None:
    manifest = json.loads((PLUGINS / plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{manifest['version']} {plugin}] — " in changelog


def test_every_archived_version_has_its_snapshot() -> None:
    config = (SITE / "astro.config.mjs").read_text(encoding="utf-8")
    listed = re.search(r"^const versions = (\[.*?\]);", config, re.MULTILINE | re.DOTALL)
    assert listed, "`const versions = [...]` moved in astro.config.mjs; update this test"
    for slug in re.findall(r'slug:\s*"([^"]+)"', listed.group(1)):
        assert (PAGES / slug / "index.mdx").is_file(), f"version {slug} has no snapshot folder"
        assert (SITE / "src" / "content" / "versions" / f"{slug}.json").is_file(), f"version {slug} has no sidebar file"


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [ROOT / line for line in out.splitlines()]


def test_nothing_links_to_the_docs_that_left_docs() -> None:
    gone = re.compile(r"docs/(?:spec\.md|decisions\.md|research\b)")
    allowed = {ROOT / "CHANGELOG.md", Path(__file__)}
    hits = []
    for path in tracked_files():
        if (
            path in allowed
            or path.is_relative_to(ROOT / "references")
            or path.suffix not in {".md", ".mdx", ".py", ".yml", ".yaml", ".json", ".ts", ".mjs", ".astro"}
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        hits += [f"{path.relative_to(ROOT)}:{n}" for n, line in enumerate(text.splitlines(), 1) if gone.search(line)]
    assert not hits, f"links to docs/spec.md, docs/decisions.md or docs/research remain: {hits}"
