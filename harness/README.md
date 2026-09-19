# Claude-Code-Harness

Quelle für alles, was in den vier Repos gleich aussehen muss: Hooks,
Berechtigungen, geteilte Skills und die `CLAUDE.md` des Arbeitsordners.

## Warum das hier liegt und nicht je Repo

Zwei Einschränkungen, die zusammen dieses Verzeichnis erzwingen:

1. **Claude Code liest `.claude/` nur im Ordner, in dem die Sitzung gestartet
   wurde** — plus `~/.claude`. Unterordner werden nicht gescannt. Wer Claude in
   `DHBW_APP/` startet, arbeitet also ohne `backend/.claude/settings.json`:
   ohne Hooks, ohne deny-Regeln. Und jeder von uns hat diesen Ordner, weil die
   vier Repos nur zusammen laufen.
2. **Die vier Repos sind getrennte Git-Repositories.** Keines kann dem anderen
   etwas mitgeben. Vorher lag in drei Repos eine eigene `agent_guard.py`; die
   drei Kopien waren bereits auseinandergedriftet, ohne dass es jemand gemerkt
   hätte.

Also: eine Quelle in dem Repo, das ohnehin jeder auscheckt, und ein Skript,
das sie an die fünf Stellen verteilt.

## Inhalt

| Datei | Was daraus wird |
|---|---|
| `agent_guard.py` | `<repo>/.claude/hooks/agent_guard.py` und `DHBW_APP/.claude/hooks/agent_guard.py` |
| `permissions.json` | der `permissions`-Block jeder `settings.json` |
| `skills/` | geteilte Skills, in jedes Repo und in den Arbeitsordner |
| `root/CLAUDE.md` | `DHBW_APP/CLAUDE.md` |
| `sync.py` | das Verteilen selbst |

## Benutzen

```bash
make harness-sync     # verteilen
make harness-check    # nur prüfen, Exit 1 bei Drift
```

Beides auch direkt: `python harness/sync.py [--check]`.

**Nach jedem `git pull` im `deployment`-Repo einmal `make harness-sync`.** Das
Skript schreibt nur, was sich unterscheidet, und ist gefahrlos wiederholbar.

## Testen

```bash
make harness-test     # 30 Tests, nur Standardbibliothek, ohne Docker
```

Geprüft wird die Entscheidungslogik: Secret-Erkennung, Repo-Zuordnung,
Pfadübersetzung in den Container, die `pre`-Entscheidungen und der
Schleifenschutz im Stop-Hook. Dazu ein Test, der die verteilten Kopien
Zeichen für Zeichen gegen die Quelle hält — ein vergessenes `harness-sync`
fällt damit auf, nicht erst im nächsten Agentenlauf.

Derselbe Lauf hängt als eigener Job `harness` in
`.github/workflows/infra-qa.yml`. Dort ist nur `deployment` ausgecheckt;
der Kopien-Test prüft deshalb, was vorhanden ist, und wertet fehlende
Nachbarrepos nicht als Fehler. Aus demselben Grund überspringt
`sync.py --check` Ziele ohne `.claude` statt sie als Abweichung zu melden.

Die drei anderen Repositories prüfen ihre eigenen Kopien selbst: jedes hat
ein `.github/workflows/harness-check.yml`, das dieses Repository klont und
den Hook-Helfer sowie die geteilten Skills dagegen hält. Verglichen wird
gegen den gleichnamigen Branch, falls es ihn hier gibt, sonst gegen den
Standardbranch — sonst wäre jede Harness-Änderung so lange rot, bis sie in
beiden Repositories denselben Weg gegangen ist.

## Voraussetzung: Git Bash

Claude Code führt `command`-Hooks unter Windows über Git Bash aus (und fällt
nur auf PowerShell zurück, wenn kein Git Bash installiert ist). Die
Hook-Kommandos sind deshalb POSIX-Shell. Das passt zum restlichen Projekt —
`MSYS_NO_PATHCONV=1` in `AGENTS.md` setzt Git Bash ohnehin voraus.

## Ändern

Immer hier, nie in einer erzeugten Kopie. Eine Änderung an
`backend/.claude/hooks/agent_guard.py` überlebt den nächsten Sync nicht.

`sync.py` ersetzt in einer `settings.json` nur `permissions` und `hooks`.
Alles andere — `enabledPlugins`, eigene Schlüssel — bleibt stehen. Die
repo-eigenen Skills unter `<repo>/.claude/skills/` fasst es nicht an; die
gehören dem Repo und sind dort richtig.

## Die drei Ebenen

Sie verstärken sich gegenseitig, statt dasselbe dreimal zu sagen:

| Ebene | Wo | Wirkung |
|---|---|---|
| `AGENTS.md` | je Repo | Begründung und Kontext. Überzeugt, hindert nicht |
| Hooks | `agent_guard.py` | erklärt beim Zugriff, warum etwas tabu ist; formatiert; hält am Ende die Gates |
| `permissions` | `permissions.json` | hart. Kein Prod-Deploy, kein Force-Push, keine Secrets — unabhängig davon, was im Kontext steht |

Der Hook ist bewusst **fail-open**: kein Docker, kaputtes JSON, Container aus
→ still Exit 0. Ein Hook, der die Sitzung blockiert, weil er selbst defekt
ist, kostet mehr als er schützt. Die harte Grenze sind die deny-Regeln, das
harte Qualitätsgate ist die CI.

## Was der Stop-Hook kostet

Im Repo gestartet: das Gate dieses Repos, immer. Im Arbeitsordner gestartet:
nur die Repos mit uncommitteten Änderungen — sonst zahlt jede Antwort einen
vollen Typecheck über alles.

Der Hook prüft `stop_hook_active` und blockt nie zweimal hintereinander.
Ohne diese Prüfung hängt eine Sitzung an einem Fehler fest, den Claude nicht
beheben kann (etwa Lint-Rot in einer Datei, die niemand angefasst hat).

## `.claude/` ist vom Linting ausgenommen

In `backend/pyproject.toml` und `worker/pyproject.toml` steht `.claude` in den
Ausschlüssen von ruff, black und isort. Grund: die verteilte Kopie des Hooks
ist kein Anwendungscode. Ohne den Ausschluss blockiert ein Stilbefund in
Harness-Code das Gate eines Repos, das damit nichts zu tun hat — genau einmal
passiert, direkt beim Bau dieses Verzeichnisses.
