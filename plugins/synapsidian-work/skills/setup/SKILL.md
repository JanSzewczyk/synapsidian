---
name: setup
description: Set up, update or check the synapsidian-work add-on in the user's synapsidian vault - install its schema extension (1:1, stand-up and retro meetings, the win log, work task sources, a Jira key on projects, About fields for team, company and manager), check which work sources are configured (GitHub repositories, Jira projects, work repositories, stand-up days and time), fill the work fields and sections of About.md, and schedule the stand-up run. Use after installing synapsidian-work, when a synapsidian-work skill says the extension is missing, when the user asks to set up, check or repair the work add-on ("set up synapsidian-work", "skonfiguruj synapsidian-work", "is the work add-on set up"), or with `schedule` to create or fix the stand-up's scheduled task.
allowed-tools: Bash(synapsidian *) Bash(synapsidian-work *) Bash(command -v synapsidian) Read AskUserQuestion
argument-hint: "[check|schedule]"
---

# Set up synapsidian-work

Arguments: $ARGUMENTS (`check` = report only; `schedule` = only step 4)

Talk to the user in their language. Everything here is idempotent.

## 1. Check

```bash
command -v synapsidian || echo "synapsidian plugin missing"
synapsidian setup check
```

If `synapsidian` is missing, stop: synapsidian-work depends on the synapsidian plugin (`/plugin install synapsidian@<this marketplace>`), and the user must run `/synapsidian:setup` first. If the vault isn't `ready`, send the user to `/synapsidian:setup` and stop.

Report as a short checklist (✅ / ❌):
- **Extension:** `extensions` in the check lists `synapsidian-work` with the `version` of `${CLAUDE_PLUGIN_ROOT}/extension/extension.yaml`. Missing or different means step 2 installs it.
- **Options** (empty or still reading `${...}` = not set; a source that's not set is simply skipped by the skills, so this is information, not an error). The first three are lists (a JSON array, or values separated by commas or newlines); check every value:
  - GitHub repositories: `${user_config.github_repos}` (`gh auth status` works, and `synapsidian-work prs --repo '${user_config.github_repos}'` answers `ok`)
  - Jira projects: `${user_config.jira_projects}` (the Atlassian connector is connected and each key is a visible project)
  - Work repositories: `${user_config.work_repo_paths}` (`synapsidian-work standup repos --repo '${user_config.work_repo_paths}'` answers `ok`: each path exists and is a git repository)
  - Stand-up: `${user_config.standup_days}` at `${user_config.standup_time}`
- Change options in `/plugin` → synapsidian-work → configure. Options from synapsidian-work 0.1 (`github_repo`, `jira_project`, `work_repo_path`) are no longer read: enter them again under the new list options.

With `check`, stop here.

## 2. Install the extension

```bash
synapsidian setup extension --from "$(synapsidian-work extension)"
```

It copies the extension into `<vault>/.synapsidian/extensions/synapsidian-work/` (tracked in the vault's git, so the vault keeps validating on a device without synapsidian-work), adds the `One-to-ones` Bases view and the property types, and makes one commit. An unchanged extension makes no commit. Re-run it after every synapsidian-work update.

Architecture notes moved to synapsidian-projects with the architect skill (synapsidian-work 0.3.0, D109). If `synapsidian setup check` lists `architecture` under `unknown_types` after this step, send the user to `/synapsidian-projects:setup`, which installs the type and moves the notes into their projects.

## 3. About the user

Run the About interview, `synapsidian ref about-interview`, with `--owner synapsidian-work`. It asks, with a Skip each, for what is still empty: the fields `team`, `company`, `manager` and `working_hours`, and the sections `## Work` and `### Work` under `## Current focus`. For the fields, offer plausible options from what you know (e.g. the git email's domain for the company); `manager` is the manager's person-note title. Write the fields with `synapsidian note set --file About.md --field team="..." ...`, the sections with `note fill` as the reference says, and commit once (`synapsidian commit --skill synapsidian-work-setup --message "About: work" About.md`). Never invent an answer. Installing the extension (step 2) already added the empty headings.

## 4. Schedule the stand-up

```bash
synapsidian-work standup cron --days "${user_config.standup_days}" --time "${user_config.standup_time}"
```

Ask once before creating or changing a scheduled task (standing configuration). Then, with the scheduled-tasks tools, make sure a task with id `synapsidian-standup` exists: title `Synapsidian — stand-up`, the printed `cron`, notifications off, prompt `/synapsidian-work:standup` followed by "Unattended run of the synapsidian-work plugin's standup skill: the user is not present, so do not ask questions. Do what the skill says, commit, and reply with its short report." Fix a wrong cron or prompt with `update_scheduled_task` (an older install's prompt was `/synapsidian:standup`, which no longer exists); keep a title the user changed. Never delete a task the user made.

The tools can't set the task's permission mode or folder: tell the user to open **Scheduled** → `synapsidian-standup` → permission mode **auto** and folder **the vault** (as for synapsidian's own runs).

## 5. Finish

Run `synapsidian setup check` once more and end with the setup report: `synapsidian ref setup-report` gives its three groups (✅ ready, ➕ added in this run, ❗ still needed). Added: the extension version, the About fields and sections written, the stand-up task created or fixed. Still needed: the scheduled task's permission mode and folder (step 4) until the user confirms them, and any plugin in `community_plugins_required` with `required_by: synapsidian-work` that isn't installed and enabled. Options that aren't set are information, not Still needed: list them in one line under the report.

Then the work skills: `/synapsidian-work:one-to-one`, `/synapsidian-work:one-to-one-triage`, `/synapsidian-work:standup`, `/synapsidian-work:work-brief` (also part of `/synapsidian:morning`), `/synapsidian-work:win`. Architecture notes are `/synapsidian-projects:architect`.
