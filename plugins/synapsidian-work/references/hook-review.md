# synapsidian-work: review steps (added to synapsidian's review)

Wins are the user's brag log for performance reviews (`type: win`, in `Wins/`, logged with `/synapsidian-work:win`).

**Step 3, gather the period:** also list the wins dated in it, as below.

**Step 4, the review note:** when there is at least one win, add a `## Wins` section after Done (`synapsidian note fill --file "<review note>" --section Wins --before Decisions`), one line per win as below. A month or quarter review lists every win of the period, not only those its week reviews named: this is what the user reads before a performance review. No wins: no section, and nothing about it in the reply.

## Listing wins

Also used by `/synapsidian-work:one-to-one` for the wins since the previous 1:1.

```bash
synapsidian query notes --type win --where "date>=<start>" --where "date<=<end>"
```

One line per win, newest first: `- [[<note title>]] (<impact>): <summary>`, with `large` ones first in a month or quarter list. Only what the notes say: never add a win, an impact or a number of your own.
