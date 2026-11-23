---
name: milestone
description: Plan and track a project's milestones (synapsidian-projects add-on) - a note in Projects/<Project>/Milestones/ with a goal, exit criteria, dates and a board of its tasks, with progress counted from them. Use when the user splits a project into stages, releases or iterations, puts tasks into one, or asks how one stands ("add a milestone", "dodaj kamień milowy", "put T5 in the MVP", "how far is the MVP", "zamknij etap"). One task is /synapsidian:task; one change is /synapsidian-projects:change.
allowed-tools: Bash(synapsidian *) Bash(synapsidian-projects *) Read Grep Glob
argument-hint: "<name> [project <name>] [target <date>] | add <tasks> to <milestone> | start|done|drop|status <milestone>"
---

# Milestone

Request: $ARGUMENTS

Run `synapsidian ref conventions` and follow it: notes in English, search before creating, one commit per run. Talk to the user in their language.

`synapsidian note where` must list `synapsidian-projects` under `extensions`; if it doesn't, send the user to `/synapsidian-projects:setup` and stop.

Milestone fields: `project` (required) · `status` planned | active | done | dropped · `start`, `target`: dates · `done_on`, set by itself when the status becomes done. A task belongs to a milestone through its own `milestone` field, a link to a milestone of the same project. Its tasks show on the milestone's board and on the hub's.

Never invent dates or scope: they come from the user; unknown is `TBD` in the body and an empty field.

## New

1. **Project:** use the one named, or the one the conversation is about. Resolve it with `synapsidian find --type project "<name>"`; ask if none fits.
2. **Search first:** `synapsidian find --type milestone "<name>"`. An open milestone with the same aim gets updated instead.
3. **Create** it. Titles must be unique across the vault, so start a generic name with the project's (`web-app beta`, not `Beta`):
   ```bash
   synapsidian note new --type milestone --title "<web-app beta>" --field project="<project title>" \
     --field summary="<one sentence: what is true when it is reached>" [--field start=YYYY-MM-DD] [--field target=YYYY-MM-DD]
   ```
4. **Write it** with Edit: **Goal** (what it delivers and for whom, 1-3 sentences) and **Exit criteria** (bullets that can be checked: "checkout works on the new API", not "done").
5. **Tasks.** Offer the project's open tasks that fit (`synapsidian query notes --type task --where status!=done --where status!=dropped`, those with this `project`), and new ones for exit criteria no task covers yet, created as `/synapsidian:task` does with the project. Put each in with `synapsidian note set --file "<task rel>" --field milestone="<milestone title>"`. Order between tasks is `blocked_by` (`/synapsidian:task`); ask when the user says one comes after another.
6. Add a hub Log line: `- YYYY-MM-DD: milestone [[<milestone>]] planned` (with `, target <date>` when set).

## Add tasks, start, done, drop, status

Find the milestone with `synapsidian find --type milestone "<words>"` and read it. Its tasks are the tasks whose `milestone` links to it.

- **Add or move tasks:** `--field milestone="<title>"` on each task; an empty value takes a task out. A task of another project can't join: say so.
- **Start:** `--field status=active`, plus `start` today when it has none, and a Log line in the milestone.
- **Status:** count its tasks by status and show `done/total`, what is in progress, what is blocked (a `blocked_by` task still open), and the days left to `target` (or how far past it). Writes nothing.
- **Done:**
  - Check its tasks and exit criteria. If tasks are still open, list them and ask: close them, move them to another milestone, or wait.
  - When the user confirms, set `--field status=done` (that sets `done_on`).
  - Add a Log line in the milestone with the outcome, and a hub Log line: `- YYYY-MM-DD: [[<milestone>]] done (<done>/<total> tasks)`.
- **Drop:** `--field status=dropped`, a Log line saying why, and a hub Log line. Its open tasks are the user's call: list them.

A changed `target` gets a dated line in the milestone's Log with the old date and the reason, so slips stay visible.

## Diagrams

After any run that changed the milestone or its tasks (not after **Status**), redraw its **Flow** and the hub's **Roadmap** as `${CLAUDE_PLUGIN_ROOT}/references/flows.md` says. Tasks waiting on each other are reported there; tell the user.

## Finish

```bash
synapsidian commit --skill synapsidian-projects-milestone --message "<planned|started|done|dropped|tasks for> <title>" "<milestone rel>" "<hub rel>" "<task rel>" ...
```

Status alone commits nothing. Tell the user: the milestone as a `[[link]]` with its status, target and `done/total` tasks, what is blocked, and what is left.
