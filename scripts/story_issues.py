#!/usr/bin/env python3
"""Offene User Stories aus der Story-Matrix als Issues in deployment anlegen.

    python scripts/story_issues.py             # Trockenlauf: was fehlt, was da ist
    python scripts/story_issues.py --anlegen   # fehlende Issues und Labels anlegen

Oder ueber make: `make story-issues`, `make story-issues-anlegen`.

Quelle ist die neueste `docs/user-story-audit-*.md`, Abschnitt
„Vollständige Story-Matrix". Ein Issue entsteht fuer jede Story mit Status
T (teilweise) oder O (offen); U und D brauchen keins (ADR 0016).

Idempotent: erkannt wird eine Story am Titelanfang `US-NN:` unter dem Label
`user-story`, offen oder geschlossen. Was es gibt, wird nicht angefasst —
auch nicht, wenn sich die Matrix geaendert hat. Ein Issue kann inzwischen
Kommentare, einen Plan und Entscheidungen tragen, die eine Neufassung aus
der Momentaufnahme ueberschreiben wuerde.

Ziel ist ausschliesslich Six7-app-store/deployment. Das Skript ruft `gh`
selbst auf; der Bash-Hook sieht diese Aufrufe nicht, deshalb steht das
Ziel hier fest und ist nicht ueberschreibbar.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

GH_REPO = "Six7-app-store/deployment"
OWNER = "Six7-app-store"
STORY_LABEL = "user-story"

# Auf welchem Branch Links in ein Repo zeigen. Die Stack-Repos arbeiten auf
# develop (ADR 0013), die App-Repos nur auf main.
BRANCH = {"backend": "develop", "frontend": "develop", "worker": "develop", "deployment": "develop"}

STATUS = {"U": "umgesetzt", "T": "teilweise umgesetzt", "O": "offen / nicht nachgewiesen", "D": "als Entscheidung dokumentiert"}

LABELS = {
    STORY_LABEL: ("1d76db", "User Story aus der Projektkonzeption (ADR 0016)"),
    "geplant": ("0e8a16", "Plan steht als Kommentar im Issue (/issue-planen)"),
}
REPO_FARBE = "c5def5"
PLAN_FARBE = "fbca04"

_spec = importlib.util.spec_from_file_location("docs_check", os.path.join(HERE, "docs_check.py"))
docs_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(docs_check)


def lesen(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def matrix() -> tuple:
    """(Audit-Datei, [Story]) — eine Story je Zeile der Story-Matrix."""
    datei, _ = docs_check.story_matrix()
    if not datei:
        return "", []
    stories, im_abschnitt = [], False
    for _, zeile in docs_check.ohne_codebloecke(lesen(datei)):
        if zeile.startswith("## "):
            im_abschnitt = "Story-Matrix" in zeile
            continue
        if not (im_abschnitt and zeile.startswith("| US-")):
            continue
        spalten = [s.strip() for s in zeile.strip().strip("|").split("|")]
        if len(spalten) != 5:
            continue
        kennung, anforderung, status, befund, plan = spalten
        stories.append({
            "id": kennung,
            "anforderung": anforderung,
            "status": status,
            "befund": befund,
            "pakete": re.findall(r"P\d{2}", plan),
        })
    return datei, stories


def github_link(ziel: str, quelle: str) -> tuple:
    """(URL, Repo) fuer einen relativen Link aus einer Datei unter docs/."""
    if re.match(r"^[a-z][a-z0-9+.-]*:", ziel, re.IGNORECASE):
        return ziel, ""
    pfad, _, fragment = ziel.partition("#")
    absolut = os.path.normpath(os.path.join(os.path.dirname(quelle), pfad))
    relativ = os.path.relpath(absolut, os.path.dirname(REPO)).replace("\\", "/")
    repo, _, rest = relativ.partition("/")
    url = f"https://github.com/{OWNER}/{repo}/blob/{BRANCH.get(repo, 'main')}/{rest}"
    return url + (f"#{fragment}" if fragment else ""), repo


def umgeschrieben(text: str, quelle: str) -> tuple:
    """Text mit absoluten GitHub-Links und die Repos, auf die er zeigt."""
    repos = set()

    def ersetzen(treffer):
        url, repo = github_link(treffer.group(2), quelle)
        if repo:
            repos.add(repo)
        return f"[{treffer.group(1)}]({url})"

    return re.sub(r"\[([^\]]*)\]\(([^)\s]+)\)", ersetzen, text), repos


def paket_titel() -> dict:
    """{P05: (Ueberschrift, Datei)} aus dem neuesten Umsetzungsplan."""
    kandidaten = sorted(f for f in os.listdir(os.path.join(REPO, "docs")) if f.startswith("user-story-umsetzungsplan-"))
    if not kandidaten:
        return {}
    datei = os.path.join(REPO, "docs", kandidaten[-1])
    result = {}
    for _, zeile in docs_check.ohne_codebloecke(lesen(datei)):
        treffer = re.match(r"^##\s+(P\d{2})\b(.*)$", zeile)
        if treffer:
            result[treffer.group(1)] = (zeile[3:].strip(), datei)
    return result


def titel(story: dict) -> str:
    text = story["anforderung"].rstrip(".")
    kopf = f"{story['id']}: {text}"
    return kopf if len(kopf) <= 110 else kopf[:107].rstrip() + "…"


def koerper(story: dict, quelle: str, pakete: dict) -> tuple:
    befund, repos = umgeschrieben(story["befund"], quelle)
    stand = os.path.basename(quelle)
    audit_url, _ = github_link(os.path.basename(quelle), quelle)
    zeilen = [
        f"**Anforderung:** {story['anforderung']}",
        "",
        f"**Befund im Audit** ([{stand}]({audit_url})): {STATUS[story['status']]}. {befund}",
        "",
    ]
    for paket in story["pakete"]:
        if paket in pakete:
            ueberschrift, datei = pakete[paket]
            url, _ = github_link(f"{os.path.basename(datei)}#{docs_check.slug(ueberschrift)}", datei)
            zeilen.append(f"**Arbeitspaket:** [{ueberschrift}]({url}) — Schritte, Abnahme und Verifikation stehen dort.")
    if repos:
        zeilen += ["", f"**Belege in:** {', '.join(sorted(repos))}"]
    zeilen += [
        "",
        "---",
        "",
        "Der Befund ist eine Momentaufnahme. Vor jeder Umsetzung prüft "
        "`/issue-planen` den Ist-Stand gegen den aktuellen Code und schreibt "
        "den Plan als Kommentar hierher. Geschlossen wird das Issue, wenn die "
        "Abnahmekriterien des Arbeitspakets erfüllt und belegt sind.",
        "",
        f"<!-- story-issues: {story['id']} -->",
    ]
    return "\n".join(zeilen), repos


def gh(*args: str) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, encoding="utf-8", errors="replace", timeout=60)
    if result.returncode != 0:
        raise SystemExit(f"gh {' '.join(args[:3])} …: {result.stderr.strip()}")
    return result.stdout


def vorhandene_issues() -> dict:
    daten = json.loads(gh("issue", "list", "-R", GH_REPO, "--label", STORY_LABEL, "--state", "all",
                          "--limit", "500", "--json", "number,title,state"))
    result = {}
    for issue in daten:
        treffer = re.match(r"^(US-\d{2,3})\b", issue["title"])
        if treffer:
            result[treffer.group(1)] = issue
    return result


def labels_sicherstellen(gebraucht: dict) -> None:
    vorhanden = {l["name"] for l in json.loads(gh("label", "list", "-R", GH_REPO, "--limit", "200", "--json", "name"))}
    for name, (farbe, beschreibung) in sorted(gebraucht.items()):
        if name not in vorhanden:
            gh("label", "create", name, "-R", GH_REPO, "--color", farbe, "--description", beschreibung)
            print(f"  Label angelegt: {name}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    anlegen = "--anlegen" in sys.argv
    quelle, stories = matrix()
    if not stories:
        print("Keine Story-Matrix unter docs/user-story-audit-*.md gefunden.")
        return 1

    if json.loads(gh("repo", "view", GH_REPO, "--json", "hasIssuesEnabled"))["hasIssuesEnabled"] is not True:
        print(f"Issues sind in {GH_REPO} abgeschaltet. Einschalten (Person, Repo-Einstellungen) und neu starten.")
        return 1

    pakete = paket_titel()
    vorhanden = vorhandene_issues()
    fehlend = []
    print(f"Quelle: {os.path.relpath(quelle, REPO)}\n")
    for story in stories:
        offen = story["status"] in "TO"
        issue = vorhanden.get(story["id"])
        if issue:
            stand = f"#{issue['number']} ({issue['state'].lower()})"
        elif offen:
            stand = "fehlt -> wird angelegt" if anlegen else "fehlt"
            fehlend.append(story)
        else:
            stand = "kein Issue noetig"
        print(f"  {story['id']}  {story['status']}  {','.join(story['pakete']) or '-':8}  {stand}")

    print(f"\n{len(fehlend)} fehlend, {len(vorhanden)} vorhanden.")
    if not fehlend or not anlegen:
        if fehlend:
            print("Anlegen mit: make story-issues-anlegen")
        return 0

    gebraucht = dict(LABELS)
    entwuerfe = []
    for story in fehlend:
        text, repos = koerper(story, quelle, pakete)
        labels = [STORY_LABEL] + [f"plan:{p}" for p in story["pakete"]] + [f"repo:{r}" for r in sorted(repos)]
        for paket in story["pakete"]:
            gebraucht[f"plan:{paket}"] = (PLAN_FARBE, (pakete.get(paket, (paket, ""))[0])[:100])
        for repo in repos:
            gebraucht[f"repo:{repo}"] = (REPO_FARBE, f"Betrifft {OWNER}/{repo}")
        entwuerfe.append((story, text, labels))

    labels_sicherstellen(gebraucht)
    for story, text, labels in entwuerfe:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as handle:
            handle.write(text)
            body = handle.name
        try:
            args = ["issue", "create", "-R", GH_REPO, "--title", titel(story), "--body-file", body]
            for label in labels:
                args += ["--label", label]
            print(f"  {story['id']}: {gh(*args).strip()}")
        finally:
            os.unlink(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
