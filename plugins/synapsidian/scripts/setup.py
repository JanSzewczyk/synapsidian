#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0.2"]
# ///
"""Set up and check the synapsidian vault and Obsidian (D52). Every command prints JSON.

  setup.py check    [--vault V]
  setup.py apply    [--vault V] [--name N --email E] [--about key=value ...]
  setup.py register [--vault V] [--obsidian-closed]   add the vault to Obsidian's registry (Obsidian must be closed)
  setup.py selftest [--vault V]        drive the session hooks end to end against a throwaway vault
  setup.py extension --from DIR [--vault V]   install or update an add-on's schema, templates and bases

`apply` is idempotent: it creates what is missing, never overwrites a note, and for
Obsidian settings only sets keys the user hasn't set differently (reported as `kept`).
It generates a Templater template per note type into `Templates/Generated/` (D110, D119),
rewriting one only while the user hasn't edited it.
It also renames tasks with a legacy `ZAD-n` id to `Tn`, links included (D93, `task_ids`), and
appends the empty `## Rules` section to an About note that predates it (D94). In the vault's
Bases it turns a top-level `file.inFolder("<type folder>")` filter into "this type, outside
Archive/", so notes filed in project folders show up too (D102); nothing else in a Base changes.
It moves notes from a folder their type no longer uses to the one the schema gives them
(D106, `refiled`), in a commit of its own, as for the task ids.
`extension` copies DIR (extension.yaml, schema.yaml, templates/, bases/) to
`<vault>/.synapsidian/extensions/<name>/`, then runs `apply` so the new folders, Bases views and
property types exist; both go into one commit (D90).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import plistlib
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml

import sessions
from synapsidianlib import config, frontmatter, gitops, obsidian_templates, schema, taskids, vault
from synapsidianlib.about import split_rules

UV_LOCATIONS = ("~/.local/bin/uv", "~/.cargo/bin/uv", "/opt/homebrew/bin/uv", "/usr/local/bin/uv")  # as hooks/run.sh
REQUIRED_HOOKS = {"SessionStart", "SessionEnd", "PreToolUse", "PostToolUse"}
MIN_OBSIDIAN = (1, 14, 0)  # kanban view in Bases is core from 1.14
FLATPAK_ID = "md.obsidian.Obsidian"


@dataclass(frozen=True)
class ObsidianHost:
    """Where Obsidian lives on this operating system, and how to talk about it (D157)."""

    platform: str
    apps: tuple[Path, ...]  # install locations; Obsidian counts as installed if one exists or `support` does
    support: Path  # Obsidian's own folder: obsidian.json and the obsidian-<x.y.z>.asar updates
    install: str
    quit: str

    @property
    def registry(self) -> Path:
        return self.support / "obsidian.json"

    def open_command(self, url: str) -> str:
        if self.platform == "win32":
            return f'start "" "{url}"'
        return f"{'open' if self.platform == 'darwin' else 'xdg-open'} '{url}'"


def obsidian_host(platform: str, env: Mapping[str, str], home: Path) -> ObsidianHost:
    """Paths from Obsidian's help ("How Obsidian stores data"): macOS Application Support,
    Windows %APPDATA%, elsewhere $XDG_CONFIG_HOME or ~/.config. The Flatpak keeps its own config
    folder; the Snap is classic, so it uses ~/.config like a native install."""
    if platform == "darwin":
        return ObsidianHost(
            platform,
            (Path("/Applications/Obsidian.app"), home / "Applications" / "Obsidian.app"),
            home / "Library" / "Application Support" / "obsidian",
            "brew install --cask obsidian  (or https://obsidian.md/download)",
            "Cmd+Q",
        )
    if platform == "win32":
        appdata = Path(env.get("APPDATA") or home / "AppData" / "Roaming")
        local = Path(env.get("LOCALAPPDATA") or home / "AppData" / "Local")
        program_files = Path(env.get("ProgramFiles") or "C:/Program Files")
        return ObsidianHost(
            platform,
            (local / "Programs" / "Obsidian" / "Obsidian.exe", program_files / "Obsidian" / "Obsidian.exe"),
            appdata / "obsidian",
            "the installer from https://obsidian.md/download",
            "close every Obsidian window",
        )
    xdg = Path(env["XDG_CONFIG_HOME"]) if env.get("XDG_CONFIG_HOME") else home / ".config"
    flatpak = home / ".var" / "app" / FLATPAK_ID / "config" / "obsidian"
    support = next((d for d in (xdg / "obsidian", flatpak) if d.is_dir()), xdg / "obsidian")
    return ObsidianHost(
        platform,
        (
            Path("/opt/Obsidian"),
            Path("/snap/obsidian"),
            Path("/var/lib/flatpak/app") / FLATPAK_ID,
            home / ".local" / "share" / "flatpak" / "app" / FLATPAK_ID,
        ),
        support,
        f"flatpak install flathub {FLATPAK_ID}  (or the AppImage or Snap from https://obsidian.md/download)",
        "close every Obsidian window",
    )


HOST = obsidian_host(sys.platform, os.environ, Path.home())

FOLDERS = [
    "Inbox",
    "Daily",
    "Tasks",
    "People",
    "Meetings",
    "Decisions",
    "Notes",
    "Howtos",
    "Ideas",
    "Goals",
    "Sources",
    "Research",
    "Reviews",
    "Thinking",
    "Bases",
    "Templates",
    "Attachments",
    "Archive",
]
EXTENSION_PARTS = ("extension.yaml", "schema.yaml", "templates", "bases")


def folders(s: schema.Schema) -> list[str]:
    """The core folders plus the folder of every type an extension added (its fixed part, for a
    `{title}` folder: `Projects`, not `Projects/{title}`)."""
    extra = [t.folder_prefix for t in s.types.values() if t.folder_prefix and t.folder_prefix not in FOLDERS]
    return [*FOLDERS, *dict.fromkeys(extra)]


GITIGNORE = """# Obsidian per-device state
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/cache
.trash/
.DS_Store

