#!/bin/sh
# SessionEnd: queue a trace of the finished session for the evening run.
#
# Deliberately does no thinking and starts nothing slow: Claude Code kills SessionEnd
# hooks as it exits, so no uv, no Python environment, no model. The evening run
# (`sessions.py`) reads the queue and the transcripts later.
#
# Queue: <vault>/.git/synapsidian/session-queue.jsonl, one JSON row per ended session.

input=$(cat)
[ -n "$input" ] || exit 0

# Same order as synapsidianlib/config.py: the option Claude Code passes, SYNAPSIDIAN_VAULT, then the saved option.
vault="${CLAUDE_PLUGIN_OPTION_VAULT_PATH:-${SYNAPSIDIAN_VAULT:-}}"
case "$vault" in '${user_config'*) vault="" ;; esac  # a placeholder Claude Code didn't fill
if [ -z "$vault" ] && command -v jq >/dev/null 2>&1; then
  settings="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json"
  vault=$(jq -r '[.pluginConfigs // {} | to_entries[] | select(.key | startswith("synapsidian@")) | .value.options.vault_path // empty][0] // empty' "$settings" 2>/dev/null)
fi
# `~`, `$HOME` and `${HOME}` as config.py expands them; other variables are left alone (no eval).
case "$vault" in
  "~"*) vault="$HOME${vault#\~}" ;;
  '${HOME}'*) vault="$HOME${vault#\$\{HOME\}}" ;;
  '$HOME'*) vault="$HOME${vault#\$HOME}" ;;
esac
[ -n "$vault" ] && [ -d "$vault/.git" ] || exit 0

state="$vault/.git/synapsidian"
mkdir -p "$state" 2>/dev/null || exit 0
now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
day=$(date +%Y-%m-%d)

if command -v jq >/dev/null 2>&1; then
  printf '%s' "$input" | jq -c --arg ts "$now" --arg day "$day" \
    '{ts: $ts, date: $day, session_id: .session_id, transcript_path: .transcript_path,
      cwd: .cwd, reason: (.reason // "other")}' >>"$state/session-queue.jsonl" 2>/dev/null
elif command -v python3 >/dev/null 2>&1; then
  # -I: isolated mode, so a json.py in the session's folder is never imported instead of the stdlib.
  printf '%s' "$input" | QUEUE="$state/session-queue.jsonl" TS="$now" DAY="$day" python3 -I -c '
import json, os, sys
d = json.load(sys.stdin)
row = {"ts": os.environ["TS"], "date": os.environ["DAY"], "session_id": d.get("session_id"),
       "transcript_path": d.get("transcript_path"), "cwd": d.get("cwd"), "reason": d.get("reason", "other")}
with open(os.environ["QUEUE"], "a", encoding="utf-8") as f:
    f.write(json.dumps(row, ensure_ascii=False) + "\n")
' 2>/dev/null
fi
exit 0
