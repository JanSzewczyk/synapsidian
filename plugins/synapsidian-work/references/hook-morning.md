# synapsidian-work: morning steps (added to synapsidian's morning run)

**First:** `synapsidian note where` must list `synapsidian-work` under `extensions`. Without it the vault has no `email` or `slack` task sources and no `1-1`, `standup` or `retro` meetings, so a note synapsidian-work writes would be refused. Skip every step below and say in one line of the report that `/synapsidian-work:setup` hasn't been run in this vault.

**After step 1, before gathering tasks:** invoke the skill `synapsidian-work:work-brief` with the argument `morning` and wait for its reply. It reads pull requests, Jira, email and Slack, files new email and Slack asks as tasks (pull requests are only listed, never filed), and makes no commit. Gather tasks only after it, so the tasks it filed show up.

Its reply has four parts. Place them in the `brief` block:

- **Needs attention** lines: after the tasks due today, before meeting prep.
- **Done** lines (merged pull requests): after the closed tasks.
- `**Pull requests**` and `**Jira**` sections: between Done and Coming up, as given.
- **Files** it touched: add them to the morning commit.

One item, one place: a task beats the email, Slack message or PR nudge about the same thing; drop the duplicate.

If the skill isn't available or fails, carry on without it and say so in one line of the report.
