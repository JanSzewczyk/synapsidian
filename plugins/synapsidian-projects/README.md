# synapsidian-projects

The projects add-on for the `synapsidian` plugin. Any number of projects in the vault, each a hub note with its own kanban board of tasks, and the project's milestones, tasks, decisions, specs, changes, bug investigations, postmortems, architecture notes, research, workflows, notes, thinking and mind maps filed under its own folder. Code repositories are only ever read.

## Requirements

- [Claude Code](https://claude.com/claude-code); not claude.ai or Cowork, because the plugin ships a `bin/` command they refuse
- The `synapsidian` plugin, set up with `/synapsidian:setup` (installing synapsidian-projects installs `synapsidian` too if it's missing)
- Two more Obsidian community plugins, which `/synapsidian-projects:setup` installs or reports:
  - **Folder notes**: a click on a project's folder opens its hub
  - **Excalidraw Extras**: turns Mermaid (a roadmap or a flow) into an editable Excalidraw drawing

## Install

```
/plugin install synapsidian-projects@synapsidian
/synapsidian-projects:setup
```

Setup installs the schema extension into the vault (`.synapsidian/extensions/synapsidian-projects/`), which adds the `project` type, the Projects Bases and a `## Projects` section in `About.md` that setup asks you about (skippable). It moves existing project notes into their project folders and gives every hub its board and views. It also shows where each project's repository is on this device. It ends with a report of what is ready, what it added and what is still needed. Re-run it after every synapsidian-projects update.

## Skills

| Skill | What it does |
|---|---|
| **setup** | `/synapsidian-projects:setup [check]`: install or update the schema extension, move existing project notes into their project folders (and architecture notes from synapsidian-work before 0.3.0 into their projects), switch the vault's Bases to type filters, give every project note its board and project-notes views; show where each project's repository is on this device and offer to switch local paths to remote URLs |
| **architect** | `/synapsidian-projects:architect <project> [app]`: architecture notes for a project's code, any language (a Vue app also gets domains, stores and routes): an overview per app and a note per large module, from a read-only scan of the hub's `repo`; refreshes only what changed and never overwrites hand edits inside generated sections |
| **project** | `/synapsidian-projects:project`: create, refresh or list projects: a hub with goal, links, status, roadmap, key decisions, risks and open questions, and optionally the people involved and the goals it serves; for a code repository, read it (read only) into the hub's Repository section and log what changed since the last read. A hub's `repo` is a remote URL, which each device resolves to its own clone, or a local path for a repository kept on one device; a clone older than the last read never overwrites it. `status` reports what closed since the last status, what is in progress or blocked and each milestone's progress and days to target, and proposes a new Status text it writes only on your yes; `close` asks what to do with each open task, milestone and change, writes a retro (went well, didn't, lessons) into the hub and marks it done |
| **decide** | `/synapsidian-projects:decide`: record a decision in the project (MADR: drivers, options with trade-offs, consequences), numbered per project, proposed until you accept it; accept, reject, deprecate or supersede one |
| **milestone** | `/synapsidian-projects:milestone`: split a project into stages: a milestone with goal, exit criteria, start and target date and a board of its tasks; planned, active, done or dropped, with progress counted from its tasks. The hub's Roadmap draws the milestones as a gantt chart and the tasks that wait on others as a flowchart (Mermaid), and each milestone and change gets a diagram of its tasks in order |
| **map** | `/synapsidian-projects:map`: draw or refresh the project's Excalidraw mind map: hub, open milestones, open tasks, decisions, specs, changes, open bugs, draft postmortems, open questions, notes coloured by status; a refresh keeps what you moved or drew and puts new nodes where they cover nothing |
| **spec** | `/synapsidian-projects:spec`: write or update a living spec of part of a project: purpose, scope, numbered requirements, design |
| **change** | `/synapsidian-projects:change`: track a change from proposed to done or dropped, with its specs, decisions and tasks; closing logs it on the hub |
| **debug** | `/synapsidian-projects:debug`: keep a bug investigation: symptom, repro, what was tried, root cause, fix; closed as fixed or wontfix with a line on the hub |
| **incident** | `/synapsidian-projects:incident`: write a blameless postmortem: summary, timeline, impact, root cause, what went well, action items filed as tasks; draft until you make it final |

Tasks in a project are `/synapsidian:task` with the project; the weekly `/synapsidian:review` adds a line per active project.

## Where notes go

A project's hub is `Projects/<Project>/<Project>.md`. Its notes sit beside it in `Tasks/`, `Milestones/`, `Decisions/`, `Specs/`, `Changes/`, `Debug/`, `Incidents/`, `Architecture/`, `Research/`, `Workflows/`, `Notes/`, `Thinking/` and `Maps/`. Setting `project` on a note later moves it there; names don't change, so links keep working. Dragging a card on a project's board changes the task's status.
