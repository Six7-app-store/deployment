#!/usr/bin/env python3
"""Hook-Helfer für Claude Code im deployment-Repo.

Ein Modus, liest das Hook-JSON von stdin:

    pre    PreToolUse auf Edit|Write — blockt Schreibzugriffe auf
           Dateien, die Geheimnisse tragen: die echte `.env` und alles
           auf `*.pem`. Gepflegt wird `.env.example`, nie `.env`.

Bewusst fail-open bei Fehlern: ein defekter Hook darf die Sitzung nicht
blockieren. Der harte Schutz ist `.gitignore` plus der Secret-Scan in
der Pipeline — dieser Hook fängt den Fehler nur früher ab.

Kein jq: das ist auf den Entwicklungsrechnern nicht überall installiert,
python dagegen zwangsläufig.
"""

import json
import sys

REASON = (
    "Diese Datei traegt Geheimnisse und wird nicht vom Agenten geschrieben. "
    "Gepflegt wird .env.example (ohne Werte); die echte .env und alle "
    "*.pem-Dateien setzt eine Person von Hand."
)


def hook_input() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def is_secret_file(path: str) -> bool:
    # Windows-Backslashes zu Slashes, damit das Muster beide Seiten trifft.
    normalized = path.replace("\\", "/")
    name = normalized.rsplit("/", 1)[-1]
    if name.endswith(".pem"):
        return True
    # .env.example ist der gepflegte Teil und bleibt erlaubt.
    return name == ".env" or (name.startswith(".env.") and name != ".env.example")


def block_secret(data: dict) -> None:
    tool_input = data.get("tool_input") or {}
    path = tool_input.get("file_path") or ""
    if not path or not is_secret_file(path):
        return
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": REASON,
                }
            }
        )
    )


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if mode == "pre":
            block_secret(hook_input())
    except Exception:
        pass


if __name__ == "__main__":
    main()
