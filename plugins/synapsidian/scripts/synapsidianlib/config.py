"""Resolve the vault path and runtime-state dirs the same way in every script.

Vault path, first match wins:
  1. explicit --vault argument (skills pass `${user_config.vault_path}`)
  2. CLAUDE_PLUGIN_OPTION_VAULT_PATH (Claude Code sets it for hook processes)
  3. SYNAPSIDIAN_VAULT (manual runs, tests, and the SessionStart hook's CLAUDE_ENV_FILE export)
  4. the plugin's saved option in Claude Code's settings.json (`pluginConfigs["synapsidian@..."]`)

A value that still reads `${...}` was not substituted and counts as unset. Paths are
returned with the on-disk letter case, because macOS matches names case-insensitively
but string comparisons (hooks, Obsidian's registry) do not.
"""

from __future__ import annotations

import json
import os
import unicodedata
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = PLUGIN_ROOT / "schema"
BASES_DIR = PLUGIN_ROOT / "bases"

VAULT_ENV_VARS = ("CLAUDE_PLUGIN_OPTION_VAULT_PATH", "SYNAPSIDIAN_VAULT")
DATA_ENV_VARS = ("CLAUDE_PLUGIN_DATA", "SYNAPSIDIAN_DATA")
PLUGIN_NAME = "synapsidian"


def true_case(path: Path) -> Path:
    """`path` with every existing component spelled as it is on disk (absolute, resolved)."""
    path = path.resolve()
    result = Path(path.anchor)
    parts = path.parts[1:]
    for index, part in enumerate(parts):
        try:
            entries = [entry.name for entry in result.iterdir()]
        except OSError:
            return result.joinpath(*parts[index:])
        if part not in entries:
            # APFS stores names as given and matches them ignoring case and normalisation form.
            folded = unicodedata.normalize("NFC", part).casefold()
            part = next((e for e in entries if unicodedata.normalize("NFC", e).casefold() == folded), part)
        result /= part
    return result


def too_broad(path: Path) -> bool:
    """A vault path that would make every file of the user's a vault note: `/`, the home folder or above."""
    home = Path.home().resolve()
    return path == Path(path.anchor) or path == home or path in home.parents


def _usable(raw: object) -> bool:
    """Set, and not a `${user_config.*}` placeholder Claude Code left unfilled (`${HOME}/x` is fine)."""
    return isinstance(raw, str) and bool(raw.strip()) and not raw.strip().startswith("${user_config")


def _expand(raw: str) -> Path:
    return true_case(Path(os.path.expandvars(raw.strip())).expanduser())


def settings_file() -> Path:
    if override := os.environ.get("SYNAPSIDIAN_SETTINGS_FILE"):
        return Path(override)
    base = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return Path(base) / "settings.json"


def _saved_option(key: str) -> object:
    try:
        settings = json.loads(settings_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for plugin_id, entry in (settings.get("pluginConfigs") or {}).items():
        if plugin_id.split("@", 1)[0] == PLUGIN_NAME and isinstance(entry, dict):
            value = (entry.get("options") or {}).get(key)
            if value is not None:
                return value
    return None


def option(key: str) -> str | None:
    """A plugin option: env from Claude Code (hooks), then settings.json; None when the user left it empty."""
    for raw in (os.environ.get(f"CLAUDE_PLUGIN_OPTION_{key.upper()}"), _saved_option(key)):
        if _usable(raw):
            return str(raw).strip()
    return None


def option_list(key: str) -> list[str]:
    """A list option (`multiple: true`): Claude Code may hand it over as a JSON array, a list in
    settings.json, or text separated by commas or newlines. Empty or unsubstituted means []."""
    raws: list[object] = [os.environ.get(f"CLAUDE_PLUGIN_OPTION_{key.upper()}"), _saved_option(key)]
    for raw in raws:
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
        if not _usable(raw):
            continue
        text = str(raw).strip()
        if text.startswith("["):
            try:
                items = json.loads(text)
            except ValueError:
                items = None
            if isinstance(items, list):
                return [str(item).strip() for item in items if str(item).strip()]
        return [part.strip() for part in text.replace("\n", ",").split(",") if part.strip()]
    return []


def vault_path(arg: str | None = None) -> Path | None:
    """The configured vault path, or None when nothing is configured."""
    for raw in (arg, *(os.environ.get(name) for name in VAULT_ENV_VARS), _saved_option("vault_path")):
        if _usable(raw):
            return _expand(raw)  # type: ignore[arg-type]
    return None


def looks_like_vault(path: Path) -> bool:
    return (path / ".git").is_dir() and any(
        (path / name).exists() for name in ("About.md", ".obsidian", ".synapsidian")
    )


def write_vault(arg: str | None = None) -> Path | None:
    """The vault a writing script may change, or None.

    `synapsidian *` is pre-approved in every skill, so `--vault` must not turn it into a way to
    write anywhere: a `--vault` other than the configured vault has to look like one (a git
    repository with About.md, .obsidian or .synapsidian). With nothing configured (tests, a first
    setup) the argument is taken as given. `/` and the home folder are never a vault.
    """
    path = vault_path(arg)
    if path is None or too_broad(path):
        return None
    configured = vault_path()
    if arg and configured is not None and path != configured and not looks_like_vault(path):
        return None
    return path


def data_dir(arg: str | None = None) -> Path:
    """Plugin-wide runtime state (caches). Never inside the vault's notes."""
    for raw in (arg, *(os.environ.get(name) for name in DATA_ENV_VARS)):
        if _usable(raw):
            path = _expand(raw)  # type: ignore[arg-type]
            break
    else:
        path = Path.home() / ".local" / "state" / "synapsidian"
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_dir(vault: Path, fallback: str | None = None) -> Path:
    """Per-vault runtime state (commit lock, saved sessions): `<vault>/.git/synapsidian`.

    It lives with the vault's repository, so every process writing to that vault shares
    it, whichever plugin data dir Claude Code handed that process. Git never tracks it.
    """
    git_dir = vault / ".git"
    path = git_dir / "synapsidian" if git_dir.is_dir() else data_dir(fallback)
    path.mkdir(parents=True, exist_ok=True)
    return path