# Claude Code per-machine state (permission approvals, worktrees) when a session runs in the vault
.claude/

# Community plugin code (Excalidraw alone is 5 MB a release); its manifest and settings stay tracked
.obsidian/plugins/*/main.js
.obsidian/plugins/*/styles.css
"""


def templater_ignored(s: schema.Schema) -> list[dict[str, str]]:
    """Every folder synapsidian writes notes to. With "Trigger on new file creation" on, Templater runs
    the `<% %>` code of any new file outside these, Claude's notes and copied web pages included."""
    return [{"folder": f} for f in folders(s) if f != "Templates"]


# Community plugins synapsidian requires (D91, D110) and the settings it gives them. Each setting is
# (synapsidian's value, the plugin's own default): a value still at the plugin's default was never
# chosen by the user, so synapsidian sets it; any other value is the user's and is kept. A value may
# be a function of the vault's schema. A setting under `lists` is a list synapsidian adds its entries
# to, keeping the user's; entries starting with the given prefix are synapsidian's own, and one synapsidian
# no longer wants is dropped.
REQUIRED_PLUGINS: dict[str, dict[str, Any]] = {
    "obsidian-git": {
        "name": "Git",
        "settings": {
            "autoSaveInterval": (30, 0),
            "disablePush": (True, False),
            "autoCommitMessage": ("vault: manual edits {{date}}", "vault backup: {{date}}"),
            "commitMessage": ("vault: manual edits {{date}}", "vault backup: {{date}}"),
        },
    },
    "obsidian-excalidraw-plugin": {
        "name": "Excalidraw",
        "settings": {
            "folder": ("Attachments", "Excalidraw"),  # synapsidian's scanners skip Attachments/
            "compress": (False, True),  # plain JSON: readable diffs and greppable drawings
        },
    },
    # Notes made by hand from the generated templates. "Trigger on new file creation" stays off:
    # it lives in Obsidian's local storage (Templater 2.21+), and synapsidian never asks for it.
    "templater-obsidian": {
        "name": "Templater",
        "settings": {
            "templates_folder": (obsidian_templates.FOLDER, ""),
            "enabled_templates_hotkeys": (obsidian_templates.hotkeys, []),
            "ignore_folders_on_creation": (templater_ignored, []),
        },
        "lists": {"enabled_templates_hotkeys": f"{obsidian_templates.FOLDER}/", "ignore_folders_on_creation": None},
    },
    # The Calendar view of the Bases (tasks by due date, meetings by date, goals by target). Its
    # options live in each view of the .base file, so synapsidian has nothing to set in its data.json.
    "calendar-bases": {"name": "Calendar Bases", "settings": {}},
}

# Community plugins setup offers and installs on a yes; `ready` doesn't wait for them (D115).
RECOMMENDED_PLUGINS: dict[str, str] = {
    "realclaudian": "Claudian",  # Claude Code in Obsidian's sidebar, with the vault as its working directory
}


def required_plugins(vault_root: Path) -> dict[str, dict[str, Any]]:
    """Core's required plugins plus those an installed add-on lists under `plugins` in its
    extension.yaml (D90, D115), each `{id: {name, settings: {key: [synapsidian value, default]}}}`.
    A plugin core or an earlier add-on already requires keeps that spec."""
    plugins = {plugin_id: {**spec, "by": "synapsidian"} for plugin_id, spec in REQUIRED_PLUGINS.items()}
    for directory in schema.extension_dirs(vault_root):
        declared = read_yaml(directory / "extension.yaml").get("plugins") or {}
        for plugin_id, spec in declared.items():
            if plugin_id in plugins:
                continue
            settings = (spec or {}).get("settings") or {}
            if not all(isinstance(pair, list) and len(pair) == 2 for pair in settings.values()):
                raise ValueError(
                    f"{directory.name}: plugin {plugin_id} settings must be [synapsidian value, default] pairs"
                )
            plugins[plugin_id] = {
                "name": (spec or {}).get("name") or plugin_id,
                "settings": {key: tuple(pair) for key, pair in settings.items()},
                "by": directory.name,
            }
    return plugins


def plugin_settings(spec: dict[str, Any], s: schema.Schema) -> dict[str, tuple[Any, Any]]:
    """A required plugin's settings as (synapsidian's value, plugin default), computed for this schema."""
    settings = spec["settings"].items()
    return {key: (value(s) if callable(value) else value, default) for key, (value, default) in settings}


def entry_key(entry: Any) -> str:
    """What identifies an entry of a list setting: a template path or a folder."""
    if isinstance(entry, dict):
        return str(entry.get("template") or entry.get("folder") or json.dumps(entry, sort_keys=True))
    return str(entry)


def merged_list(current: Any, wanted: list[Any], owned: str | None) -> list[Any]:
    """The user's entries plus synapsidian's missing ones; synapsidian's own entries it no longer wants go."""
    current = current if isinstance(current, list) else []
    keep = {entry_key(w) for w in wanted}
    have = {entry_key(e) for e in current}
    kept = [e for e in current if not (owned and entry_key(e).startswith(owned) and entry_key(e) not in keep)]
    return [*kept, *(w for w in wanted if entry_key(w) not in have)]


