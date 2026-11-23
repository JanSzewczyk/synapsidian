---
name: task
description: Add, update, close or list tasks (Tn notes with status, priority, due date and project). Use when the user wants something on their task list or asks what's on it ("add a task", "remind me to", "close T12", "dodaj zadanie", "co mam na dziś").
allowed-tools: Bash(synapsidian *) Read Grep Glob
argument-hint: "add <what> [due <date>] [priority] [project] | done <Tn> | update <Tn> ... | list [today|overdue|week|project <name>]"
---

# Tasks

The `synapsidian` command finds the vault by itself (plugin option `vault_path`); `synapsidian note where` prints its path.
Conventions: `${CLAUDE_PLUGIN_ROOT}/references/conventions.md` (read it before the first write in a session).

Request: $ARGUMENTS

Task fields (from the schema): `status` todo | doing | waiting | done | dropped · `priority` high | medium | low · `due` YYYY-MM-DD · `project` "[[Project]]" (only with synapsidian-projects, see conventions) · `source` save | session | meeting | manual | capture | ingest | research, plus any an add-on defines (`synapsidian note new` lists the allowed values when one is wrong) · `source_link` · `repeat` for a recurring task: every `<n>d`, `<n>w`, `<n>m` or `<n>y` (`1w` weekly, `1m` monthly, `1y` yearly) · `blocked_by`: the tasks that must be done first, as links (`--field blocked_by="[[T3 Buy the paint]],[[T4 Tape the edges]]"`) · `milestone` "[[Milestone]]" (only with synapsidian-projects: a milestone of the task's own project, `/synapsidian-projects:milestone`).

Resolve relative dates ("friday", "next week", "jutro") against today's date to an absolute `YYYY-MM-DD` before writing.

## Add

1. Check it isn't already a task: `synapsidian find --type task "<what>"`. If an open task matches, update that one instead.
2. If a project is mentioned and the vault has projects, find its exact note title: `synapsidian find --type project "<name>"`. Link only to a project that exists; the task is then filed under `Projects/<Project>/Tasks/`. Without projects, put the name in the summary instead.
3. Create it (the id is assigned for you):
   ```bash
   synapsidian note new --type task --title "<short imperative title>" \
     --field summary="<one sentence: what and why>" --field priority=<p> [--field due=<date>] \
     [--field project="<Project title>"] --field source=manual
   ```
   Default priority is `medium`; use `high` only when the user signals urgency. Something that comes back on a schedule ("every month", "co tydzień") gets `--field repeat=<interval>` and a `due` for the first time. Something that can start only after other tasks ("after T5", "once the paint is bought", "po T5") gets `--field blocked_by=` with those tasks' exact titles as links; find them with `synapsidian find --type task` and link only tasks that exist.
4. If there is useful context (why, links, acceptance), add it under `## Context` with Edit.

## Update or close

1. Find the note: by id, `synapsidian find --type task "T12"` (or by description).
2. Change fields with `synapsidian note set --file "<rel>" --field status=done` (closing sets `done_on` automatically). Use `--field due=` with an empty value to clear a field. Closing a task with `repeat` files the next one itself and returns it as `next`: commit its `rel` too and tell the user the new task and its due date. To stop a recurring task, clear `repeat` before closing it. A dependency is changed the same way: `--field blocked_by=` with the full new list, or empty to clear it. Never make a task wait on itself or on a task that waits on it.
   - After closing or dropping a task, look for the tasks it blocked: `synapsidian query notes --type task --where status!=done --where status!=dropped`, then those whose `blocked_by` links to it. Tell the user which are now free to start (none of their other blockers open).
3. Add a dated line under `## Log` when something notable happened ("2026-10-13: waiting on the quote from [[Alex]]").

## List

Read the open tasks with `synapsidian query notes --type task --where status!=done --where status!=dropped` (tasks may also sit in project folders, so don't read only `Tasks/`), narrowed with `synapsidian find --type task "<filter words>"` when the user names a topic, then show them grouped: overdue, due today, in progress, upcoming (7 days), no date. One line each: `[[Tn Title]]` · priority · due · project (when it has one) · `blocked by [[Tm ...]]` while a task in its `blocked_by` is open. Done and dropped tasks only when asked.

## Finish

Commit everything this run changed (see conventions), message like `add T14 review TDD` or `close T7`. Listing commits nothing.
