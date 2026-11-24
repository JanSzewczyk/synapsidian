# synapsidian-work

The work add-on for the `synapsidian` plugin: 1:1 notes and prep, the stand-up note, retro meeting notes, a win log for performance reviews, and your pull requests, Jira tickets and unanswered email and Slack asks in the morning brief. Everything tied to a job lives here, so the core stays usable for a personal vault.

## Requirements

- [Claude Code](https://claude.com/claude-code); not claude.ai or Cowork, because the plugin ships a `bin/` command they refuse
- The `synapsidian` plugin, set up with `/synapsidian:setup` (installing synapsidian-work installs `synapsidian` too if it's missing)
- Each source is optional, and a source you don't configure is skipped silently:
  - [`gh`](https://cli.github.com), signed in, for pull requests
  - the Atlassian connector for Jira
  - Gmail and Slack connectors for asks

## Install

```
/plugin install synapsidian-work@synapsidian
/synapsidian-work:setup
```

Setup checks the work sources, installs the schema extension into the vault (`.synapsidian/extensions/synapsidian-work/`, kept in the vault's git so the vault still validates on a device without synapsidian-work), fills `team`, `company` and `manager` in `About.md`, schedules the stand-up, and ends with a report of what is ready, what it added and what is still needed. Re-run it after every synapsidian-work update: it re-installs the extension when its version changed.

## Options

Set in `/plugin` → synapsidian-work → configure. Leave any empty to skip that source.

| Option | What it does |
|---|---|
| `github_repos` | `owner/name` of each repository whose pull requests the brief and the stand-up read |
| `jira_projects` | Key of each Jira project the brief and the stand-up query, e.g. `ABC` |
| `work_repo_paths` | Absolute path of each local clone the stand-up reads `git log` from |
| `standup_days` | Weekdays of the stand-up, e.g. `mon,tue,wed,thu,fri` (the default) |
| `standup_time` | Local time the stand-up starts, `HH:MM` (default `10:00`); the note is prepared an hour before |

## Skills

| Skill | What it does |
|---|---|
| **setup** | `/synapsidian-work:setup [check\|schedule]`: install or update the schema extension in the vault, check the work sources, fill team / company / manager / working hours and the `## Work` section of `About.md`, schedule the stand-up |
| **work-brief** | `/synapsidian-work:work-brief`: PRs waiting on you, ready or stuck, open Jira tickets, unanswered email and Slack asks filed as tasks; PRs are listed, never filed (part of `/synapsidian:morning`) |
| **standup** | `/synapsidian-work:standup`: stand-up note from devlogs, today's sessions, Jira, GitHub, git and the calendar (scheduled an hour before the stand-up) |
| **one-to-one** | `/synapsidian-work:one-to-one`: prepare a 1:1 note, add or work out a topic, carry action items forward, read it back |
| **one-to-one-triage** | `/synapsidian-work:one-to-one-triage`: interview-driven prep of a 1:1, topic by topic, ending in an English talking script |
| **win** | `/synapsidian-work:win`: log a win in the brag log (`Wins/`: date, impact, evidence, who saw it) or list a period's wins; the 1:1 prep with your manager and `/synapsidian:review` list them too |

## How it meets the core

- **Schema:** the extension adds the 1:1, stand-up and retro meeting kinds, the win log, work task sources, a Jira key on projects and the work fields of `About.md`. The core merges whatever is installed in `.synapsidian/extensions/`.
- **Core skills** reach synapsidian-work only through `synapsidian-work hook <name>`: the morning brief, meeting notes, the review and the scheduled runs. Without synapsidian-work they skip that part.
- **synapsidian-work** calls the core through `synapsidian ...` on PATH and never imports its code.
