# think: patterns

Recurring themes over a period: what keeps coming up in the user's work, for better or worse.

1. **Period**: from the argument (`last month`, `Q3`, `since 2026-09-01`); default the last 30 days. Resolve to dates.
2. **Read the period**: daily notes' devlog blocks (`synapsidian query notes --type daily --where "date>=<start>"`), reviews, meetings, decisions, tasks created and closed, and `synapsidian query commits --since-skill ...` for what the vault changed. For long periods, give each month to an Explore subagent that returns themes with evidence; you merge.
3. **Patterns**: 3-7 themes that recur at least three times, each with the evidence (dated `[[links]]`) and whether it is helping or hurting: repeated blockers, the same bug class, meetings that keep producing the same action item, tasks that slip, topics the user keeps returning to, decisions revisited.
4. **Suggestions**: for each harmful pattern, one concrete change (a task, a how-to, a rule, a conversation to have). Don't create the tasks; offer them.
5. Write a `thinking` note with `kind=patterns` and answer with the patterns in a few lines.

The Friday review already lists patterns for its week (D19); this mode is for longer spans or a specific question ("why do my estimates slip?").
