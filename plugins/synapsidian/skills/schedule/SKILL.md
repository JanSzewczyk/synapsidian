---
name: schedule
description: Set up, check or repair the synapsidian plugin's recurring runs as desktop scheduled tasks - vault health, morning brief, evening devlog and the Friday review (default times the user can move), plus any add-on's runs - and tell the user exactly how to set their permission mode. Use when the user asks to schedule, automate or check synapsidian's recurring runs ("set up synapsidian's scheduled tasks", "zaplanuj automaty", "is the morning brief scheduled", "why didn't the evening run work").
argument-hint: "[check]"
allowed-tools: Bash(synapsidian *) Bash(command -v synapsidian-work) Bash(synapsidian-work hook *) Read
---

# Scheduled runs

Arguments: $ARGUMENTS (`check` = report only)

The runs (D60, D62, D65, D66), with their default times:

| Task id | Title | Default cron (local) | Prompt |
|---|---|---|---|
| `synapsidian-health` | Synapsidian — vault health | `15 8 * * 1-5` | `/synapsidian:health` |
| `synapsidian-morning` | Synapsidian — morning brief | `0 9 * * 1-5` | `/synapsidian:morning` |
| `synapsidian-evening` | Synapsidian — evening devlog | `0 20 * * *` | `/synapsidian:evening` |
| `synapsidian-review` | Synapsidian — Friday review | `0 16 * * 5` | `/synapsidian:review` |
| `synapsidian-research-watch` | Synapsidian — watched research | `30 8 * * 1` | `/synapsidian:research watch` |

`synapsidian-research-watch` only when the vault has a watched dossier (`synapsidian query notes --type research --where "watch!="` returns one); offer it then, and leave it alone in `check` otherwise (D134).

Each prompt is the slash command followed by: "Unattended run of the synapsidian plugin's <name> skill: the user is not present, so do not ask questions. Do what the skill says, commit, and reply with its short report." The times are defaults, not rules: keep a cron or a title the user changed (an earlier morning, a title in their own language) and mention it in the report. Only a missing task, a wrong prompt or a wrong folder is a fix. Keep the order the times give, if the user asks to move them: health before the morning brief, so the brief lists the health commit; the review on Fridays (a missed one fires on the weekend or Monday and reviews that Friday).

**Add-ons:** if `command -v synapsidian-work` succeeds, run `synapsidian-work hook schedule` and follow what it prints after your own rows. Leave tasks whose id starts with an add-on's name alone otherwise.

## 1. Check

List the scheduled tasks (scheduled-tasks tools). For each synapsidian task: exists, enabled, its cron (the default, or the user's own), last run and its status (`list_task_runs`). A run that is still `running` long after it started, or a missing commit in the vault for that run, usually means it is waiting on a permission prompt: the task's permission mode isn't `auto`.

With `check`, report as a table and stop.

## 2. Create or fix

Ask once before creating or changing tasks (they are standing configuration), then create the missing ones with `create_scheduled_task` (task id, title, description, default cron, prompt as above, notifications off) or fix a wrong prompt with `update_scheduled_task`. Change a cron only when the user asks. Never delete a task the user made.

## 3. Permission mode and folder (the user does this)

The tools can't set either. Tell the user: open **Scheduled** in the app sidebar → each synapsidian task:

- permission mode **auto** (like their other unattended tasks). Never suggest bypassing permissions. In the default mode every run stops at its first Skill call and waits for a person.
- folder **the vault** (`synapsidian note where` prints its path). A new task takes the folder of the session that created it; if that is a code checkout or the plugin's own source, the runs break the day that folder moves or is deleted.

Tasks run while the desktop app is open; a run missed while the Mac slept fires on the next launch. The evening run handles that (the queue keeps every unlogged day).
