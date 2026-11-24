# synapsidian-projects: review steps (added to synapsidian's review)

Printed by `synapsidian-projects hook review` for `/synapsidian:review` (D151). The review runs unattended: these steps only read the projects and write the review note. They never ask, and never edit a hub.

**Step 3, gather the period:** for each project the review lists as active (`synapsidian query notes --type project --where status=active`), count the period:

```bash
synapsidian query notes --limit 100000 \
  | synapsidian-projects progress --project "<project title>" --since <period_start> --until <period_end> --today <period_end>
```

A month or quarter review counts its own period this way, rather than adding up its week reviews.

**Step 4, the review note:** when there is at least one active project, add a `## Projects` section before Open threads:

```bash
synapsidian note fill --file "<review note>" --section Projects --before "Open threads" <<'EOF'
- <summary line of the first project>
- ...
EOF
```

- One bullet per active project: the JSON's `summary` as printed (`[[Project]]: what closed; in progress, blocked; next milestone done/total and its days to target`). Busiest first: most closed, then most in progress.
- Under a project's bullet, indented, only what needs the user: a milestone past its target (`days_to_target` below 0), a blocked task whose blockers are none of them in progress, and, for a project with nothing closed and nothing in progress in the period, "quiet all period: still active, or pause it?". The review only lists these; the user decides.
- Where a hub's Status looks out of date against these facts, say so in the bullet and point to `/synapsidian-projects:project status <project>`; don't rewrite it.
- Only what `progress` returned: never add a count, a date or a judgment of your own.

No active projects: no section, and nothing about projects in the reply.
