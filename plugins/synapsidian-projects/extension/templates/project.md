## Board

```base
filters:
  and:
    - note.type == "task"
    - note.project == this
views:
  - type: kanban
    name: Board
    filters:
      and:
        - note.status != "dropped"
    groupBy:
      property: status
      direction: ASC
    groupOrder:
      - todo
      - doing
      - waiting
      - done
    order:
      - file.name
      - priority
      - due
      - milestone
      - blocked_by
```

## Goal


## Links

- Docs:
- Tracker:
- Other:

## Status


## Roadmap
<!-- @generated:roadmap -->
<!-- @end -->

## Key decisions


## Risks
<!-- One bullet per risk: what could go wrong · likelihood / impact (low, medium, high) · mitigation -->

## Open questions


## Project notes

```base
filters:
  and:
    - note.project == this
    - note.type != "task"
views:
  - type: table
    name: Milestones
    filters:
      and:
        - note.type == "milestone"
    order:
      - file.name
      - status
      - start
      - target
      - summary
    sort:
      - property: target
        direction: ASC
  - type: table
    name: Decisions
    filters:
      and:
        - note.type == "decision"
    order:
      - number
      - file.name
      - status
      - summary
    sort:
      - property: file.name
        direction: DESC
  - type: table
    name: Specs
    filters:
      and:
        - note.type == "spec"
    order:
      - file.name
      - status
      - summary
  - type: table
    name: Changes
    filters:
      and:
        - note.type == "change"
    order:
      - file.name
      - status
      - done_on
      - summary
    sort:
      - property: file.name
        direction: DESC
  - type: table
    name: Debug
    filters:
      and:
        - note.type == "debug"
    order:
      - file.name
      - status
      - summary
    sort:
      - property: file.name
        direction: DESC
  - type: table
    name: Incidents
    filters:
      and:
        - note.type == "incident"
    order:
      - file.name
      - status
      - date
      - summary
    sort:
      - property: file.name
        direction: DESC
  - type: table
    name: Architecture
    filters:
      and:
        - note.type == "architecture"
    order:
      - file.name
      - app
      - kind
      - summary
      - scanned_at
  - type: table
    name: Research
    filters:
      and:
        - note.type == "research"
    order:
      - file.name
      - summary
  - type: table
    name: Workflows and notes
    filters:
      or:
        - note.type == "howto"
        - note.type == "note"
    order:
      - file.name
      - note.type
      - summary
  - type: table
    name: Thinking
    filters:
      and:
        - note.type == "thinking"
    order:
      - file.name
      - kind
      - summary
```

## Log
