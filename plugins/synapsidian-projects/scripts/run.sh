#!/bin/sh
# Run a synapsidian-projects script with uv. A plugin can't use another plugin's files, so this is
# synapsidian-work's run.sh again: the desktop app may not pass the shell PATH, so look for uv in the
# usual install locations before giving up.
# Usage: run.sh <script.py> [args...]   (stdin is passed through)
script="$1"
shift

for candidate in "$(command -v uv 2>/dev/null)" "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" \
  /opt/homebrew/bin/uv /usr/local/bin/uv; do
  if [ -n "$candidate" ] && [ -x "$candidate" ]; then
    exec "$candidate" run --no-config --quiet --script "$script" "$@"  # no uv.toml from the cwd
  fi
done

echo "synapsidian-projects: uv not found; install it from https://docs.astral.sh/uv/" >&2
exit 2
