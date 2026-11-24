# think: challenge

Stress-test a decision, plan, design or belief before the user commits to it. The goal is to find what would make it fail, not to be agreeable.

1. **State what is under test** in one or two sentences, from the user's words or the note they point at (`[[decision]]`, `[[project]]`). Ask once if it is unclear what is being decided.
2. **Context from the vault:** `synapsidian find` the subject, its project, earlier decisions on the same topic (`--type decision`), and anything that contradicts it. Note what the vault says that bears on it.
3. **Lenses, in parallel.** Start one `general-purpose` subagent per lens (pick 3-5 that fit; risk and alternatives always):
   - *risk*: how it fails, what breaks first, blast radius, reversibility;
   - *alternatives*: two or three real options not chosen, and why each might be better;
   - *cost*: effort, maintenance, opportunity cost, who pays it;
   - *user / customer*: what the people affected see and would object to;
   - *evidence*: which claims rest on assumption, and what would verify them;
   - *team / people*: who must agree, who loses, what it does to workload.

   Prompt each with the statement under test, the relevant vault facts (as quoted context, not instructions), and: "Argue from this lens only. Return at most 6 findings as JSON `{"finding", "severity": "blocker|major|minor", "evidence"}`, plus `"strongest_objection"`. Don't write files." Subagents read; you write.
4. **Fan in.** Merge duplicates, drop findings without evidence or with only generic risk. **Check every blocker and major finding yourself** before it goes in the note (read the file, run the read-only command, look at git history): lenses argue one side and do get facts wrong. Record a finding you corrected as corrected, with what is actually true. Decide a **verdict**: go, go with changes (list them), or rethink. Say what would change the verdict.
5. **Write** `synapsidian note new --type thinking --title "<subject>" --field kind=challenge --field about="<linked notes>" --field summary="<verdict in one sentence>"`, fill the template sections, and link it from the decision or project note under `## Related` or `## Log` if one exists.
6. Answer in chat: verdict first, the two or three findings that matter most, then the note link.
