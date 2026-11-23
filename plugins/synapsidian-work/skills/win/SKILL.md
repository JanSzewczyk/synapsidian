---
name: win
description: Log a work win in the synapsidian vault's brag log (synapsidian-work add-on) - one note in Wins/ per thing the user got done that is worth bringing up at a performance review, with its date, impact (small, medium, large), evidence links and who saw it - or list the wins of a period. Use when the user wants an achievement remembered for later ("log a win", "add this to my brag doc", "zapisz to jako sukces", "dopisz do brag logu", "this is worth mentioning at my review", "I shipped X, keep it for my review") or asks what they achieved ("my wins this quarter", "co osiągnąłem w tym kwartale", "what can I bring to my performance review").
argument-hint: "[<what happened>] | list [week|month|quarter|half|year|<from> <to>]"
allowed-tools: Bash(synapsidian *) Bash(synapsidian-work hook *) Read Grep Glob
---

# Wins

The `synapsidian` command (from the synapsidian plugin) finds the vault by itself; `synapsidian note where` must list `synapsidian-work` under `extensions` and the schema must know the `win` type, otherwise run `/synapsidian-work:setup` first. Run `synapsidian ref conventions` before writing and follow it.

Request: $ARGUMENTS

A win is something the user did, or drove, that someone else benefits from: a release, a fix that unblocked people, a migration finished, a process improved, help that mattered. One note per win, in English whatever language the user writes in.

## Log a win

1. **Not twice:** `synapsidian find --type win "<key words>"` and `synapsidian query notes --type win --where "date>=<date minus 14 days>"`. The same win already there: add what is new to it (evidence, who saw it) instead of a second note.
2. **The fields**, from what the user said and the vault, never invented:
   - `date`: when it happened (default today).
   - `impact`: `small` (helped the user's own work or one person), `medium` (the team or one stakeholder group), `large` (beyond the team: customers, other teams, the company). Unclear: `medium`, and say so in the reply.
   - `evidence`: links that prove it, as `[[note]]` for vault notes (the task, meeting, decision or project note it came from; look them up with `synapsidian find`) and URLs for pull requests, tickets, docs or messages the user named. Never a link you did not see.
   - `summary`: one sentence, the outcome rather than the activity.
3. **Create it:**

   ```bash
   synapsidian note new --type win --title "<≤8 words, the outcome>" --field date=<YYYY-MM-DD> \
     --field impact=<impact> --field evidence="[[T12 Fix the export]],https://example.com/pr/123" \
     --field summary="<one sentence>"
   ```

4. **Fill the sections** with `synapsidian note fill --file "<rel>" --section <name>` (text on stdin):
   - **What:** what the user did, in the first person and past tense, two to four sentences. Their phrasing survives.
   - **Impact:** who benefits and how; figures only when the user or a linked note gives them.
   - **Evidence:** the evidence links again, each with a few words on what it shows.
   - **Who saw it:** the people who know about it, as `[[Person]]` when a person note exists (`synapsidian find --type person`), else their name as plain text. Never create a person note here. Unknown: leave it empty.
5. **Commit:** `synapsidian commit --skill win --message "win: <title>" "<rel>"`, and reply in one or two lines: the title, its impact, and any field left empty that the user could add.

## List wins

`list` with a period (default: the last 90 days). `week`, `month` and `quarter` run from this week's Monday, the 1st of this month or the first day of this quarter to today; `half` and `year` count 183 and 365 days back from today; two dates are taken as given. List them as `synapsidian-work hook review` describes under Listing wins, grouped by month for a half or a year. Read only; nothing is committed.

## Rules

- Only what the user said or a note shows; never inflate an impact, add a number or credit the user with someone else's work. Shared work says who else did it.
- Compensation, ratings and other people's performance stay out of wins.
- One question at most, and only when the win itself is unclear (which release, which week).
