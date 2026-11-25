# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The sections before synapsidian-dock 0.6.0 were reconstructed from git history on 2026-11-17, from the
commits that changed each plugin's version; some versions in between had no release commit of their
own and are folded into the next one.

## [0.34.1 synapsidian] — 2026-11-25

### Changed

- README: developed and tested on macOS; setup also finds Obsidian on Windows and Linux, and the hooks need a POSIX shell (`/bin/sh`).

## [0.7.1 synapsidian-work] — 2026-11-25

### Fixed

- The setup skill's description and the README name `working_hours` and the `## Work` sections among the About fields setup fills.

## [0.13.1 synapsidian-projects] — 2026-11-25

### Fixed

- `/synapsidian-projects:architect` no longer advertises a `[module]` argument it never read; it takes `<project> [app]`.

## [0.7.2 synapsidian-dock] — 2026-11-25

### Fixed

- The README requires synapsidian 0.34.x, as the manifest's `~0.34.0` does, instead of "0.32.0 or later".

## [0.34.0 synapsidian] — 2026-11-24

### Added

- About.md declares its body sections in the schema; an add-on adds its own with `extend: about: sections:` (a section, or a `###` subsection of one).
- `setup about [--owner P]` lists the questions still empty; setup interviews you about them, each with a Skip, and asks again the next time it runs.
- `note fill` takes the declared sections of About.md (`--subsection`), never Rules.
- About fields `language` and `interests`.

### Changed

- The brief labels each About part (1,200 characters instead of 700).
- `working_hours` moved to synapsidian-work; elsewhere `setup apply` turns it into a line under How I work.

## [0.7.0 synapsidian-work] — 2026-11-24

### Added

- `working_hours` field and a `## Work` section (with `### Work` under Current focus) in About.md; setup interviews you about them.

### Changed

- Requires synapsidian ~0.34.0.

## [0.13.0 synapsidian-projects] — 2026-11-24

### Added

- A `## Projects` section in About.md; setup asks about it.

### Changed

- Requires synapsidian ~0.34.0.

## [0.7.1 synapsidian-dock] — 2026-11-24

### Changed

- Requires synapsidian ~0.34.0.

## [0.7.0 synapsidian-dock] — 2026-11-17

### Added

- On the desktop, badges: each row shows its state (`● In progress`, `○ To do`, `◑ Waiting`, `⊘ Blocked`), `High` for high priority and when it is due, red when late and amber for today. Section counts, the open task's facts and the band's facts are badges too.

### Changed

- On the desktop, a row opens on a press of its title (the `›` toggle is gone). The open task is a card with its title in bold, closed by a press on its id.
- Hovering a row tints it with rounded corners and shows its two likeliest status moves before the badges, without moving or resizing the row.
- Tabs are equal buttons with their counts. The desktop no longer shows hotkey badges, which read as counts.
- The band's close button is a ✕.

### Fixed

- The open task's card and a hovered row are tinted again on the desktop, which drew nothing for the theme's `userMessageBackground`.

## [0.6.0 synapsidian-dock] — 2026-11-17

### Changed

- Needs Claude Code 2.1.299 or later (was 2.1.287): the dock's spacing and type sizes need it, and older builds draw no dock.
- A new look in the Claude theme's own colours, so the dock follows a light, dark or custom theme.
- The band opens with a synapsidian mark (`✻` in the terminal); only the overdue task is in the alert colour, and the close button is the app's own.
- The pane opens on the date, today's meetings and the Inbox count; tabs show their counts, and Refresh says how old the lists are.
- A row reads state mark, id, title and when it is due (`9d late`, `today`, `tomorrow`, a weekday, a date). On the desktop, a row opens from the `›` at its end.
- The Claude dropdown is now two buttons, Ask Claude (`a`) and Hand to Claude (`c`); both still only put a draft in the prompt box.

### Added

