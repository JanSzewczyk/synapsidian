# think: ideas

Review the ideas waiting in `Ideas/` and decide what to do with each.

1. List open ideas: `synapsidian query notes --type idea --where "status!=graduated" --where "status!=dropped"`. Read each (they are short).
2. For each, check the vault for what changed since it was written (a related project, a decision, research that answers it).
3. **Rank** by value to the user's current focus (`About.md`, active projects) against effort, one line each: `[[idea]]` · value · effort · why.
4. **Graduate next**: the one or two worth turning into work now; offer `/synapsidian:think graduate <idea>`.
5. **Drop or park**: ideas overtaken by events or not worth it. Set `status=dropped` only when the user agrees; set `status=exploring` on the ones the user wants to keep thinking about.
6. Write a `thinking` note with `kind=ideas` and answer with the ranking.
