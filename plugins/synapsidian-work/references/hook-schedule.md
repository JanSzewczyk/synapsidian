# synapsidian-work: scheduled runs (added to synapsidian's schedule skill)

synapsidian-work has one run, the stand-up note. Its time comes from synapsidian-work's options, which only synapsidian-work's own skills can read, so don't create or fix it yourself: tell the user to run `/synapsidian-work:setup schedule`, or invoke the skill `synapsidian-work:setup` with the argument `schedule` when the user already agreed to scheduling in this conversation.

For `check`, list a task with id `synapsidian-standup` in your table like the others (exists, enabled, last run) without judging its cron, and note that its prompt must be `/synapsidian-work:standup` (an older install used `/synapsidian:standup`, which no longer exists).