- On the desktop, hovering a row shows its two likeliest status moves (for a task in progress, Done and Waiting).
- The details offer those two moves as buttons that change the task with one key while the pane has focus: `s` Start, `d` Done, `w` Waiting, `t` back to to-do.

## [0.33.1 synapsidian] — 2026-11-17

### Fixed

- `block set` and `note set` refuse text that looks like a credential, as `note new` and `note fill` already did; the session digest and memory reader print `[redacted]` in its place.
- A date in a file name is the note's own date (else `created`), and `note new` refuses a title that repeats the file name's date.
- `synapsidian commit` reports the broken links a commit added (and commits anyway), so ingest, research, think and architect no longer run a health pass for it.
- `health` lists a note as an orphan unless a note other than a daily, review or capture note links to it.
- `daily` leaves a brief the morning run filled alone.

## [0.12.5 synapsidian-projects] — 2026-11-17

### Fixed

- Text fixes in project and architect after the core's commit now reports broken links (D158).

## [0.6.3 synapsidian-work] — 2026-11-17

### Fixed

- Follows the core's D158 changes; the extension version moves with the plugin.

## [0.5.0 synapsidian-dock] — 2026-11-13

### Changed

- The band no longer shows when a session starts; `/synapsidian` shows it. The `show_dock_band` option now defaults to off and, turned on, brings the band back at every start.

## [0.4.1 synapsidian-dock] — 2026-11-05

### Changed

- Back to the Status, Due and Claude dropdowns with an Open in Obsidian button: 0.4.0's Actions menu looked much worse in the desktop app.

## [0.4.0 synapsidian-dock] — 2026-11-05

### Added

- An Actions button that opens a column of the task actions with no value (ask Claude about it, ask Claude to do it, open in Obsidian).

## [0.3.0 synapsidian-dock] — 2026-11-05

### Changed

- One control per kind of task action: a Status dropdown showing the current status, a Due dropdown (today, this Sunday, the month's or year's end, or no date), Open in Obsidian, and a Claude dropdown whose drafts wait in the prompt box.

## [0.2.0 synapsidian-dock] — 2026-11-05

### Added

- Rows show a state badge (to do, in progress, waiting, blocked) and a priority chip, and go by priority, then due date.
- A press on a row opens the task's summary, its facts and its actions; `/synapsidian tasks` opens the pane.

## [0.1.3 synapsidian-dock] — 2026-11-05

### Fixed

- In the desktop app `/synapsidian` shows the band instead of printing the lists, and the band keeps a step of space so its buttons don't overlap the band above.

## [0.1.2 synapsidian-dock] — 2026-11-05

### Changed

- The band is the way in: its Tasks button opens the pane, ✕ hides the band for the session and `/synapsidian` shows it again; `claude -p` still gets the lists as text.

## [0.1.1 synapsidian-dock] — 2026-11-05

### Fixed

- The dock finds `synapsidian` in the desktop app, which leaves plugins' `bin/` folders off a mod's PATH: it runs the newest installed synapsidian's `bin/synapsidian` instead.
- A timeout is no longer reported as a missing command, and button labels no longer repeat their hotkey.

## [0.1.0 synapsidian-dock] — 2026-11-05

### Added

- First release: the dock moves out of the core into its own add-on, a Claude Code mod with a band above the prompt (overdue, due today, in progress, Inbox) and a `/synapsidian` pane (Today, Projects, Writes) whose keys close, start, move or drop a task, open it in Obsidian or draft a prompt about it. It reaches the core only through `synapsidian brief --json`, `note set` and `commit`.

## [0.32.3 synapsidian] — 2026-11-05

### Added

- `brief --json` carries each task's one-line summary, for the dock's details.

## [0.32.2 synapsidian] — 2026-11-05

### Fixed

- Setup finds Obsidian on Linux and Windows too (Flatpak included): its folder, install locations, process check, how to quit it and the command that opens a vault, per system. It asks you to confirm Obsidian is closed where it can't check, and URL-encodes the vault name.

