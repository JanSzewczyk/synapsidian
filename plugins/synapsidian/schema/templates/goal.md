## Why it matters


## Success criteria


## Milestones


## Progress log


## Linked work

```base
filters:
  and:
    - not:
        - file.inFolder("Archive")
    - or:
        - note.goal == this
        - file.hasLink(this.file)
views:
  - type: table
    name: Tasks
    filters:
      and:
        - note.type == "task"
    order:
      - file.name
      - status
      - due
    groupBy:
      property: status
      direction: ASC
  - type: table
    name: Notes and ideas
    filters:
      and:
        - note.type != "task"
        - note.type != "daily"
    order:
      - file.name
      - type
      - summary
```