APP_SETTINGS = {
    "newFileLocation": "folder",
    "newFileFolderPath": "Inbox",
    "attachmentFolderPath": "Attachments",
    "newLinkFormat": "shortest",
    "useMarkdownLinks": False,
    "alwaysUpdateLinks": True,
    "trashOption": "local",
}
CORE_PLUGINS_ON = [
    "file-explorer",
    "global-search",
    "switcher",
    "backlink",
    "outgoing-link",
    "tag-pane",
    "page-preview",
    "daily-notes",  # fills Templates/Daily.md's {{date}} itself; the core Templates plugin isn't needed (D110)
    "command-palette",
    "outline",
    "file-recovery",
    "bases",
    "properties",
    "canvas",
    "bookmarks",
]
DAILY_NOTES = {"folder": "Daily", "format": "YYYY-MM-DD", "template": "Templates/Daily", "autorun": False}
PROPERTY_TYPES = {
    "date": "date",
    "number": "number",
    "links": "multitext",
    "list": "multitext",
    "link": "text",
    "text": "text",
}
BUILTIN_PROPERTIES = {"tags", "aliases", "cssclasses"}


# --- helpers ------------------------------------------------------------------------


def version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", text)[:3])


def same_path(a: Path, b: object) -> bool:
    """Same location on disk; macOS folder names match regardless of letter case."""
    if not isinstance(b, str) or not b:
        return False
    return config.true_case(a) == config.true_case(Path(b))


def obsidian_running() -> bool | None:
    """None when this system can't tell (no pgrep or tasklist, or it failed)."""
    try:
        if HOST.platform == "win32":
            listing = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Obsidian.exe", "/NH", "/FO", "CSV"],
                capture_output=True,
                text=True,
                check=True,
            )
            return "obsidian.exe" in listing.stdout.lower()
        process = "Obsidian" if HOST.platform == "darwin" else "obsidian"
        code = subprocess.run(["pgrep", "-x", process], capture_output=True).returncode
    except (OSError, subprocess.CalledProcessError):
        return None
    return {0: True, 1: False}.get(code)  # pgrep exits 2 or 3 on its own errors


def obsidian_installed() -> bool:
    return HOST.support.is_dir() or any(app.exists() for app in HOST.apps)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def git_global(key: str) -> str | None:
    out = subprocess.run(["git", "config", "--global", key], capture_output=True, text=True)
    return out.stdout.strip() or None


def system_timezone() -> str | None:
    try:
        target = Path("/etc/localtime").readlink().as_posix()
    except OSError:
        return None
    return target.split("zoneinfo/", 1)[-1] if "zoneinfo/" in target else None


def property_types(s: schema.Schema) -> dict[str, str]:
    """Obsidian property types derived from the vault's schema (one type per name, vault-wide)."""
    types: dict[str, str] = {}
    for type_name in s.types:
        for name, f in s.fields_for(type_name).items():
            if name in BUILTIN_PROPERTIES:
                continue
            kind = PROPERTY_TYPES.get(f.kind, "text")
            if types.setdefault(name, kind) != kind:
                raise ValueError(f"schema gives property {name!r} two Obsidian types: {types[name]} and {kind}")
    return types


# --- check --------------------------------------------------------------------------


def core_templates_clash(vault_root: Path) -> dict[str, Any] | None:
    """The core Templates plugin on with a folder that holds `Templates/Generated/` (D118), as synapsidian's
    own setup left it before D110. Its *Insert template* lists the generated Templater templates and
    pastes one without running it, so the note shows the runtime's JavaScript. `own_templates` are
    the Markdown files in that folder synapsidian didn't write: the user's core templates."""
    obsidian = vault_root / ".obsidian"
    core = read_json(obsidian / "core-plugins.json")
    # Obsidian turns core Templates on by default, so a vault without the key has it on.
    if isinstance(core, dict) and core.get("templates") is False:
        return None
    settings = read_json(obsidian / "templates.json")
    folder = str((settings or {}).get("folder") or "").strip("/ ") if isinstance(settings, dict) else ""
    synapsidian_folder = obsidian_templates.FOLDER
    if not folder or not (synapsidian_folder == folder or synapsidian_folder.startswith(f"{folder}/")):
        return None
    own = sorted(
        rel
        for path in (vault_root / folder).rglob("*.md")
        if (rel := path.relative_to(vault_root).as_posix()) != obsidian_templates.DAILY
        and not rel.startswith(f"{synapsidian_folder}/")
        and not obsidian_templates.legacy(rel)
    )
    return {"folder": folder, "own_templates": own}


def move_templater_folder(data: Path, vault_root: Path, changes: Changes) -> None:
    """Templater settings that still name the folder synapsidian generated into before D119: its
    templates folder moves to the new one, and a *Create* command for a file the move removed
    goes. Commands for files still there (templates the user edited) stay."""
    settings = read_json(data)
    if not isinstance(settings, dict):
        return
    moved = dict(settings)
    if moved.get("templates_folder") in obsidian_templates.LEGACY_FOLDERS:
        moved["templates_folder"] = obsidian_templates.FOLDER
    hotkeys = moved.get("enabled_templates_hotkeys")
    if isinstance(hotkeys, list):
        moved["enabled_templates_hotkeys"] = [
            h
            for h in hotkeys
            if not (isinstance(h, str) and obsidian_templates.legacy(h) and not (vault_root / h).is_file())
        ]
    if moved != settings:
        write_json(data, moved)
        changes.updated.append(changes.rel(data))


def installer_version() -> str | None:
    """The version of the installed app bundle; only macOS records one synapsidian can read."""
    for app in HOST.apps:
        plist = app / "Contents" / "Info.plist"
        try:
            return plistlib.loads(plist.read_bytes()).get("CFBundleShortVersionString")
        except (OSError, plistlib.InvalidFileException):
            continue
    return None