## [0.32.1 synapsidian] — 2026-11-05

### Removed

- The dock mod leaves the core for the new synapsidian-dock add-on; the core keeps `brief --json` for it.

## [0.32.0 synapsidian] — 2026-11-05

### Added

- `brief --json`: the session brief's agenda as JSON, from the same function as the brief.
- The first synapsidian dock mod, a band and a `/synapsidian` task pane (moved to synapsidian-dock in 0.32.1).

## [0.31.5 synapsidian] — 2026-11-04

### Changed

- Each plugin has its own README (what it is, requirements, install, options, every skill); the root README links to them.

## [0.31.4 synapsidian] — 2026-11-04

### Added

- Every setup ends with a ready / added / still needed report; still needed names each missing Obsidian plugin, what needs it and how to add it.

## [0.12.4 synapsidian-projects] — 2026-11-04

### Changed

- A README of its own, with every skill and how it meets the core.

## [0.12.3 synapsidian-projects] — 2026-11-04

### Added

- Setup ends with the ready / added / still needed report.

### Changed

- Requires the Excalidraw Extras Obsidian plugin.

## [0.6.2 synapsidian-work] — 2026-11-04

### Changed

- A README of its own, with every skill and how it meets the core.

## [0.6.1 synapsidian-work] — 2026-11-04

### Added

- Setup ends with the ready / added / still needed report.

## [0.31.3 synapsidian] — 2026-11-03

### Fixed

- A space after the comma in a list of links no longer cuts the next wikilink at its first comma: `[[A]], [[B, with commas]]` is read whole.

## [0.31.2 synapsidian] — 2026-11-03

### Fixed

- A recurring task's next occurrence no longer copies `blocked_by`.

## [0.31.1 synapsidian] — 2026-11-03

### Added

- The weekly review gets a Projects section from synapsidian-projects when that add-on is installed.

## [0.31.0 synapsidian] — 2026-11-03

### Added

- Tasks can wait on other tasks (`blocked_by`): the briefs say blocked by while a blocker is open, and closing a task names the tasks it frees.

## [0.12.2 synapsidian-projects] — 2026-11-03

### Fixed

- Text on doing and waiting nodes stays readable in Obsidian's dark theme.

## [0.12.1 synapsidian-projects] — 2026-11-03

### Fixed

- A blocker counts wherever it is filed; the status window starts the day after the last status line; done and one-day milestones show in the gantt; a map rename needs the old title gone; a flow refuses another project's milestone or change.

## [0.12.0 synapsidian-projects] — 2026-11-03

### Added

- Project status: what closed since the hub's last Log line, what is in progress or blocked, and each open milestone's progress and days to target, written only on your yes.
- Project close: asks per open task, milestone and change whether to close, drop or move it, writes a Retro and closes the project in one commit.
- A Projects section in the weekly review, one progress line per active project.

## [0.11.0 synapsidian-projects] — 2026-11-03

### Added

- Hubs get a Risks section, and projects link their owner, stakeholders and goals.
- Flow diagrams (Mermaid): the hub's Roadmap as a gantt of milestones and a flowchart of waiting tasks, and a Flow per milestone and change.

### Fixed

- A new map node goes below any box it would cover, and nothing already drawn moves.

## [0.10.0 synapsidian-projects] — 2026-11-03

### Added

- Milestones: a milestone type with a board of its tasks, the milestone skill, a Milestones Base, a hub view and a map branch; setup adds them to older hubs.

## [0.9.1 synapsidian-projects] — 2026-11-03

### Fixed

- The map colours notes by status, adds thinking notes, drops retired specs and keeps a node when its note is renamed; `+N more` links to the hub's list, and `--max-leaves` limits a branch.

## [0.30.1 synapsidian] — 2026-11-02

### Added

