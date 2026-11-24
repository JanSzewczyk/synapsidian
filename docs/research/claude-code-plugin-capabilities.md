# Claude Code plugin capabilities (as of 2026-10-12)

Condensed from the official docs. Source index: https://code.claude.com/docs/llms.txt

## Layout and manifest
- `.claude-plugin/plugin.json` (only `name` required). Components at plugin root: `skills/<name>/SKILL.md`, `commands/*.md` (legacy, docs say prefer skills), `agents/*.md`, `hooks/hooks.json`, `.mcp.json`, `output-styles/`, `workflows/*.js`, `monitors/monitors.json` (experimental), `bin/` (on Bash PATH while enabled), `settings.json` (only `agent`, `subagentStatusLine` honoured), `scripts/`.
- A `CLAUDE.md` at the plugin root is **not** loaded. Instructions go into skills.
- Validate with `claude plugin validate <dir> --strict`.
- Docs: https://code.claude.com/docs/en/plugins/manifest-reference.md

## userConfig
- Per key: `type` (string|number|boolean|directory|file), `title`, `description`, `required`, `default`, `options`, `multiple`, `sensitive`, `min`/`max`.
- Prompted on enable; editable in `/config`. Sensitive values go to the OS keychain.
- Exposed as `${user_config.KEY}` (MCP/LSP config, exec-form hook `args`, skill and agent bodies) and as env `CLAUDE_PLUGIN_OPTION_<KEY>` in hook processes. Not in shell-form hooks.
- Fits: vault path (`type: directory`), API keys (`sensitive: true`).

## Paths
- `${CLAUDE_PLUGIN_ROOT}`: install dir, changes on every version. Never store state there.
- `${CLAUDE_PLUGIN_DATA}`: `~/.claude/plugins/data/<id>/`, survives updates. Use for indexes, caches, venvs.
- Neither is set inside the Bash tool environment; they are substituted in skill/agent Markdown and hook/MCP config.

## Skills
- Frontmatter: `name`, `description`, `when_to_use` (desc + when_to_use capped at 1,536 chars), `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context: fork` + `agent` + `background`, `hooks`, `paths`, `shell`.
- `` !`cmd` `` / ```! blocks inject command output before the prompt is sent (failure aborts; use `|| true`).
- Keep SKILL.md < 500 lines; link reference files loaded on demand.
- Plugin skills are invoked as `/<plugin>:<skill>`.
- Docs: https://code.claude.com/docs/en/skills.md

## Subagents
- `agents/*.md` frontmatter: `name`, `description`, `tools`, `disallowedTools`, `model`, `maxTurns`, `skills`, `memory`, `background`, `omitClaudeMd`, `effort`, `isolation: worktree`, `color`.
- Plugin agents ignore `hooks`, `mcpServers`, `permissionMode`, `initialPrompt`.
- Docs: https://code.claude.com/docs/en/sub-agents.md

## Hooks
- 33 events incl. SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PostToolBatch, Stop, SubagentStop, PreCompact, PostCompact, SessionEnd, FileChanged, CwdChanged, InstructionsLoaded.
- Handler types: `command`, `http`, `mcp_tool`, `prompt`, `agent` (experimental).
- `additionalContext` (max 10,000 chars) on SessionStart, UserPromptSubmit, PostToolUse, Stop, etc. Write it as facts, not imperatives.
- Command hooks: exec form `args`, `async`, `asyncRewake`, `onFailure`. `if` filter on tool events.
- Docs: https://code.claude.com/docs/en/hooks.md

## Scheduling and headless
- `/loop`: in-session only, expires after 7 days.
- Cloud routines (`/schedule`): run on a fresh clone in the cloud, **cannot read a local vault** unless the vault is a GitHub repo.
- Desktop scheduled tasks: run locally with file access. Best fit for a nightly/morning vault job.
- `claude -p "/plugin:skill ..."` expands plugin skills headlessly; use `--permission-prompts none` for unattended runs.

## Memory
- Auto memory: `~/.claude/projects/<project>/memory/MEMORY.md` (first 200 lines / 25KB). `autoMemoryDirectory` can redirect it.
- Don't duplicate vault content into auto memory; inject a small vault index via SessionStart `additionalContext` or a skill `!` block instead.
- Docs: https://code.claude.com/docs/en/memory.md

## Development loop
- `claude --plugin-dir ./synapsidian` loads in place; `/reload-plugins` after edits.
- Or a local marketplace (`claude plugin marketplace add <path>`): relative-path plugins load in place.
