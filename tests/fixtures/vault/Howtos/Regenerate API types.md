---
type: howto
created: '2026-10-01'
summary: Rebuild the TypeScript client after the backend OpenAPI schema changes
---
## Steps
1. `pnpm openapi:pull`
2. `pnpm openapi:generate`
3. Fix type errors.