- Watched research dossiers that refresh on a schedule, and a folder ingest that resumes where it stopped.
- The evening run reads Claude Code's auto-memory files that changed; a prompt starting with `>>` goes to the Inbox without a model turn.
- Sources carry a `source_quality`; find and recap run in a subagent that returns only the answer; the morning brief shows one old note from the archive.
- Person and goal notes show their meetings, tasks and linked work as Bases.

### Fixed

- The session brief marks note titles as data, and the overnight and Done windows count from the previous morning run.

## [0.9.0 synapsidian-projects] — 2026-11-02

### Added

- A project's repository is a remote URL or a local path; each device finds its own clone of a URL, and an older clone's scan never overwrites newer facts.

## [0.30.0 synapsidian] — 2026-10-30

### Added

- Sessions off the record, recurring tasks, a quote check, wanted notes, `find --related` and "Still true?" facts in the brief.

### Fixed

- Hardening from an audit: the writing scripts never touch CLAUDE.md, `.claude/`, About.md, Templates/ or `.synapsidian/`; frontmatter is typed as YAML 1.2; task ids and daily-note blocks are written under a lock; missed Friday reviews and second morning runs get the right window.

## [0.29.0 synapsidian] — 2026-10-30

### Fixed

- Setup turns off the core Templates plugin, which pasted the generated Templater templates as raw JavaScript; the generated templates move to Templates/Generated/, older vaults included.

## [0.8.2 synapsidian-projects] — 2026-10-30

### Fixed

- Follows the core's audit fixes (D118-D126).

## [0.8.1 synapsidian-projects] — 2026-10-30

### Fixed

- Its generated templates move to Templates/Generated/ with the core's.

## [0.6.0 synapsidian-work] — 2026-10-30

### Fixed

- Follows the core's audit fixes (D118-D126).

## [0.28.1 synapsidian] — 2026-10-29

### Changed

- The evening run writes as many devlog bullets as a day needs and links each note it created from one related note, so new notes aren't orphans.

## [0.28.0 synapsidian] — 2026-10-29

### Added

- Calendar Bases is a required Obsidian plugin, and the task, meeting and goal Bases get a Calendar view.
- An add-on can require Obsidian plugins; setup offers recommended ones, such as Claudian.

## [0.27.2 synapsidian] — 2026-10-29

### Fixed

- Marketplace entries carry author, license and dependencies, and each plugin has a display name.

## [0.27.1 synapsidian] — 2026-10-29

### Changed

- Dataview and Tasks stay optional; the Obsidian plugins reference says why.

## [0.8.0 synapsidian-projects] — 2026-10-29

### Added

- Requires the Folder notes Obsidian plugin, so a project's folder opens its hub.

## [0.7.1 synapsidian-projects] — 2026-10-29

### Fixed

- The marketplace entry carries author, license and dependencies, and a display name.

## [0.5.1 synapsidian-work] — 2026-10-29

### Fixed

- The marketplace entry carries author, license and dependencies, a display name, and no longer lists architecture notes (moved to synapsidian-projects).

## [0.7.0 synapsidian-projects] — 2026-10-28

### Added

- Debug notes (bug investigations) and incident postmortems, each with a template, a Base, a hub view, a map branch and a skill.

## [0.27.0 synapsidian] — 2026-10-28

### Added

- Goals: a goal type with a Base, shown in the morning brief near its target and in the review.
- People get `last_contact` and `follow_up`; the brief lists due follow-ups.
- Concept and literature notes; ingest writes a literature note for a source worth keeping whole.

## [0.26.0 synapsidian] — 2026-10-28

### Added

- Links can hold a URL beside wikilinks.

## [0.5.0 synapsidian-work] — 2026-10-28

### Added

