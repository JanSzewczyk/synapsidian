## Goal


## Exit criteria


## Tasks

```base
filters:
  and:
    - note.type == "task"
    - note.milestone == this
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
      - blocked_by
```

## Flow
<!-- @generated:flow -->
<!-- @end -->

## Log
