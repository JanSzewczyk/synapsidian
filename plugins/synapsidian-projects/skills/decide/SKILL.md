---
name: decide
description: Record an architecture or project decision (synapsidian-projects add-on) as a MADR note in the project's Decisions/ folder, numbered per project, drafted as proposed and accepted only after review; also accepts, rejects, deprecates or supersedes one. Use when the user decides something about a project ("record this decision", "zapisz decyzję", "ADR for switching to X", "supersede decision 4"). Smaller decisions found while saving are /synapsidian:save's.
allowed-tools: Bash(synapsidian *) Bash(synapsidian-projects *) Read Grep Glob
argument-hint: "<what was decided> [project <name>] | accept|reject|deprecate <decision> | supersede <decision> with <what>"
---

# Decide

Request: $ARGUMENTS

Run `synapsidian ref conventions` and follow it: notes in English, search before creating, one commit per run. Talk to the user in their language.

`synapsidian note where` must list `synapsidian-projects` under `extensions`; if it doesn't, send the user to `/synapsidian-projects:setup` and stop.

Decision fields (from the schema): `status` proposed | accepted | rejected | deprecated | superseded · `number`, the decision's number within its project · `project` · `supersedes` and `superseded_by`, links between a decision and the one that replaced it · `decided_by`, the people who decided, as links to their notes.

**Rules (D100, D107):**
- **An accepted decision is never rewritten.** To change it, record a new decision that supersedes it. In the old note only `status` and `superseded_by` change. Fixing a typo is fine; changing what it says is not.
- **Nothing is accepted unreviewed.** A draft is `proposed` until the user accepts it in this conversation. An unattended run, with no one to ask, leaves it `proposed` and says so.
- **No invented references.** Cite only notes that exist (search first) and sources the user gave or the vault keeps. No made-up benchmarks, numbers, quotes or URLs. Unknown is `TBD`. Every quote or figure taken from a source note is checked first with `synapsidian source quote-check --file "<source rel>" "<the words>"`; one that isn't found doesn't go in.

## Record a decision

1. **Project.** Use the one named, or the one the conversation is about. Resolve it with `synapsidian find --type project "<name>"`. If the vault has no fitting project, ask. A decision that belongs to no project is recorded the same way, but without `project` and `number`.
2. **Earlier decisions.** Run `synapsidian find --type decision "<topic>"` with one or two phrasings. Does an accepted decision already answer the same question? Then this one supersedes it: tell the user, and use **Supersede**.
3. **Number:**
   ```bash
   synapsidian query notes --type decision --all --limit 100000 | synapsidian-projects decision-number --project "<project title>"
   ```
4. **Create** the note as `proposed`:
   ```bash
   synapsidian note new --type decision --title "<the decision, short: Use SQLite for local storage>" \
     --field project="<project title>" --field number=<n> --field status=proposed \
     --field summary="<one sentence: what was decided and the main reason>" \
     [--field decided_by="<Person>,<Person>"] [--field supersedes="<old decision title>"]
   ```
   `decided_by` lists only people who have a note, and not the user.
5. **Write the body** with Edit, in the template's sections (MADR 4):
   - **Context**: the problem in a few sentences, and why it needs a decision now. Then the decision drivers as bullets: the forces and requirements that decide between the options.
   - **Options considered**: at least two real ones; "keep things as they are" counts when it is a real option. One `### <option>` per option, with `- Good:` and `- Bad:` bullets measured against the drivers.
   - **Decision**: `Chosen: **<option>**, because <reason, tied to the drivers>.`
   - **Consequences**: `- Good:` and `- Bad:` bullets, the follow-up work (link the tasks once they exist), and how to tell the decision is being followed when that can be checked.
   - Links to the research, tasks, sources or meetings it rests on go where they are used.
6. **Review.** Show the user the summary, the chosen option and the main trade-off, and ask: accept, change something, or keep it proposed. Make the changes they ask for in the draft; it isn't accepted yet, so it may still change.
7. **Accept**, on the user's yes, with the steps under **Accept** below.
8. Commit (Finish).

## Accept, reject, deprecate

Find the decision by number or topic: `synapsidian find --type decision "<number or words>"`, then read it.

- **Accept** (only `proposed`): `synapsidian note set --file "<rel>" --field status=accepted`. Then, with Edit in the hub:
  - add a line to `## Key decisions`: `- [[<decision>]] (#<number>): <summary>`;
  - add a Log line: `- YYYY-MM-DD: decided [[<decision>]]`.
- **Reject** (only `proposed`, when the team chose not to do it): `--field status=rejected`. The note stays as the record of why not, and the hub gets a Log line.
- **Deprecate** (only `accepted`, when it no longer applies and nothing replaces it): `--field status=deprecated`. Add ` (deprecated YYYY-MM-DD)` to its Key decisions line, plus a Log line.

## Supersede

1. Record the new decision (steps 1-6 above) with `--field supersedes="<old decision title>"`. Its Context says what changed since the old one.
2. When it is accepted, apply **Accept** to the new decision, then update the old one:
   ```bash
   synapsidian note set --file "<old rel>" --field status=superseded --field superseded_by="<new decision title>"
   ```
   Leave the old note's body alone. In the hub, append ` (superseded by [[<new decision>]])` to the old decision's Key decisions line.

## Finish

One commit of every note this run touched: the decision, the hub, and a superseded decision:

```bash
synapsidian commit --skill synapsidian-projects-decide --message "<proposed|accepted|...> #<n> <title>" "<rel>" ...
```

Tell the user: the decision as a `[[link]]` with its number and status, what it supersedes, and what's left. That can be follow-up tasks to create with `/synapsidian:task`, or `proposed` waiting for their review.