- A retro meeting kind (Went well, Didn't go well, Ideas).
- A win log for performance reviews: `/synapsidian-work:win`, a Wins Base, and the period's wins in the review and the 1:1 prep with your manager.

## [0.24.0 synapsidian] — 2026-10-28

### Added

- Templater is a required Obsidian plugin, and every note type gets a template generated from the schema, which prompts for the title, summary and choices and files the note where `note new` would.

## [0.6.0 synapsidian-projects] — 2026-10-28

### Added

- Templates for project notes, and a Links section on the hub.

## [0.4.0 synapsidian-work] — 2026-10-28

### Added

- Meeting templates per kind (team, review, external, stand-up).

## [0.23.0 synapsidian] — 2026-10-28

### Changed

- A type two extensions define is a warning, not an error.

## [0.5.0 synapsidian-projects] — 2026-10-28

### Added

- Architect moves here from synapsidian-work: a scan for any language (Vue as a profile), the repository taken from the project hub, notes under the project's Architecture folder; setup moves existing notes.

## [0.3.0 synapsidian-work] — 2026-10-28

### Removed

- Architect moves to synapsidian-projects.

### Fixed

- The stand-up checks `work_repo_paths`.

## [0.22.0 synapsidian] — 2026-10-28

### Changed

- `note new` refuses missing required fields, `done_on` works for any type, and links keep commas inside `[[...]]`.

## [0.4.0 synapsidian-projects] — 2026-10-28

### Added

- An Excalidraw mind map per project that keeps your edits on refresh, and spec and change notes with their skills.

## [0.21.0 synapsidian] — 2026-10-28

### Added

- `block set --before` places a missing section.

## [0.3.0 synapsidian-projects] — 2026-10-28

### Added

- The project skill (a read-only repository scan into the hub) and the decide skill (MADR decisions numbered per project).

## [0.20.0 synapsidian] — 2026-10-28

### Removed

- The project type leaves the core for synapsidian-projects; extensions merge types before `extend:` and never break the schema.

## [0.2.0 synapsidian-projects] — 2026-10-28

### Added

- The project type, with a folder per hub; setup files existing project notes into their folders.

## [0.5.2 synapsidian-projects] — 2026-10-28

### Changed

- Internal clean-up of the map script.

## [0.5.1 synapsidian-projects] — 2026-10-28

### Fixed

- The architect scan counts `bin/` executables as entry points.

## [0.19.0 synapsidian] — 2026-10-28

### Changed

- Setup switches older vault Bases to filter by type.

## [0.1.0 synapsidian-projects] — 2026-10-28

### Added

- First release: the projects add-on with its setup, a project extension that files project notes under Projects/<Project>/, and a board per project hub.

## [0.18.0 synapsidian] — 2026-10-28

### Added

- A type's folder can follow a link field (`folder_by`), so notes move when the link changes; Bases select by type outside Archive; the brief shows projects only when the schema has them.

## [0.2.1 synapsidian-work] — 2026-10-28

### Changed

- Follows the core's `folder_by` change.

## [0.17.0 synapsidian] — 2026-10-28

### Added

- Tasks get Tn ids; your vault rules live in About.md; a daily health run proposes where to link orphan notes.

## [0.2.0 synapsidian-work] — 2026-10-28

### Changed

- Work sources are lists, and pull requests are listed, never filed as tasks.

## [0.16.0 synapsidian] — 2026-10-20

### Added

- Meeting import fills a meeting note from its Gemini notes and files the next steps as tasks.

### Changed

- Plugin code a vault already tracks stays tracked; the reference gives the step to untrack it.

## [0.13.0 synapsidian] — 2026-10-14

### Added

- Setup requires Git and Excalidraw (installed through the Obsidian CLI, or a task with the steps); health reports stuck tasks; Importer is recommended.

## [0.12.0 synapsidian] — 2026-10-14

### Changed

- Split into two plugins: synapsidian (the core) and synapsidian-work (the work add-on).

## [0.1.0 synapsidian-work] — 2026-10-14

### Added

- First release: the work add-on split out of the core.
