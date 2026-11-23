---
name: recap
description: Summarise any period from the synapsidian vault in chat - a day, a week, a sprint, a month, or "since X" - from devlogs, tasks, decisions and meetings, without writing anything. Use when the user asks what they did, what happened or what was decided over some stretch of time ("recap last week", "co robiłem w zeszłym tygodniu", "what happened on the export project this month", "summarise since Monday", "przypomnij mi ostatnie dwa tygodnie").
argument-hint: "<period, e.g. 'last week', 'since 2026-10-01', 'yesterday'> [topic or project]"
allowed-tools: Bash(synapsidian *) Read Grep Glob
context: fork
agent: Explore
background: false
---

# Recap

Read-only: this skill never writes to the vault. For a saved review use `/synapsidian:review`.

Request: $ARGUMENTS

This runs in a subagent of its own (D131): it sees only the request above, so the period and any topic must be in it. Return the summary, not the notes it was built from.

1. Turn the period into absolute dates (today is known; weeks start on Monday). If a topic or project is given, keep to it.
2. Gather, as the review skill does: daily-note `devlog` blocks in the period (`synapsidian block get --file "Daily/<date>.md" --name devlog`), tasks done and created (`synapsidian query notes --type task ...` with `done_on` / `created` ranges), decisions and meetings created in the period, and existing review notes that cover it. For a topic, add `synapsidian find "<topic>"` and keep only notes touched in the period (`modified` in the query output).
3. Answer in the user's language, short: what got done (grouped by project when the vault has projects, otherwise by topic), decisions, what's still open. Every claim cites its note as `[[link]]`. If the vault has nothing for some days, say which days are empty rather than guessing.