def obsidian_status() -> dict[str, Any]:
    hints = {"install": HOST.install, "quit": HOST.quit, "registry": str(HOST.registry)}
    if not obsidian_installed():
        return {"installed": False, **hints}
    installer = installer_version()
    # Obsidian downloads each update as obsidian-<x.y.z>.asar next to its registry, on every OS.
    asars = sorted(HOST.support.glob("obsidian-*.asar"), key=lambda p: version_tuple(p.stem))
    app_version = asars[-1].stem.removeprefix("obsidian-") if asars else installer
    registry = read_json(HOST.registry)
    registry = registry if isinstance(registry, dict) else {}
    return {
        "installed": True,
        "app_version": app_version,
        "installer_version": installer,
        # None: no update downloaded yet and no bundle to read, so the user checks Settings → General.
        "version_ok": version_tuple(app_version) >= MIN_OBSIDIAN if app_version else None,
        "minimum": ".".join(map(str, MIN_OBSIDIAN)),
        "running": obsidian_running(),
        "registered_vaults": [v.get("path") for v in registry.get("vaults", {}).values()],
        "cli_enabled": bool(registry.get("cli")),
        "cli_on_path": shutil.which("obsidian"),
        **hints,
    }


def find_uv() -> str | None:
    """uv as hooks/run.sh finds it: hooks started by the desktop app may not see the shell PATH."""
    candidates = [shutil.which("uv"), *(Path(p).expanduser() for p in UV_LOCATIONS)]
    return next((str(c) for c in candidates if c and Path(c).is_file() and os.access(c, os.X_OK)), None)


