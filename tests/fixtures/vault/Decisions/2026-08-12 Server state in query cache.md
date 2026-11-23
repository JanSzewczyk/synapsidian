---
type: decision
created: '2026-10-01'
status: accepted
summary: Keep API data in the query library cache instead of Pinia stores to avoid
  stale duplicates
---
## Context
Two sources of truth drifted after mutations.

## Decision
Pinia only for UI state.
