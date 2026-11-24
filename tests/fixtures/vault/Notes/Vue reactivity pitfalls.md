---
type: note
created: '2026-10-01'
area: tech
summary: Mistakes that silently break reactivity in Vue 3, such as destructuring props
---
## Details
Destructuring a reactive object loses tracking; use toRefs. Watching a getter vs a ref.
