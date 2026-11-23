---
name: review
description: Periodic vault review - weekly every Friday, monthly on the last Friday of the month, quarterly on the last Friday of the quarter - summarising what got done, decisions and open threads, plus a safe health pass; saves a review note. Use when the scheduled run fires or the user asks for a review ("weekly review", "przegląd tygodnia").
allowed-tools: Bash(synapsidian *) Bash(command -v synapsidian-work) Bash(synapsidian-work hook *) Bash(command -v synapsidian-projects) Bash(synapsidian-projects hook *) Bash(synapsidian-projects progress *) Read Grep Glob
argument-hint: "[week|month|quarter] [YYYY-MM-DD]"
---

# Review

The `synapsidian` command finds the vault by itself. Read `${CLAUDE_PLUGIN_ROOT}/references/conventions.md` first. Usually unattended: don't ask questions.

**Add-ons:** `command -v synapsidian-work && synapsidian-work hook review` prints the steps the work add-on adds; follow each at the step it names. When `command -v synapsidian-projects` succeeds and `synapsidian note where` lists `synapsidian-projects` under `extensions`, `synapsidian-projects hook review` prints the projects add-on's steps; follow them the same way. Nothing printed, or `no hook named review` from an older add-on: carry on without it.

Arguments: $ARGUMENTS

## 1. Which review

`synapsidian when review [--date D]` gives `kind` (week / month / quarter), `period_start` and `period_end`. An explicit kind in the arguments overrides it, keeping the dates of that kind's period. When it also gives `catch_up_for`, this run is the review of that missed Friday (the scheduled run fired on the weekend or the Monday after): use the period it gives as is. The note is named by `period_end`, so it carries that Friday's date.

## 2. Vault health

The weekday health run (`/synapsidian:health`, D97) already applies the safe fixes; this pass catches what it missed (the weekend, a skipped run) and lists what is still open.

```bash
synapsidian health --fix
```

It applies only the safe fixes (tag format, missing `created` from git, link letter case) and lists what it changed under `fixed`; everything else is a report. Don't fix anything else yourself: broken links, orphans, duplicates, schema problems, overdue tasks and `stuck_tasks` (in `doing` or `waiting` with no change for over 14 days) go into the review as a short list for the user.

## 3. Gather the period

- **Devlog:** the `devlog` block of every daily note in the period (`synapsidian block get --file "Daily/<date>.md" --name devlog`).
- **Tasks:** done in the period (`synapsidian query notes --type task --where status=done --where "done_on>=<start>" --where "done_on<=<end>"`), still open (`--where status!=done --where status!=dropped`), created in the period (`--where "created>=<start>"`).
- **Decisions, meetings, projects:** `synapsidian query notes --type decision --where "created>=<start>"`, the same for `meeting`, and, when the vault has projects (see conventions), `--type project --where status=active`.
- **Goals:** `synapsidian query notes --type goal --where status!=dropped`, then each goal's `## Progress log` lines dated in the period. Goals marked `achieved` stay in only when the change falls in the period (their log, or `modified`).
- **For month and quarter** reviews, also read the week reviews in the period (`synapsidian query notes --type review --where "period_start>=<start>"`) and build on them instead of re-reading every day.

## 4. Write the review note

```bash
synapsidian note new --type review --title "<kind> review" --field period=<kind> \
  --field period_start=<start> --field period_end=<end> --field summary="<one sentence: the shape of the period>"
```

Fill its sections (English, short, everything linked):
- **Summary:** 3-5 sentences on what the period was about.
- **Done:** the outcomes, grouped by project when the vault has projects, otherwise by topic, from devlogs and closed tasks (not every bullet: what moved).
- **Decisions:** links to decisions made, one line each.
- **Goals:** one line per active or paused goal: `[[Goal]]`, `progress`% (or "no progress figure"), the target and how far off it is, and what moved in the period from its Progress log ("nothing logged" when nothing did). Then the goals achieved in the period. A goal past its target, or active with nothing logged for the whole period, gets the choice it needs: a new target, `paused`, or `dropped`; the review only lists it, the user decides. No goals in the vault → leave the section empty.
- **Open threads:** overdue tasks, stuck work (health's `stuck_tasks`, each with the choice it needs: still live, back to `todo` with a date, or dropped; the review only lists them, the user decides), things promised and not done.
- **Patterns:** themes that recur across at least three separate notes or days in the period and were never named (D19), each with the notes that show it. None found → say so; don't invent.
- **Contradictions:** notes in the vault that now disagree (a decision superseded but still cited, a fact stated two ways), each with both links. Report only: don't rewrite notes on this basis.
- **Vault health:** what `health --fix` fixed (count) and the remaining issues worth the user's attention.

Don't edit the daily note: the next morning run lists the review under "Written overnight", and the note is also reachable from the Reviews folder.

## 5. Commit

One commit: the review note plus every file `health --fix` changed (`--skill review --message "<kind> review <end>, <n> health fixes"`). Reply with the Summary and Open threads sections.
