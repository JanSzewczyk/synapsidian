---
type: note
created: '2026-10-01'
area: tech
summary: Every API query is scoped by organisation so one customer never sees another's
  salaries
---
## Details
Middleware adds the organisation filter; tests assert cross-tenant requests return 404.
