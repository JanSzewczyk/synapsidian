#!/bin/sh
# UserPromptSubmit: a prompt that starts with `>>` goes to the vault's Inbox, not to Claude (D137).
#
# This runs on every prompt, so it decides in the shell: only a `>>` prompt starts uv and
# capture.py. Anything else exits at once with no output, and the prompt goes on as usual.
input=$(cat)
case "$input" in *'"prompt"'*) ;; *) exit 0 ;; esac
if command -v jq >/dev/null 2>&1; then
  prompt=$(printf '%s' "$input" | jq -r '.prompt // empty' 2>/dev/null)
  case "$prompt" in ">>"* | " >>"* | "	>>"*) ;; *) exit 0 ;; esac
else
  # No jq: a cheap look at the raw JSON, then capture.py checks the prompt properly.
  printf '%s' "$input" | grep -q '"prompt"[[:space:]]*:[[:space:]]*"[[:space:]]*>>' || exit 0
fi
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
printf '%s' "$input" | exec "$root/hooks/run.sh" "$root/scripts/capture.py"
