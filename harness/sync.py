#!/usr/bin/env python3
"""Verteilt den geteilten Harness in die vier Repos und den Arbeitsordner.

Das Problem, das dieses Skript löst: Claude Code liest `.claude/` nur im
Ordner, in dem die Sitzung gestartet ist — plus `~/.claude`. Ein
`backend/.claude/settings.json` gilt also **nicht**, wenn jemand Claude in
`DHBW_APP/` startet. Und weil die vier Repos getrennte Git-Repositories
sind, kann kein Repo dem anderen etwas mitgeben.

Also: eine Quelle in `deployment/harness/` (versioniert, im Repo, das
ohnehin jeder hat) und ein Skript, das daraus erzeugt:

    DHBW_APP/.claude/        Hooks + Berechtigungen + geteilte Skills + CLAUDE.md
    <repo>/.claude/          dasselbe, je Repo passend

Aufruf:

    python deployment/harness/sync.py            # verteilen
    python deployment/harness/sync.py --check    # nur prüfen, Exit 1 bei Drift

Was das Skript **nicht** anfasst: die `AGENTS.md` der Repos, ihre eigenen
Skills und alles, was nicht in `harness/` steht. `enabledPlugins` und andere
eigene Schlüssel in einer `settings.json` bleiben erhalten — ersetzt werden
nur `permissions` und `hooks`.
"""

import json
import os
import sys

HARNESS = os.path.dirname(os.path.abspath(__file__))
DEPLOYMENT = os.path.dirname(HARNESS)
ROOT = os.path.dirname(DEPLOYMENT)

REPOS = ("backend", "frontend", "worker", "deployment")

# Welche Hook-Modi ein Ziel braucht. `lint` steht nur dort, wo es etwas tut —
# ein Prozessstart pro Edit für einen No-Op ist verschenkte Zeit.
HOOK_MODES = {
    "_root": ("pre", "bash", "lint", "stop"),
    "backend": ("pre", "bash", "lint", "stop"),
    "worker": ("pre", "bash", "lint", "stop"),
    "deployment": ("pre", "bash", "lint", "stop"),
    "frontend": ("pre", "bash", "stop"),
}

STATUS = {
    "pre": "Secret- und Migrationsschutz",
    "bash": "Secret-Schutz (Shell)",
    "lint": "Auto-Format",
    "stop": "Qualitaets-Gate",
}

EVENT = {
    "pre": "PreToolUse",
    "bash": "PreToolUse",
    "lint": "PostToolUse",
    "stop": "Stop",
}

# Ohne matcher laeuft ein Hook zu jedem Werkzeug — `stop` hat deshalb keinen.
MATCHER = {"pre": "Edit|Write", "bash": "Bash", "lint": "Edit|Write"}

TIMEOUT = {"pre": 15, "bash": 15, "lint": 90, "stop": 300}


def hook_entry(mode: str) -> dict:
    """Ein Hook-Eintrag für settings.json.

    Der Pfad geht über ``$CLAUDE_PROJECT_DIR``, nicht relativ: ein relatives
    ``.claude/hooks/...`` schlägt still fehl, sobald das Arbeitsverzeichnis
    nicht die Projektwurzel ist — und ein stiller Fehlschlag sieht aus wie
    ein Hook, den es nicht gibt.
    """
    script = '"$CLAUDE_PROJECT_DIR/.claude/hooks/agent_guard.py"'
    command = (
        "P=$(command -v python || command -v python3); "
        f'[ -n "$P" ] && "$P" {script} {mode}; exit 0'
    )
    entry = {
        "hooks": [
            {
                "type": "command",
                "command": command,
                "timeout": TIMEOUT[mode],
                "statusMessage": STATUS[mode],
            }
        ]
    }
    if mode in MATCHER:
        entry["matcher"] = MATCHER[mode]
    return entry


def hooks_for(target: str) -> dict:
    hooks = {}
    for mode in HOOK_MODES[target]:
        hooks.setdefault(EVENT[mode], []).append(hook_entry(mode))
    return hooks


