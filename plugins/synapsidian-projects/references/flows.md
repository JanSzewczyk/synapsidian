# Order-of-work diagrams

Shared by `/synapsidian-projects:project`, `/synapsidian-projects:milestone` and `/synapsidian-projects:change` (D146). `synapsidian-projects flow` turns the vault's notes into Mermaid diagrams, which Obsidian renders in the note; each lives in a hashed generated block. They show the notes as they were at the last run: a task closed or moved since then shows up on the next refresh by one of these skills, not before.

The order comes from the tasks' `blocked_by`, which the core has from synapsidian 0.31.0. If `synapsidian note set --field blocked_by=...` is refused as an unknown field, the synapsidian plugin is older: tell the user to update it (`/plugin`), and draw without it.

## The hub's roadmap

A gantt chart of the project's milestones (start, or the day the note was made, to target) and a flowchart of the open tasks that wait on another open task and the open tasks they wait on, grouped by milestone.

```bash
synapsidian query notes --limit 100000 | synapsidian-projects flow --project "<project title>"
synapsidian query notes --limit 100000 | synapsidian-projects flow --project "<project title>" --markdown \
  | synapsidian block set --file "<hub rel>" --name roadmap --section Roadmap --before "Key decisions" --hash
```

## A milestone's or a change's flow

Its tasks, the tasks they wait on, and an arrow from each blocker to the task that waits on it. Every task is a link to its note, styled by status.

```bash
synapsidian query notes --limit 100000 | synapsidian-projects flow --project "<project title>" --milestone "<milestone title>"
synapsidian query notes --limit 100000 | synapsidian-projects flow --project "<project title>" --milestone "<milestone title>" --markdown \
  | synapsidian block set --file "<milestone rel>" --name flow --section Flow --before Log --hash
```

For a change, `--change "<change title>"` instead of `--milestone`, written to the change note the same way.

## Reading the result

The JSON run comes first; it is what you report:
- `cycles`: tasks waiting on each other, so none of them can start. The diagram marks them too. Name them to the user and ask which dependency to drop; change it with `synapsidian note set --field blocked_by=...` as `/synapsidian:task` does. Never pick one yourself.
- `undated` (roadmap): milestones without a `target`, left out of the chart and listed under it.
- `tasks` and `edges`: how much the diagram shows, for the report.

`block set` exiting 4 (`edited by hand`) means the user changed the diagram. Leave it, say so, and overwrite with `--force` only if the user says so; an unattended run leaves it and reports. Include the note in the run's commit only when the block changed.
