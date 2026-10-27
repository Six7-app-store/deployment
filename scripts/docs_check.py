#!/usr/bin/env python3
"""Prueft, dass Doku, Diagramme, ADR-Verzeichnis und Issues zusammenpassen.

    python scripts/docs_check.py                   # wie make docs-check
    python scripts/docs_check.py --mermaid=on      # wie die CI: Diagramme rendern
    python scripts/docs_check.py --issues          # wie die CI: Stories gegen Issues

Warum es das gibt: Doku veraltet nicht mit einem Knall, sondern leise. Ein
ADR fehlt im Verzeichnis, ein Link zeigt auf eine verschobene Datei, ein
Diagramm parst nicht mehr, und niemand merkt es, bis jemand danach handelt.
Gefunden beim Bau: ADR 0014 lag im Repo, stand aber nicht im Verzeichnis.

Geprueft wird:

    adr       Nummern lueckenlos, Kopfzeile passt zur Datei, Status gueltig,
              jedes ADR genau einmal im Verzeichnis mit demselben Status.
    links     Relative Links und Anker in allen Markdown-Dateien dieses
              Repos. Links in ein Nachbarrepo bleiben ungeprueft (siehe
              pruefe_links).
    doc-map   harness/doc-map.json: jede Doku existiert, jedes Muster zeigt
              noch auf mindestens eine Datei.
    mermaid   Jeder ```mermaid-Block rendert (mermaid-cli in Docker).
    issues    Jede offene Story (Status T oder O) aus der Story-Matrix hat
              genau ein Issue; kein Issue nennt eine unbekannte Story.

Nur Standardbibliothek. Exit 1, sobald etwas nicht passt.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.path.dirname(REPO)

GH_REPO = "Six7-app-store/deployment"
STORY_LABEL = "user-story"
MERMAID_IMAGE = "minlag/mermaid-cli:11.17.1"
SKIP_DIRS = {".git", ".claude", "node_modules", ".terraform", "roles_external", ".worktrees"}
ADR_STATUS = re.compile(r"^(Vorschlag|Angenommen|Abgelehnt|Abgelöst durch ADR-\d{4})$")

fehler = []


def melden(ort: str, text: str) -> None:
    fehler.append(f"{ort}: {text}")


def rel(path: str) -> str:
    return os.path.relpath(path, REPO).replace("\\", "/")


def lesen(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def markdown_dateien() -> list:
    result = []
    for folder, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        result.extend(os.path.join(folder, name) for name in files if name.endswith(".md"))
    return sorted(result)


def ohne_codebloecke(text: str) -> list:
    """(Zeilennummer, Zeile) ausserhalb von ```-Bloecken."""
    zeilen, im_block = [], False
    for nummer, zeile in enumerate(text.splitlines(), 1):
        if zeile.lstrip().startswith("```"):
            im_block = not im_block
            continue
        if not im_block:
            zeilen.append((nummer, zeile))
    return zeilen


# ----------------------------------------------------------------
# adr
# ----------------------------------------------------------------
def adr_status(text: str) -> str:
    treffer = re.search(r"^\*\*Status:\*\*\s*(.+?)\s*$", text, re.MULTILINE)
    return treffer.group(1) if treffer else ""


def pruefe_adr() -> None:
    ordner = os.path.join(REPO, "docs", "adr")
    dateien = sorted(n for n in os.listdir(ordner) if re.match(r"^\d{4}-.+\.md$", n))
    nummern = [int(n[:4]) for n in dateien]
    erwartet = list(range(1, len(nummern) + 1))
    if nummern != erwartet:
        melden("docs/adr", f"Nummern nicht lueckenlos ab 0001: {nummern}")

    status = {}
    for name in dateien:
        text = lesen(os.path.join(ordner, name))
        kopf = text.splitlines()[0] if text else ""
        if not kopf.startswith(f"# {name[:4]} — "):
            melden(f"docs/adr/{name}:1", f"Kopfzeile muss mit '# {name[:4]} — ' beginnen")
        wert = adr_status(text)
        if not ADR_STATUS.match(wert):
            melden(f"docs/adr/{name}", f"Status '{wert}' ungueltig (Vorschlag | Angenommen | Abgelehnt | Abgelöst durch ADR-NNNN)")
        status[name] = wert

    readme = lesen(os.path.join(ordner, "README.md"))
    eintraege = {}
    for nummer, zeile in ohne_codebloecke(readme):
        treffer = re.match(r"^\|\s*\[(\d{4})\]\(([^)]+)\)\s*\|.*\|\s*([^|]+?)\s*\|\s*$", zeile)
        if not treffer:
            continue
        ziel = treffer.group(2)
        if ziel in eintraege:
            melden(f"docs/adr/README.md:{nummer}", f"{ziel} steht doppelt im Verzeichnis")
        eintraege[ziel] = (nummer, treffer.group(1), treffer.group(3))
    for name in dateien:
        if name not in eintraege:
            melden("docs/adr/README.md", f"{name} fehlt im Verzeichnis")
            continue
        nummer, kennung, wert = eintraege[name]
        if kennung != name[:4]:
            melden(f"docs/adr/README.md:{nummer}", f"Nummer {kennung} zeigt auf {name}")
        if wert != status[name]:
            melden(f"docs/adr/README.md:{nummer}", f"Status '{wert}', im ADR steht '{status[name]}'")
    for ziel, (nummer, _, _) in eintraege.items():
        if ziel not in dateien:
            melden(f"docs/adr/README.md:{nummer}", f"{ziel} gibt es nicht")