def load_permissions() -> dict:
    with open(os.path.join(HARNESS, "permissions.json"), encoding="utf-8") as handle:
        return json.load(handle)["permissions"]


def siblings(repo: str) -> list:
    """Die anderen drei Repos als zusätzliche Arbeitsverzeichnisse.

    Nötig, weil die Arbeit über Repogrenzen geht: ein neuer Endpunkt braucht
    `frontend/src/api/*.ts`, jede Architekturentscheidung braucht
    `deployment/docs/adr/`.
    """
    return [f"../{other}" for other in REPOS if other != repo]


def desired_settings(target: str, existing: dict) -> dict:
    settings = dict(existing)
    permissions = load_permissions()
    if target != "_root":
        permissions = dict(permissions)
        permissions["additionalDirectories"] = siblings(target)
    settings["permissions"] = permissions
    settings["hooks"] = hooks_for(target)
    settings.setdefault("enabledPlugins", {"context7@claude-plugins-official": True})
    return settings


def read_json(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def write_if_changed(path: str, content: str, check: bool, changed: list) -> None:
    current = None
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            current = handle.read()
    if current == content:
        return
    changed.append(os.path.relpath(path, ROOT))
    if check:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def copy_tree(source: str, destination: str, check: bool, changed: list) -> None:
    for folder, _, files in os.walk(source):
        for name in files:
            source_file = os.path.join(folder, name)
            relative = os.path.relpath(source_file, source)
            with open(source_file, encoding="utf-8") as handle:
                write_if_changed(
                    os.path.join(destination, relative), handle.read(), check, changed
                )


def sync_target(target: str, base: str, check: bool, changed: list) -> bool:
    """Ein Ziel abgleichen. Gibt zurueck, ob es ueberhaupt geprueft wurde.

    Beim Pruefen werden Ziele ohne `.claude` uebersprungen statt als
    Abweichung gemeldet: in der CI ist nur ein Repository ausgecheckt, und
    der Arbeitsordner darueber existiert dort gar nicht. Beim Verteilen
    wird ein fehlendes `.claude` dagegen angelegt.
    """
    claude = os.path.join(base, ".claude")
    if check and not os.path.isdir(claude):
        return False

    with open(os.path.join(HARNESS, "agent_guard.py"), encoding="utf-8") as handle:
        write_if_changed(
            os.path.join(claude, "hooks", "agent_guard.py"),
            handle.read(),
            check,
            changed,
        )

    copy_tree(
        os.path.join(HARNESS, "skills"),
        os.path.join(claude, "skills"),
        check,
        changed,
    )

    settings_path = os.path.join(claude, "settings.json")
    settings = desired_settings(target, read_json(settings_path))
    write_if_changed(
        settings_path,
        json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
        check,
        changed,
    )

    if target == "_root":
        with open(
            os.path.join(HARNESS, "root", "CLAUDE.md"), encoding="utf-8"
        ) as handle:
            write_if_changed(
                os.path.join(base, "CLAUDE.md"), handle.read(), check, changed
            )
    return True


def main() -> int:
    check = "--check" in sys.argv
    changed = []

    geprueft = 0
    geprueft += sync_target("_root", ROOT, check, changed)
    for repo in REPOS:
        base = os.path.join(ROOT, repo)
        if not os.path.isdir(base):
            print(f"! {repo} fehlt in {ROOT} — uebersprungen")
            continue
        geprueft += sync_target(repo, base, check, changed)

    if check and not geprueft:
        print("Kein einziges Ziel mit .claude gefunden — nichts geprueft.")
        return 1

    if not changed:
        print("Harness aktuell.")
        return 0
    verb = "abweichend" if check else "geschrieben"
    for path in changed:
        print(f"  {verb}: {path}")
    if check:
        print(
            f"\n{len(changed)} Datei(en) weichen ab. "
            "Beheben: python deployment/harness/sync.py"
        )
        return 1
    print(f"\n{len(changed)} Datei(en) aktualisiert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
