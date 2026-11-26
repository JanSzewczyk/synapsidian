# synapsidian-dock

The synapsidian brief on screen, without a Claude turn. A Claude Code mod on top of `synapsidian`: a band above the prompt says what is overdue, due today and in progress, and its **Tasks** button opens a pane where one key closes, starts, moves or drops a task. Nothing in it assumes a job or a project; it shows what the core's session brief shows.

## Requirements

- The `synapsidian` plugin 0.35.x, enabled (the manifest requires `~0.35.0`; the dock calls its `synapsidian` command)
- Claude Code 2.1.299 or later, in the terminal or the desktop app (the dock's spacing and type sizes need it; it is tested on 2.1.323); older versions draw no dock, WSL sessions and `--safe-mode` load no mods, and synapsidian works as before

## Install

```
/plugin install synapsidian-dock@synapsidian
```

Then start a new session. There is nothing to set up: the vault is the one `synapsidian` is configured with.

## Options

| Option | What it does |
|---|---|
| `show_dock_band` | Show the band as soon as a session starts (default on); off, it shows when you run `/synapsidian` |

## What it shows

- **Band above the prompt**, shown from the start of every session (with `show_dock_band` off, by **`/synapsidian`**): a synapsidian mark (`✻` in the terminal), then the overdue task (or how many) in the theme's alert colour, how many are due today, what is in progress and the Inbox count (on the desktop as badges), kept current every 5 minutes and after Claude writes in the vault. **Tasks** opens the pane, the close button hides the band for the session, and **`/synapsidian`** shows it again, even while Claude works; `/synapsidian tasks` also opens the pane.
- **The pane** opens on the date and today's meetings and Inbox count, with refresh and how old the lists are on the right. Three tabs, each with its count: Today (the brief's lists), Projects (open tasks by project, when an add-on gives tasks a `project` field), Writes (vault notes changed in this session). In the terminal the keys are `1`, `2`, `3` and `r`; Esc closes.
- **Each task row**, in the terminal, reads: its state mark, `●` in progress, `○` to do, `◑` waiting, `⊘` blocked while a task it waits on is open; its id; its title; and on the right when it is due (`9d late`, `today`, `tomorrow`, a weekday, a date), or `high` for an undated high-priority task. On the desktop it reads id and title, then badges: when it is due (red when late, amber for today, a later date as plain text), `High` for high priority, and its state (`● In progress`, `○ To do`, `◑ Waiting`, `⊘ Blocked`); hovering it shows its two likeliest status moves (for a task in progress, *Done* and *Waiting*) before the badges. Rows go by priority, then due date, and a section's count is a badge too.
- **A press on a row** (on the desktop, on its title) opens its details: the note's summary, its state, due date, priority, project and repeat (on the desktop as badges, in a card with the title in bold, which a press on its id closes), then its actions: the two likeliest status moves as buttons (`s` Start, `d` Done, `w` Waiting, `t` back to to-do), **Status** and **Due** pickers (today, the end of this week, month or year, each with its date, or no date), then **Ask Claude** (`a`) and **Hand to Claude** (`c`), each a draft in the prompt box that Enter sends, and **Open in Obsidian** (`o`). A second press closes it. The keys are the terminal's; the desktop is clicked.
- Colours are the Claude theme's own (`claude`, `error`, `success`, `warning`, `inactive`), so the dock follows a light, dark or custom theme. The desktop's badges are images, which follow the system's light or dark scheme instead.
- `claude -p "/synapsidian"` prints the same lists as text.

## How it meets the core

Only through the `synapsidian` command: `synapsidian brief --json` for the lists, `synapsidian note set` and `synapsidian commit --skill task` for a change, whose commit message ends in `(dock)`. So the vault path, the schema checks, `done_on`, folder moves and the next occurrence of a recurring task are the core's own, and every change is a commit you can revert. Nothing is written without a key press. The desktop app leaves plugins' commands off a mod's PATH, so where `synapsidian` isn't on it the dock runs the installed synapsidian's `bin/synapsidian` directly. Sessions share a state less than a minute old, so many open sessions don't each read the vault.

## Development

`claude plugin validate plugins/synapsidian-dock` lists the mod's hooks and calls; `claude plugin test` in this folder runs its tests; `claude --plugin-dir plugins/synapsidian-dock` loads it for one session with reload on save.
