---
name: think
description: Thinking tools over the second-brain vault, one mode per call - challenge, brainstorm, topic (all the vault knows about X), patterns, distill, learn (lessons from past sessions as proposed rules), ideas (rank the backlog), graduate (an idea into a project or tasks). Use when the user wants something stress-tested ("challenge this", "co może pójść nie tak"), brainstormed ("burza mózgów"), pulled together ("co wiem o X"), patterns spotted ("jakie wzorce"), a source distilled, or ideas reviewed or graduated ("przejrzyj pomysły", "zrób z tego projekt").
argument-hint: "<challenge|brainstorm|topic|patterns|distill|learn|ideas|graduate> <subject> [fix]"
allowed-tools: Bash(synapsidian *) Read Grep Glob
---

# Think

The `synapsidian` command finds the vault by itself (plugin option `vault_path`); `synapsidian note where` prints its path.

Request: $ARGUMENTS

1. **Pick the mode** from the first word, or from what the user is asking for if they didn't name one (see the description). If two modes fit, ask once.
2. Read `${CLAUDE_PLUGIN_ROOT}/references/conventions.md` and the mode's file, then follow it:

| Mode | Instructions |
|---|---|
| challenge | `${CLAUDE_PLUGIN_ROOT}/references/think-challenge.md` |
| brainstorm | `${CLAUDE_PLUGIN_ROOT}/references/think-brainstorm.md` |
| topic | `${CLAUDE_PLUGIN_ROOT}/references/think-topic.md` |
| patterns | `${CLAUDE_PLUGIN_ROOT}/references/think-patterns.md` |
| distill | `${CLAUDE_PLUGIN_ROOT}/references/think-distill.md` |
| learn | `${CLAUDE_PLUGIN_ROOT}/references/think-learn.md` |
| ideas | `${CLAUDE_PLUGIN_ROOT}/references/think-ideas.md` |
| graduate | `${CLAUDE_PLUGIN_ROOT}/references/think-graduate.md` |

3. **Rules for every mode:**
   - Search before you claim the vault has nothing; cite every vault fact as `[[note]]`.
   - Subagents only read and return findings; you write every note.
   - Thinking notes: `synapsidian note new --type thinking --title "<subject>" --field kind=<mode> --field summary="<the result in one sentence>" [--field about="<note>,<note>"]`, then fill the template's sections. The title is the subject, not the mode (the file name already says it).
   - Write in English; answer the user in their language, result first.
4. **Finish**: one devlog bullet in today's daily note (`synapsidian note daily`, `synapsidian block get` / `set` on `devlog`): `Thought through [[<thinking note>]]` (or what `graduate` created). Then one commit: `synapsidian commit --skill think --message "<mode>: <subject>" <every file touched>`. If it reports `broken_links`, fix them as the conventions say.
