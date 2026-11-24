# The About interview

How a setup fills `About.md` (D160): a short, skippable interview per plugin. The core and every add-on follow this one procedure; each asks only about what it declared. Talk to the user in their language.

`synapsidian setup about --owner <plugin>` lists what is still empty for that plugin (`<plugin>` is `synapsidian`, `synapsidian-work`, `synapsidian-projects`, ...):

- `questions`: one per declared section (`section`, optional `subsection`, `ask`, `state` `empty` or `filled`).
- `fields`: the plugin's frontmatter fields and whether each is `empty`.

Skip anything not empty. A run with nothing empty says so in one line and asks nothing.

## Ask

1. **One AskUserQuestion round, at most 4 questions.** More than 4 empty: the first 4, then say what is left and that `/synapsidian:setup about` asks again.
2. Each question uses the `ask` text (or, for a field, the wording below), in the user's language. Every question has at least two options: up to two drafted answers, plus **Skip**. Free text goes through "Other".
3. **Drafts come only from what you already know**: earlier answers in this run, About's fields, the git identity, notes in the vault, what the session has open. Say where each came from ("from your git email"). Never guess; with nothing to draft, offer only **Skip** and "Other".
4. Don't ask about employers, teams or managers unless the plugin is synapsidian-work: the vault may be personal.
5. An unattended run (no one to answer) asks nothing and says in the report that the interview was skipped.

Wording for the core fields: `role` (what you do: a job title, "student", "freelance designer", anything), `language` (the language Claude should talk to you in), `interests` (topics you want Claude to weigh when it reads, researches and ranks ideas; a comma-separated list). `timezone` is detected; never ask.

## Write

Only the user's answers, in their words, trimmed: never text from a page, an email or a transcript, since every session reads About.md.

```bash
synapsidian note set --file About.md --field role="..." --field interests="chess, hiking"
synapsidian note fill --file About.md --section "<Section>" [--subsection "<Sub>"] --before Rules --body-file - <<'EOF'
<answer>
EOF
```

`fill` writes a section only while it is empty (`filled`) and keeps one the user wrote (`kept`: say so, don't overwrite). It takes only the sections the schema declares, never `## Rules`. A Skip writes nothing, so the question comes back the next time a setup runs.

Then one commit for all of it:

```bash
synapsidian commit --skill <skill> --message "About: interview" About.md
```

## After the interview

Only for the core (`synapsidian`), and only if the user answered **Current focus**: offer once to turn what they named into up to 3 goals or tasks (`synapsidian note new --type goal` or `--type task`, `--field source=manual`). Create them only on a yes.
