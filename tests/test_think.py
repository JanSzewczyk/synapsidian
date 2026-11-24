from __future__ import annotations

import re
from pathlib import Path

from synapsidianlib import frontmatter, schema

ROOT = Path(__file__).resolve().parents[1] / "plugins" / "synapsidian"


def test_thinking_note_gets_its_mode_template(run, vault):
    code, out = run(
        "note", "new", "--type", "thinking", "--title", "XLSX-first export", "--field", "kind=challenge",
        "--field", "summary=Go with changes", "--field", "about=Pay equity export", vault=vault,
    )  # fmt: skip
    assert code == 0 and out["rel"].startswith("Thinking/") and out["rel"].endswith("challenge XLSX-first export.md")
    note = frontmatter.parse((vault / out["rel"]).read_text())
    assert note.meta["kind"] == "challenge" and note.meta["about"] == ["[[Pay equity export]]"]
    assert "## Verdict" in note.body and "## By lens" in note.body
    code, bad = run(
        "note", "new", "--type", "thinking", "--title", "x", "--field", "kind=graduate", "--field", "summary=s",
        vault=vault,
    )  # fmt: skip
    assert code == 2 and "kind" in bad["error"]


def test_every_thinking_kind_has_a_template_and_instructions():
    kinds = schema.load().types["thinking"].fields["kind"].enum
    skill = (ROOT / "skills/think/SKILL.md").read_text()
    for kind in kinds:
        assert (ROOT / f"schema/templates/thinking-{kind}.md").is_file(), kind
        assert re.search(rf"\| {kind} \| `\$\{{CLAUDE_PLUGIN_ROOT\}}/references/think-{kind}\.md` \|", skill), kind
    assert "references/think-graduate.md" in skill  # graduate writes no thinking note, but has instructions
