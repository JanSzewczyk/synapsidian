---
name: recap
description: Summarise any period from the vault in chat - a day, week, sprint, month or "since X" - from devlogs, tasks, decisions and meetings, writing nothing. Use when the user asks what happened over a stretch of time ("recap last week", "co robiłem w zeszłym tygodniu", "summarise since Monday").
allowed-tools: Bash(synapsidian *) Read Grep Glob Agent
argument-hint: "<period, e.g. 'last week', 'since 2026-10-01', 'yesterday'> [topic or project]"
---

# Recap

Read-only: this skill never writes to the vault. For a saved review use `/synapsidian:review`.

Request: $ARGUMENTS

Run this in an Explore subagent (D131), so the notes it reads stay out of this conversation: spawn it with the Agent tool (`subagent_type: Explore`) and a prompt that holds the request above, with the period and any topic, and the steps below, because it does not see the conversation. Relay its answer and `[[links]]`, not the notes' text, and read no notes yourself. If no subagent tool is available, do the steps yourself.

1. Turn the period into absolute dates (today is known; weeks start on Monday). If a topic or project is given, keep to it.
2. Gather, as the review skill does: daily-note `devlog` blocks in the period (`synapsidian block get --file "Daily/<date>.md" --name devlog`), tasks done and created (`synapsidian query notes --type task ...` with `done_on` / `created` ranges), decisions and meetings created in the period, and existing review notes that cover it. For a topic, add `synapsidian find "<topic>"` and keep only notes touched in the period (`modified` in the query output).
3. Answer in the user's language, short: what got done (grouped by project when the vault has projects, otherwise by topic), decisions, what's still open. Every claim cites its note as `[[link]]`. If the vault has nothing for some days, say which days are empty rather than guessing.