# ----------------------------------------------------------------
# links
# ----------------------------------------------------------------
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|!\[[^\]]*\]\(([^)\s]+)\)")


def slug(ueberschrift: str) -> str:
    """Der Anker, den GitHub fuer eine Ueberschrift vergibt."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", ueberschrift)
    text = text.replace("`", "").strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


anker_cache = {}


def anker(path: str) -> set:
    if path not in anker_cache:
        gesehen, result = {}, set()
        for _, zeile in ohne_codebloecke(lesen(path)):
            treffer = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", zeile)
            if not treffer:
                continue
            basis = slug(treffer.group(1))
            anzahl = gesehen.get(basis, 0)
            result.add(basis if anzahl == 0 else f"{basis}-{anzahl}")
            gesehen[basis] = anzahl + 1
        anker_cache[path] = result
    return anker_cache[path]


def pruefe_links() -> None:
    for datei in markdown_dateien():
        for nummer, zeile in ohne_codebloecke(lesen(datei)):
            zeile = re.sub(r"`[^`]*`", "", zeile)
            for treffer in LINK.finditer(zeile):
                ziel = treffer.group(1) or treffer.group(2)
                if re.match(r"^[a-z][a-z0-9+.-]*:", ziel, re.IGNORECASE):
                    continue
                pfad, _, fragment = ziel.partition("#")
                ort = f"{rel(datei)}:{nummer}"
                absolut = os.path.normpath(os.path.join(os.path.dirname(datei), pfad)) if pfad else datei
                # Links in ein Nachbarrepo bleiben ungeprueft. Ob sie
                # aufloesen, haengt davon ab, welcher Branch dort gerade
                # ausgecheckt ist, und die CI hat das Nachbarrepo gar nicht.
                # Ein Check, der lokal anders urteilt als in der CI, ist
                # schlimmer als keiner.
                if os.path.commonpath([absolut, REPO]) != REPO:
                    continue
                if not os.path.exists(absolut):
                    melden(ort, f"Link zeigt ins Leere: {ziel}")
                    continue
                if fragment and absolut.endswith(".md") and os.path.isfile(absolut):
                    if fragment.lower() not in anker(absolut):
                        melden(ort, f"Anker #{fragment} gibt es in {os.path.basename(absolut)} nicht")


# ----------------------------------------------------------------
# doc-map
# ----------------------------------------------------------------
def git_dateien(repo_dir: str) -> list:
    try:
        result = subprocess.run(
            ["git", "-C", repo_dir, "ls-files"], capture_output=True, encoding="utf-8", errors="replace", timeout=30
        )
        return result.stdout.splitlines() if result.returncode == 0 else []
    except Exception:
        return []


def pruefe_doc_map() -> None:
    import fnmatch

    pfad = os.path.join(REPO, "harness", "doc-map.json")
    try:
        regeln = json.loads(lesen(pfad))["regeln"]
    except Exception as error:
        melden("harness/doc-map.json", f"nicht lesbar: {error}")
        return
    dateien = {}
    for nummer, regel in enumerate(regeln, 1):
        ort = f"harness/doc-map.json Regel {nummer}"
        repo = regel.get("repo")
        if repo not in ("backend", "frontend", "worker", "deployment"):
            melden(ort, f"unbekanntes Repo '{repo}'")
            continue
        if not regel.get("pfade") or not regel.get("doku"):
            melden(ort, "pfade und doku duerfen nicht leer sein")
        for doku in regel.get("doku", []):
            if not os.path.isfile(os.path.join(REPO, doku)):
                melden(ort, f"Doku {doku} gibt es nicht")
        repo_dir = REPO if repo == "deployment" else os.path.join(ROOT, repo)
        if not os.path.isdir(os.path.join(repo_dir, ".git")) and not os.path.isfile(os.path.join(repo_dir, ".git")):
            continue
        if repo not in dateien:
            dateien[repo] = git_dateien(repo_dir)
        for muster in regel.get("pfade", []):
            if not any(fnmatch.fnmatchcase(d, muster) for d in dateien[repo]):
                melden(ort, f"Muster {repo}:{muster} trifft keine Datei mehr")


# ----------------------------------------------------------------
# mermaid
# ----------------------------------------------------------------
def docker_da() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except Exception:
        return False


def pruefe_mermaid(modus: str) -> None:
    mit_diagramm = [d for d in markdown_dateien() if "```mermaid" in lesen(d)]
    if not mit_diagramm or modus == "off":
        return
    if not docker_da():
        if modus == "on":
            melden("mermaid", "Docker fehlt, Diagramme nicht geprueft")
        else:
            # Ausgaben ohne Umlaute und Gedankenstriche: die Windows-Konsole
            # laeuft nicht zwangslaeufig auf UTF-8.
            print(f"Hinweis: Docker laeuft nicht, {len(mit_diagramm)} Datei(en) mit Mermaid ungeprueft. Die CI prueft sie.")
        return
    for datei in mit_diagramm:
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(datei, os.path.join(tmp, "in.md"))
            # Die Ausgabe landet im Container unter /tmp: ein Schreibzugriff
            # auf den Mount scheitert unter Linux an der Benutzerkennung.
            result = subprocess.run(
                ["docker", "run", "--rm", "-v", f"{tmp}:/data:ro", MERMAID_IMAGE,
                 "-i", "/data/in.md", "-o", "/tmp/out.md", "-q"],
                capture_output=True, encoding="utf-8", errors="replace", timeout=300,
            )
        if result.returncode != 0:
            letzte = (result.stderr or result.stdout).strip().splitlines()[-3:]
            melden(rel(datei), "Mermaid rendert nicht: " + " | ".join(letzte))


# ----------------------------------------------------------------
# issues
# ----------------------------------------------------------------
def story_matrix() -> tuple:
    """(Datei, {US-ID: Status}) aus der neuesten Story-Matrix."""
    kandidaten = sorted(glob.glob(os.path.join(REPO, "docs", "user-story-audit-*.md")))
    if not kandidaten:
        return "", {}
    datei = kandidaten[-1]
    stories, im_abschnitt = {}, False
    for _, zeile in ohne_codebloecke(lesen(datei)):
        if zeile.startswith("## "):
            im_abschnitt = "Story-Matrix" in zeile
            continue
        treffer = re.match(r"^\|\s*(US-\d{2,3})\s*\|[^|]*\|\s*([UTOD])\s*\|", zeile)
        if im_abschnitt and treffer:
            stories[treffer.group(1)] = treffer.group(2)
    return datei, stories


def pruefe_issues() -> None:
    datei, stories = story_matrix()
    if not stories:
        melden("issues", "keine Story-Matrix unter docs/user-story-audit-*.md gefunden")
        return
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "-R", GH_REPO, "--label", STORY_LABEL, "--state", "all",
             "--limit", "500", "--json", "number,title,state"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=60,
        )
    except Exception as error:
        melden("issues", f"gh nicht aufrufbar: {error}")
        return
    if result.returncode != 0:
        melden("issues", f"gh issue list scheiterte: {result.stderr.strip()}")
        return
    je_story = {}
    for issue in json.loads(result.stdout or "[]"):
        treffer = re.match(r"^(US-\d{2,3})\b", issue["title"])
        if not treffer:
            melden(f"Issue #{issue['number']}", "Label user-story, aber Titel beginnt nicht mit US-NN")
            continue
        je_story.setdefault(treffer.group(1), []).append(issue["number"])
    quelle = rel(datei)
    for story, status in sorted(stories.items()):
        nummern = je_story.get(story, [])
        if status in "TO" and not nummern:
            melden(quelle, f"{story} (Status {status}) hat kein Issue — /stories-zu-issues")
        if len(nummern) > 1:
            melden(quelle, f"{story} hat mehrere Issues: {nummern}")
    for story, nummern in sorted(je_story.items()):
        if story not in stories:
            melden(f"Issue #{nummern[0]}", f"{story} steht nicht in {quelle}")


# ----------------------------------------------------------------
def main() -> int:
    mermaid = "auto"
    for arg in sys.argv[1:]:
        if arg.startswith("--mermaid="):
            mermaid = arg.split("=", 1)[1]
    pruefe_adr()
    pruefe_links()
    pruefe_doc_map()
    pruefe_mermaid(mermaid)
    if "--issues" in sys.argv:
        pruefe_issues()

    if fehler:
        for zeile in fehler:
            print(f"FEHLER {zeile}")
        print(f"\n{len(fehler)} Befund(e). Doku nachziehen, nicht den Check.")
        return 1
    print("Doku-Check gruen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
