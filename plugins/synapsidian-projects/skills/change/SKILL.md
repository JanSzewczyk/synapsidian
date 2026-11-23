---
name: change
description: Track one change to a project (synapsidian-projects add-on) - a note in Projects/<Project>/Changes/ that goes proposed, doing, done or dropped, says why and what changes, and links its specs, decisions and tasks. Use when the user plans, starts, finishes or abandons a feature, migration, refactor or process change ("open a change for", "zaplanuj zmianę", "the migration is done", "zamknij zmianę"). Single steps are /synapsidian:task; a choice between options is /synapsidian-projects:decide.
allowed-tools: Bash(synapsidian *) Bash(synapsidian-projects *) Read Grep Glob
argument-hint: "<what changes> [project <name>] | start|done|drop <change>"
---

# Change

Request: $ARGUMENTS

Run `synapsidian ref conventions` and follow it: notes in English, search before creating, one commit per run. Talk to the user in their language.

`synapsidian note where` must list `synapsidian-projects` under `extensions`; if it doesn't, send the user to `/synapsidian-projects:setup` and stop.

Change fields: `project` (required) · `status` proposed | doing | done | dropped · `specs`, `decisions`, `tasks`: links · `done_on`, set by itself when the status becomes done. Several links go in one value: `--field tasks="[[T3 Ship it]],[[T4 Plan, then test]]"`.

Never invent facts: why, scope and plan come from the user and the project's notes; unknown is `TBD`.

## Open a change

1. **Project:** use the one named, or the one the conversation is about. Resolve it with `synapsidian find --type project "<name>"`; ask if none fits.
2. **Search first:** `synapsidian find --type change "<subject>"`. An open change with the same aim gets updated instead.
3. **Create** it as `proposed`, with an imperative title:
   ```bash
   synapsidian note new --type change --title "<Move checkout to the new payment API>" --field project="<project title>" \
     --field summary="<one sentence: what changes and why>" \
     [--field specs="[[<spec>]]"] [--field decisions="[[<decision>]]"]
   ```
   Link only specs and decisions that exist; find them with `synapsidian find --type spec|decision`.
4. **Write it** with Edit:
   - **Why:** the problem or the goal.
   - **What changes:** the effect, for users or for the system; what stays the same.
   - **Plan:** ordered steps.
5. **Tasks.** Ask whether the plan's steps should become tasks. Create each one as `/synapsidian:task` does (`synapsidian note new --type task ... --field project="<project title>"`), then set them all on the change:
   ```bash
   synapsidian note set --file "<change rel>" --field tasks="[[<task 1>]],[[<task 2>]]"
   ```
   A step that needs a decision first is a call for `/synapsidian-projects:decide`; say so. A step that can start only after another gets `blocked_by` on its task, as `/synapsidian:task` does, so the plan's order is in the notes and the diagram.
   Then draw the change's **Flow** as `${CLAUDE_PLUGIN_ROOT}/references/flows.md` says, and redraw it on **Start** and **Done** below.
6. Add a hub Log line: `- YYYY-MM-DD: change [[<change>]] proposed`.

## Start, finish, drop

Find the change with `synapsidian find --type change "<words>"` and read it, with its tasks.

- **Start:** `--field status=doing`, plus a Log line in the change.
- **Done:**
  - Check its tasks. If any are still open, list them and ask: close them, move them to another change, or wait.
  - When the user confirms, set `--field status=done` (that sets `done_on`).
  - Add a Log line in the change with the outcome.
  - Add a hub Log line: `- YYYY-MM-DD: [[<change>]] done: <outcome in a few words>`.
  - If the change altered how something works, update the specs it links, in place, the way `/synapsidian-projects:spec` does. Mention each spec you edited.
- **Drop:** `--field status=dropped`. Add a Log line in the change saying why, and a hub Log line. Its open tasks are the user's call: list them.

## Finish

```bash
synapsidian commit --skill synapsidian-projects-change --message "<proposed|started|done|dropped> <title>" "<change rel>" "<hub rel>" ...
```

Include the tasks and specs this run created or edited. Tell the user: the change as a `[[link]]` with its status, its tasks (open and done), and the specs it touched.
