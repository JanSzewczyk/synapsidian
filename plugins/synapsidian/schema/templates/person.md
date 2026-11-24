## Context


## What they care about


## How we help each other


## Open topics


## History


## Meetings and tasks

```base
filters:
  and:
    - not:
        - file.inFolder("Archive")
    - or:
        - note.attendees.contains(this)
        - file.hasLink(this.file)
views:
  - type: table
    name: Meetings
    filters:
      and:
        - note.type == "meeting"
    order:
      - file.name
      - kind
    sort:
      - property: date
        direction: DESC
  - type: table
    name: Open tasks
    filters:
      and:
        - note.type == "task"
        - note.status != "done"
        - note.status != "dropped"
    order:
      - file.name
      - status
      - due
```