def automation_status(vault_root: Path) -> dict[str, Any]:
    """What the session-capture hooks need in order to work. Scheduled tasks are checked by /synapsidian:schedule."""
    try:
        events = set(json.loads((config.PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"])
    except (OSError, ValueError, KeyError):
        events = set()
    queue = {"rows": 0, "pending_days": {}}
    if vault_root.is_dir() and gitops.is_repo(vault_root):
        state = sessions.State(vault_root)
        queue["rows"] = sum(1 for _ in sessions.read_jsonl(state.queue))
        queue["pending_days"] = {day: len(ids) for day, ids in state.pending().items()}
    json_tool = "jq" if shutil.which("jq") else "python3" if shutil.which("python3") else None
    problems = []
    if not find_uv():
        problems.append("uv not found where hooks look for it (PATH, ~/.local/bin, ~/.cargo/bin, /opt/homebrew/bin)")
    if json_tool is None:
        problems.append("neither jq nor python3 on PATH: session-end.sh would queue nothing")
    if missing := sorted(REQUIRED_HOOKS - events):
        problems.append(f"hooks.json lacks {', '.join(missing)}")
    return {
        "ok": not problems,
        "problems": problems,
        "uv": find_uv(),
        "session_end_json_tool": json_tool,
        "hook_events": sorted(events),
        "queue": queue,
        "scheduled_tasks": "not readable from here; run /synapsidian:schedule check",
    }


def plugin_dir(vault_root: Path, plugin_id: str) -> Path:
    return vault_root / ".obsidian" / "plugins" / plugin_id


def enabled_plugins(vault_root: Path) -> set[str]:
    enabled = read_json(vault_root / ".obsidian" / "community-plugins.json")
    return set(enabled) if isinstance(enabled, list) else set()


def recommended_status(vault_root: Path) -> list[dict[str, Any]]:
    """Each recommended community plugin: installed and enabled."""
    enabled = enabled_plugins(vault_root)
    report = []
    for plugin_id, name in RECOMMENDED_PLUGINS.items():
        manifest = read_json(plugin_dir(vault_root, plugin_id) / "manifest.json")
        installed = isinstance(manifest, dict)
        report.append(
            {
                "id": plugin_id,
                "name": name,
                "installed": installed,
                "version": manifest.get("version") if installed else None,
                "enabled": plugin_id in enabled,
            }
        )
    return report


def plugins_status(vault_root: Path, s: schema.Schema | None = None) -> list[dict[str, Any]]:
    """Each required community plugin, the add-ons' included: installed, enabled, and which synapsidian
    settings are still unset (for a list setting: one of synapsidian's entries is missing)."""
    s = s or schema.load(vault_root)
    enabled = enabled_plugins(vault_root)
    report = []
    for plugin_id, spec in required_plugins(vault_root).items():
        manifest = read_json(plugin_dir(vault_root, plugin_id) / "manifest.json")
        data = read_json(plugin_dir(vault_root, plugin_id) / "data.json")
        data = data if isinstance(data, dict) else {}
        unset = []
        for key, (value, default) in plugin_settings(spec, s).items():
            if key in spec.get("lists", {}):
                current = data.get(key)
                have = {entry_key(e) for e in current} if isinstance(current, list) else set()
                if any(entry_key(w) not in have for w in value):
                    unset.append(key)
            elif data.get(key, default) == default:
                unset.append(key)
        report.append(
            {
                "id": plugin_id,
                "name": spec["name"],
                "required_by": spec["by"],
                "installed": isinstance(manifest, dict),
                "version": manifest.get("version") if isinstance(manifest, dict) else None,
                "enabled": plugin_id in enabled,
                "settings_unset": unset,
            }
        )
    return report


def unknown_types(vault_root: Path, s: schema.Schema) -> dict[str, int]:
    """Note types in the vault that no installed schema defines, with how many notes have each:
    usually notes of an add-on whose extension isn't installed (yet) in this vault."""
    counts: dict[str, int] = {}
    for note in vault.iter_notes(vault_root):
        if isinstance(note.type, str) and note.type and note.type not in s.types:
            counts[note.type] = counts.get(note.type, 0) + 1
    return dict(sorted(counts.items()))


def cmd_check(vault_root: Path) -> dict[str, Any]:
    obsidian = obsidian_status()
    s = schema.load(vault_root)
    wanted = folders(s)
    missing = [f for f in wanted if not (vault_root / f).is_dir()]
    report = {
        "vault": str(vault_root),
        "vault_exists": vault_root.is_dir(),
        "vault_is_git_repo": vault_root.is_dir() and gitops.is_repo(vault_root),
        "missing_folders": missing if vault_root.is_dir() else wanted,
        "extensions": installed_extensions(vault_root),
        "schema_warnings": list(s.warnings),
        "unknown_types": unknown_types(vault_root, s) if vault_root.is_dir() else {},
        "about_exists": (vault_root / "About.md").is_file(),
        "registered_in_obsidian": any(same_path(vault_root, p) for p in obsidian.get("registered_vaults", [])),
        "obsidian": obsidian,
        "tools": {"uv": shutil.which("uv") or str(Path.home() / ".local/bin/uv"), "git": shutil.which("git")},
        "git_identity": {"name": git_global("user.name"), "email": git_global("user.email")},
        "community_plugins_required": (plugins := plugins_status(vault_root, s)),
        "community_plugins_recommended": recommended_status(vault_root),
        "core_templates_clash": core_templates_clash(vault_root) if vault_root.is_dir() else None,
        "automation": automation_status(vault_root),
    }
    report["ready"] = bool(
        report["vault_exists"]
        and report["vault_is_git_repo"]
        and not missing
        and report["about_exists"]
        and obsidian["installed"]
        and obsidian.get("version_ok") is not False
        and report["registered_in_obsidian"]
        and report["automation"]["ok"]
        and not report["core_templates_clash"]
        and all(p["installed"] and p["enabled"] and not p["settings_unset"] for p in plugins)
    )
    return report


# --- selftest -----------------------------------------------------------------------


def run_hook(argv: list[str], env: dict[str, str], stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, input=stdin, capture_output=True, text=True, env=env, timeout=120)


def cmd_selftest(vault_root: Path) -> dict[str, Any]:
    """Drive the hooks the way Claude Code does, against a throwaway vault so the real queue stays clean."""
    hooks = config.PLUGIN_ROOT / "hooks"
    checks: list[dict[str, Any]] = []

    def record(name: str, ok: bool, detail: str = "") -> bool:
        checks.append({"check": name, "ok": ok, **({"detail": detail} if detail else {})})
        return ok

    base_env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_PLUGIN", "SYNAPSIDIAN_"))}
    with tempfile.TemporaryDirectory(prefix="synapsidian-selftest-") as tmp:
        scratch = Path(tmp) / "vault"
        scratch.mkdir()
        gitops.git(scratch, "init", "--quiet")
        env = {**base_env, "CLAUDE_PLUGIN_OPTION_VAULT_PATH": str(scratch)}
        payload = json.dumps(
            {
                "session_id": "selftest-session",
                "transcript_path": str(Path(tmp) / "t.jsonl"),
                "cwd": tmp,
                "reason": "other",
            }
        )
        ended = run_hook(["/bin/sh", str(hooks / "session-end.sh")], env, payload)
        rows = list(sessions.read_jsonl(sessions.State(scratch).queue))
        record(
            "SessionEnd queues a row",
            ended.returncode == 0 and len(rows) == 1 and rows[0].get("session_id") == "selftest-session",
            ended.stderr.strip(),
        )
        listed = run_hook(
            [
                str(hooks / "run.sh"),
                str(config.PLUGIN_ROOT / "scripts" / "sessions.py"),
                "--vault",
                str(scratch),
                "pending",
            ],
            env,
        )
        try:
            days = json.loads(listed.stdout)["days"]
        except (ValueError, KeyError):
            days = {}
        record(
            "uv runs the queue reader and it sees the row",
            any("selftest-session" in ids for ids in days.values()),
            listed.stderr.strip(),
        )

    if vault_root.is_dir() and gitops.is_repo(vault_root):
        env = {**base_env, "CLAUDE_PLUGIN_OPTION_VAULT_PATH": str(vault_root)}
        brief = run_hook([str(hooks / "run.sh"), str(config.PLUGIN_ROOT / "scripts" / "brief.py"), "--minimal"], env)
        try:
            ok = "additionalContext" in json.loads(brief.stdout)["hookSpecificOutput"]
        except (ValueError, KeyError):
            ok = False
        record("SessionStart brief returns context for the real vault", ok, brief.stderr.strip())
    else:
        record("SessionStart brief returns context for the real vault", False, "vault is not set up yet")
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


# --- apply --------------------------------------------------------------------------


class Changes:
    def __init__(self, vault_root: Path) -> None:
        self.root = vault_root
        self.created: list[str] = []
        self.updated: list[str] = []
        self.kept: list[str] = []

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def write_new(self, path: Path, text: str) -> None:
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.created.append(self.rel(path))

    def merge_json(
        self,
        path: Path,
        wanted: dict[str, Any],
        unchosen: dict[str, Any] | None = None,
        lists: dict[str, str | None] | None = None,
    ) -> None:
        """Set `wanted` keys the user hasn't set; a value equal to `unchosen[key]` (a plugin default) is unset.
        A key in `lists` is merged entry by entry instead (`merged_list`, its value the owned prefix)."""
        current = read_json(path)
        current = current if isinstance(current, dict) else {}
        merged = dict(current)
        unchosen = unchosen or {}
        lists = lists or {}
        for key, value in wanted.items():
            if key in lists:
                merged[key] = merged_list(current.get(key), value, lists[key])
            elif key in current and current[key] != value and (key not in unchosen or current[key] != unchosen[key]):
                self.kept.append(
                    f"{self.rel(path)}: {key}={json.dumps(current[key])} (synapsidian default {json.dumps(value)})"
                )
            else:
                merged[key] = value
        if merged != current or not path.exists():
            listed = self.updated if path.exists() else self.created
            if self.rel(path) not in listed:
                listed.append(self.rel(path))
            write_json(path, merged)


def about_note(s: schema.Schema, about: dict[str, str]) -> str:
    fields = s.fields_for("about")
    meta: dict[str, Any] = {"type": "about", "created": dt.date.today()}
    for key, value in about.items():
        if key not in fields:
            raise ValueError(f"unknown About field {key!r}; allowed: {', '.join(sorted(fields))}")
        if value:
            meta[key] = schema.coerce(fields[key], value)
    meta.setdefault("timezone", system_timezone())
    meta = {k: v for k, v in meta.items() if v is not None}
    template = s.types["about"].template()
    return frontmatter.dump(meta, template.read_text(encoding="utf-8") if template else "")


def add_rules_section(s: schema.Schema, path: Path, changes: Changes) -> None:
    """Append the template's empty `## Rules` section to an About note that predates it (D94).

    Only a note with `type: about` and no Rules heading; the rest of the file is left byte for byte.
    """
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    parsed = frontmatter.parse(text)
    template = s.types["about"].template()
    if (parsed.meta or {}).get("type") != "about" or split_rules(parsed.body)[1] is not None or not template:
        return
    section = split_rules(template.read_text(encoding="utf-8"))[1]
    if section is None:
        return
    path.write_text(f"{text.rstrip(chr(10))}\n\n## Rules\n{section.strip(chr(10))}\n", encoding="utf-8")
    changes.updated.append(changes.rel(path))


FOLDER_FILTER = re.compile(r'^(?P<indent>[ \t]+)- file\.inFolder\("(?P<folder>[^"]*)"\)[ \t]*$')


def type_filters(text: str, s: schema.Schema) -> str:
    """A Base's top-level `file.inFolder("<type folder>")` filter rewritten to select by type (D102).

    Before 0.18.0 the shipped Bases picked a type's notes by its folder, which misses notes
    filed in a project folder. Only a top-level filter line naming exactly one type's folder
    changes: it becomes "not in Archive/", and `note.type == "<type>"` is added when the
    block lacks it. Views, other filters and everything the user wrote stay byte for byte.
    """
    by_folder: dict[str, list[str]] = {}
    for t in s.types.values():
        if t.folder_prefix:
            by_folder.setdefault(t.folder_prefix, []).append(t.name)
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    top = False
    for line in lines:
        if line[:1] not in (" ", "\t", "\n", "\r", ""):
            top = line.startswith("filters:")
        match = FOLDER_FILTER.match(line.rstrip("\r\n")) if top else None
        names = by_folder.get(match["folder"], []) if match else []
        if not match or len(names) != 1:
            out.append(line)
            continue
        indent, newline = match["indent"], line[len(line.rstrip("\r\n")) :] or "\n"
        out += [f"{indent}- not:{newline}", f'{indent}    - file.inFolder("Archive"){newline}']
        if f'note.type == "{names[0]}"' not in text:
            out.append(f'{indent}- note.type == "{names[0]}"{newline}')
    return "".join(out)


def update_base_filters(vault_root: Path, s: schema.Schema, changes: Changes) -> None:
    for path in sorted((vault_root / "Bases").glob("*.base")):
        text = path.read_text(encoding="utf-8")
        new = type_filters(text, s)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changes.updated.append(changes.rel(path))


def installed_extensions(vault_root: Path) -> list[dict[str, Any]]:
    found = []
    for directory in schema.extension_dirs(vault_root):
        manifest = read_yaml(directory / "extension.yaml")
        found.append({"name": directory.name, "version": manifest.get("version"), "rel": rel(vault_root, directory)})
    return found


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def rel(vault_root: Path, path: Path) -> str:
    return path.relative_to(vault_root).as_posix()


def cmd_extension(vault_root: Path, source: Path, data_dir: Path) -> dict[str, Any]:
    """Install or update one add-on in the vault; unchanged files make no commit."""
    manifest = read_yaml(source / "extension.yaml")
    name = str(manifest.get("name") or "")
    if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
        raise ValueError(f"{source}/extension.yaml needs a `name` like synapsidian-work")
    if not vault_root.is_dir():
        raise ValueError("vault does not exist yet; run apply first")
    # Merge into the core plus the other installed extensions first: a conflict fails before any write.
    raw = yaml.safe_load((config.SCHEMA_DIR / "types.yaml").read_text(encoding="utf-8"))
    others = [(d.name, read_yaml(d / "schema.yaml")) for d in schema.extension_dirs(vault_root) if d.name != name]
    schema.merge_extensions(raw, [*others, (name, read_yaml(source / "schema.yaml"))])

    target = vault_root / schema.EXTENSIONS_DIR / name
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for part in EXTENSION_PARTS:
        src = source / part
        if src.is_dir():
            shutil.copytree(src, target / part)
        elif src.is_file():
            shutil.copy2(src, target / part)
    result = cmd_apply(
        vault_root,
        None,
        None,
        {},
        data_dir,
        message=f"synapsidian(setup): install extension {name} {manifest.get('version', '')}".rstrip(),
        also_commit=(rel(vault_root, target),),
    )
    return {**result, "extension": name, "version": manifest.get("version"), "installed_at": rel(vault_root, target)}


def cmd_apply(
    vault_root: Path,
    name: str | None,
    email: str | None,
    about: dict[str, str],
    data_dir: Path,
    *,
    message: str = "synapsidian(setup): create vault layout and Obsidian config",
    also_commit: tuple[str, ...] = (),
) -> dict[str, Any]:
    vault_root.mkdir(parents=True, exist_ok=True)
    name, email, baseline = prepare_repo(vault_root, name, email, data_dir)
    task_ids = migrate_task_ids(vault_root, data_dir)
    refiled = refile_notes(vault_root, data_dir)
    changes = Changes(vault_root)
    s = schema.load(vault_root)

    for folder in folders(s):
        (vault_root / folder).mkdir(exist_ok=True)
    changes.write_new(vault_root / "About.md", about_note(s, about))
    add_rules_section(s, vault_root / "About.md", changes)
    templates = obsidian_templates.sync(vault_root, s)
    changes.created += templates.created
    changes.updated += [*templates.updated, *templates.removed]
    changes.kept += templates.kept
    base_dirs = [config.BASES_DIR, *(d / "bases" for d in schema.extension_dirs(vault_root))]
    for base in sorted(b for d in base_dirs for b in d.glob("*.base")):
        changes.write_new(vault_root / "Bases" / base.name, base.read_text(encoding="utf-8"))
    update_base_filters(vault_root, s, changes)

    obsidian = vault_root / ".obsidian"
    changes.merge_json(obsidian / "app.json", APP_SETTINGS)
    # Core Templates would paste a generated template unrun (D118). With no templates of the user's
    # own in its folder, it is synapsidian's leftover: a `true` there counts as unchosen and goes off.
    core_plugins: dict[str, Any] = dict.fromkeys(CORE_PLUGINS_ON, True)
    clash = core_templates_clash(vault_root)
    if clash and not clash["own_templates"]:
        core_plugins["templates"] = False
    elif clash:
        changes.kept.append(
            f".obsidian/templates.json: folder={json.dumps(clash['folder'])} holds {obsidian_templates.FOLDER}/"
            f" and your templates {', '.join(clash['own_templates'])} (core Templates pastes synapsidian's unrun)"
        )
    changes.merge_json(obsidian / "core-plugins.json", core_plugins, {"templates": True})
    changes.merge_json(obsidian / "daily-notes.json", DAILY_NOTES)
    types_path = obsidian / "types.json"
    current_types = (read_json(types_path) or {}).get("types", {})
    wanted_types = property_types(s)
    merged_types = {**wanted_types, **current_types}
    for key in wanted_types.keys() & current_types.keys():
        if current_types[key] != wanted_types[key]:
            changes.kept.append(f".obsidian/types.json: {key}={current_types[key]} (synapsidian {wanted_types[key]})")
    if merged_types != current_types:
        (changes.updated if types_path.exists() else changes.created).append(".obsidian/types.json")
        write_json(types_path, {"types": merged_types})

    # Settings for the required plugins, once Obsidian has installed them (it owns the plugin folder).
    plugins_configured = []
    for plugin_id, spec in required_plugins(vault_root).items():
        if not spec["settings"] or not (plugin_dir(vault_root, plugin_id) / "manifest.json").is_file():
            continue
        data = plugin_dir(vault_root, plugin_id) / "data.json"
        before = read_json(data)
        if plugin_id == "templater-obsidian":
            move_templater_folder(data, vault_root, changes)
        settings = plugin_settings(spec, s)
        changes.merge_json(
            data,
            {k: value for k, (value, _) in settings.items()},
            {k: default for k, (_, default) in settings.items()},
            spec.get("lists"),
        )
        if read_json(data) != before:
            plugins_configured.append(plugin_id)

    to_commit = [*changes.created, *changes.updated, ".gitignore", *also_commit]
    with gitops.vault_lock(config.state_dir(vault_root, str(data_dir))):
        sha = gitops.commit(vault_root, to_commit, message).sha
    return {
        "ok": True,
        "vault": str(vault_root),
        "baseline_commit": baseline,
        "created": changes.created,
        "updated": changes.updated,
        "kept_user_settings": changes.kept,
        "plugins_configured": plugins_configured,  # reload these in Obsidian, or it keeps the old settings in memory
        "core_templates_off": core_plugins.get("templates") is False,  # takes effect once Obsidian reloads
        "task_ids": task_ids,
        "refiled": refiled,
        "commit": sha,
        "git_author": f"{name} <{email}>",
    }


def refile_notes(vault_root: Path, data_dir: Path) -> dict[str, Any] | None:
    """Move notes from the folder their type used to have to the one the schema now gives
    them (D106), in a commit of its own; None when every note is where it belongs.

    A note moves only when it sits in one of its type's `legacy_folders` (`Tasks/` for a task
    with a project, `Projects/` for a hub that now has a folder of its own) and the schema
    points elsewhere. Names don't change, so links keep working. A note whose target is taken
    stays and is reported; Archive/ and Sources/ are never touched.
    """
    s = schema.load(vault_root)
    moves: list[tuple[Path, Path]] = []
    skipped: list[dict[str, str]] = []
    for note in vault.iter_notes(vault_root):
        note_type = s.types.get(note.type) if isinstance(note.type, str) else None
        if note_type is None or note.meta is None:
            continue
        wanted = note_type.folder_for(note.meta, note.title)
        if note.folder == wanted or note.folder not in note_type.legacy_folders(note.title):
            continue
        target = vault_root / wanted / note.path.name
        if target.exists():
            skipped.append({"rel": note.rel, "to": vault.rel_path(vault_root, target), "why": "target exists"})
        else:
            moves.append((note.path, target))
    if not moves:
        return {"moved": [], "skipped": skipped, "commit": None} if skipped else None
    moved = []
    with gitops.vault_lock(config.state_dir(vault_root, str(data_dir))):
        for source, target in moves:
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
            moved.append({"from": vault.rel_path(vault_root, source), "to": vault.rel_path(vault_root, target)})
        paths = [p for m in moved for p in (m["from"], m["to"])]
        sha = gitops.commit(vault_root, paths, "synapsidian(setup): file notes into their folders").sha
    return {"moved": moved, "skipped": skipped, "commit": sha}


def migrate_task_ids(vault_root: Path, data_dir: Path) -> dict[str, Any] | None:
    """Move legacy ZAD-n tasks to Tn (D93) in a commit of its own; None when there is nothing to move."""
    with gitops.vault_lock(config.state_dir(vault_root, str(data_dir))):
        migration = taskids.migrate_legacy_ids(vault_root)
        if not (migration.renamed or migration.skipped):
            return None  # plain-text mentions alone are reported only alongside a migration
        sha = None
        if migration.touched:
            sha = gitops.commit(vault_root, migration.touched, "synapsidian(setup): rename tasks ZAD-n to Tn").sha
    return {
        "renamed": [{"from": r["from"], "to": r["to"], "file": r["new_rel"]} for r in migration.renamed],
        "relinked": migration.relinked,
        "skipped": migration.skipped,
        "mentions_left": migration.mentions_left,  # plain-text ZAD-n, left alone: may name another tool's task
        "commit": sha,
    }


def ensure_gitignore(gitignore: Path) -> None:
    """Write synapsidian's ignore rules, or append the ones an existing .gitignore lacks; the user's own lines stay."""
    if not gitignore.exists():
        gitignore.write_text(GITIGNORE, encoding="utf-8")
        return
    current = gitignore.read_text(encoding="utf-8")
    present = {line.strip() for line in current.splitlines()}
    missing = [line for line in GITIGNORE.splitlines() if line and not line.startswith("#") and line not in present]
    if missing:
        separator = "" if current.endswith("\n") or not current else "\n"
        gitignore.write_text(f"{current}{separator}{'\n'.join(missing)}\n", encoding="utf-8")


def prepare_repo(vault_root: Path, name: str | None, email: str | None, data_dir: Path) -> tuple[str, str, str | None]:
    """git init + identity, then commit whatever the vault already held and git doesn't track.

    Runs before synapsidian changes anything, so every pre-existing file (an Obsidian-made
    Welcome.md, the user's own notes and settings) has a version to return to (D7).
    """
    if not gitops.is_repo(vault_root):
        gitops.git(vault_root, "init", "--quiet", "--initial-branch=main")
    name = name or gitops.git(vault_root, "config", "user.name", check=False).stdout.strip() or git_global("user.name")
    email = (
        email or gitops.git(vault_root, "config", "user.email", check=False).stdout.strip() or git_global("user.email")
    )
    if not (name and email):
        raise ValueError("no git identity: pass --name and --email")
    gitops.git(vault_root, "config", "user.name", name)
    gitops.git(vault_root, "config", "user.email", email)

    # Ignore rules first, so per-device state (workspace.json) never lands in the baseline.
    ensure_gitignore(vault_root / ".gitignore")
    untracked = gitops.git(vault_root, "ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0")
    existing = [path for path in untracked if path and path != ".gitignore"]
    if not existing:
        return name, email, None  # empty vault: .gitignore goes in with the setup commit
    with gitops.vault_lock(config.state_dir(vault_root, str(data_dir))):
        baseline = gitops.commit(
            vault_root, [*existing, ".gitignore"], "synapsidian(setup): track existing vault files"
        ).sha
    return name, email, baseline


# --- register -----------------------------------------------------------------------


def cmd_register(vault_root: Path, obsidian_closed: bool = False) -> dict[str, Any]:
    """`obsidian_closed`: the user says Obsidian is closed, for systems where synapsidian can't check."""
    if not obsidian_installed():
        return {
            "ok": False,
            "error": f"Obsidian is not installed, or has never been opened ({HOST.registry} is missing)",
            "install": HOST.install,
        }
    if not vault_root.is_dir():
        return {"ok": False, "error": "vault does not exist yet; run apply first"}
    running = obsidian_running()
    if running or (running is None and not obsidian_closed):
        state = "is running" if running else "may be running (this system can't tell)"
        return {
            "ok": False,
            "running": running,
            "error": f"Obsidian {state}; it rewrites its registry from memory, so quit it ({HOST.quit}) "
            "and run register again"
            + ("" if running else " with --obsidian-closed")
            + ", or use 'Open folder as vault' in Obsidian instead",
        }
    registry = read_json(HOST.registry)
    registry = registry if isinstance(registry, dict) else {}
    vaults = registry.setdefault("vaults", {})
    if any(same_path(vault_root, v.get("path")) for v in vaults.values()):
        return {"ok": True, "registered": False, "reason": "already registered"}
    backup = None
    if HOST.registry.exists():
        backup = HOST.registry.with_name(f"obsidian.json.synapsidian-backup-{int(time.time())}")
        shutil.copy2(HOST.registry, backup)
    for entry in vaults.values():
        entry.pop("open", None)
    vaults[secrets.token_hex(8)] = {"path": str(vault_root), "ts": int(time.time() * 1000), "open": True}
    write_json(HOST.registry, registry)
    return {
        "ok": True,
        "registered": True,
        "registry": str(HOST.registry),
        "backup": str(backup) if backup else None,
        "open_with": HOST.open_command(f"obsidian://open?vault={quote(vault_root.name, safe='')}"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cmd", choices=["check", "apply", "register", "selftest", "extension"])
    parser.add_argument("--vault")
    parser.add_argument("--from", dest="source", help="extension: the add-on's extension directory")
    parser.add_argument("--data-dir")
    parser.add_argument("--name")
    parser.add_argument("--email")
    parser.add_argument(
        "--obsidian-closed",
        action="store_true",
        help="register: the user confirmed Obsidian is closed, where synapsidian can't check",
    )
    parser.add_argument(
        "--about",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="About.md field from the vault's schema (core: role, timezone, working_hours)",
    )
    args = parser.parse_args()

    vault_root = config.vault_path(args.vault)
    if vault_root is None:
        print(json.dumps({"ok": False, "error": "no vault path configured (plugin option vault_path)"}))
        sys.exit(2)
    if config.too_broad(vault_root):
        print(json.dumps({"ok": False, "error": f"{vault_root} can't be a vault: choose a folder of its own"}))
        sys.exit(2)
    try:
        match args.cmd:
            case "check":
                result = cmd_check(vault_root)
            case "apply":
                about = dict(pair.split("=", 1) for pair in args.about if "=" in pair)
                result = cmd_apply(vault_root, args.name, args.email, about, config.data_dir(args.data_dir))
            case "register":
                result = cmd_register(vault_root, args.obsidian_closed)
            case "selftest":
                result = cmd_selftest(vault_root)
            case "extension":
                if not args.source:
                    raise ValueError("extension needs --from <dir>")
                result = cmd_extension(vault_root, Path(args.source).expanduser(), config.data_dir(args.data_dir))
    except (ValueError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        print(json.dumps({"ok": False, "error": detail.strip()}))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
