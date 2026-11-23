#!/bin/sh
# Run a plugin script with uv. Hooks started by the desktop app may not inherit the
# shell PATH, so look for uv in the usual install locations before giving up.
# Usage: run.sh <script.py> [args...]   (stdin is passed through)
#
# --no-config: hooks run in whatever folder the session was opened in, and a uv.toml there
# would otherwise choose the package index (and cache) the plugin's dependencies come from.
script="$1"
shift

for candidate in "$(command -v uv 2>/dev/null)" "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" \
  /opt/homebrew/bin/uv /usr/local/bin/uv; do
  if [ -n "$candidate" ] && [ -x "$candidate" ]; then
    exec "$candidate" run --no-config --quiet --script "$script" "$@"
  fi
done

echo "synapsidian: uv not found; install it from https://docs.astral.sh/uv/" >&2
exit 0
