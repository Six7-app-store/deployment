# 0010 — Jeder Betreiber rollt Staging und Produktion aus seinem eigenen Forgejo aus

**Status:** Vorschlag — löst bei Annahme ADR-0002 ab
**Datum:** 27.09.2026
**Beteiligt:** Projektteam; Anlass ist die Rückmeldung eines Stakeholders (Mail, September 2026)

## Kontext

ADR-0002 (18.09.2026) hat den Staging-Deploy von einer Forgejo-Instanz auf
einen self-hosted GitHub-Runner verlegt. Gründe dort: Forgejo ist ein zweiter
Dienst mit eigener VM, Caddy, Pull-Mirror und Benutzerverwaltung, und ein
Mirror-Sync löst in Forgejo keine Actions zuverlässig aus — der Deploy war
faktisch immer ein `workflow_dispatch` von Hand. Umgesetzt in `52d931f`, der
`.forgejo/workflows/staging.yml` entfernt hat.

Eine Anforderung, die ADR-0002 nicht kannte, steht in der Rückmeldung des
Stakeholders:

- Der AppStore soll **mehrere Betreiber** haben, die jeweils eigene Staging-
  und Produktionsinstallationen betreiben — **ohne ihre Secrets zu GitHub
  hochzuladen**.
- Nachvollziehbar soll sein, **wer** in der Organisation die letzte
  Einrichtung ausgelöst hat und **warum**.
- Zitiert wird die GitHub-Dokumentation: „We recommend that you only use
  self-hosted runners with private repositories." Alle Repositories des
  Projekts sind öffentlich.
- Gewünscht ist, auch das Setup der Produktion auf diesem Weg zu gestalten.
  GitLab wäre gleichwertig, Forgejo ist bereits aufgebaut.

Stand im Repository am 27.09.2026:

| | Six7-app-store/deployment | DHBW-AppStore/deployment |
|---|---|---|
| `.forgejo/workflows/staging.yml` | entfernt (`52d931f`) | vorhanden |
| `.github/workflows/staging.yml` | aktiv, self-hosted Runner | vorhanden, ohne Runner/Secrets |
| `docs/staging-setup.md` | beschreibt Forgejo | beschreibt Forgejo |
| `forgejo/` (VM, Caddy, Runner, Job-Image) | vorhanden | vorhanden |

`docs/staging-setup.md` und `AGENTS.md` widersprechen sich in Six7 damit
bereits: das eine beschreibt Forgejo, das andere den GitHub-Runner.

Der Worker stößt seit `9727107` (18.09.2026) den Deploy per
`repository_dispatch` an `Six7-app-store/deployment` an.

Die Produktion wird heute per `make prod-*` von einem Menschen auf der
Zielmaschine ausgerollt (`docs/prod-setup.md`).

## Entscheidung

Wir rollen Staging — und in einem zweiten Schritt Produktion — aus einer
Forgejo-Instanz aus, die **der jeweilige Betreiber selbst betreibt**; GitHub
bleibt Ort des Codes und der CI der Anwendungsrepositories auf gehosteten
Runnern.

Im Einzelnen:

- Der Deploy-Workflow liegt als `.forgejo/workflows/staging.yml` im
  `deployment`-Repository und wird per `workflow_dispatch` von einer Person
  ausgelöst. Der Lauf verlangt eine Begründung als Eingabe; Forgejo hält fest,
  wer ihn gestartet hat.
- Secrets liegen ausschließlich im Forgejo des Betreibers. Der Workflow unter
  `.github/workflows/` und der Runner aus ADR-0002 entfallen; der
  `repository_dispatch` aus dem Worker entfällt mit.
- Die Produktion folgt mit einem eigenen Workflow und eigenem ADR, sobald der
  Staging-Weg mit einem zweiten Betreiber erprobt ist.

## Konsequenzen

**Leichter:**

- Ein neuer Betreiber braucht nichts bei GitHub: Er spiegelt `deployment` in
  sein Forgejo, hinterlegt dort seine Secrets und registriert seinen Runner.
  Die Secrets anderer Betreiber sieht er nie, und seine liegen nicht beim
  Projekt.
- Kein self-hosted Runner an einem öffentlichen Repository. Die Sicherheit
  hängt wieder an einer Netz- und Zugriffsgrenze (wer im Forgejo Actions
  starten darf), nicht an einer Trigger-Zeile in einer YAML-Datei.
- Jeder Lauf hat eine Person und einen Grund. Das dokumentiert die
  Einrichtung der Plattform zugleich, wie es der Stakeholder beschreibt.
- Forgejo Actions ist syntaktisch nah an GitHub Actions; der Workflow
  ist weitgehend derselbe, der Aufbau unter `forgejo/` existiert schon.

**Schwerer:**

- Ein Merge rollt **nicht mehr von selbst** aus. Das war das Hauptziel von
  ADR-0002 und geht hier bewusst verloren. Staging kann hinter `main`
  zurückliegen, bis jemand den Lauf startet. Der Image-Timer aus ADR-0002
  (alle 5 Minuten neue Images aus GHCR) bleibt und hält wenigstens die
  Container aktuell, nicht aber Terraform und Ansible.
- Jeder Betreiber betreibt einen zweiten Dienst: Forgejo-VM, Caddy,
  Pull-Mirror, Benutzerverwaltung, Runner, Job-Image. Für ein kleines
  Betreiberteam ist das spürbar mehr Arbeit als ein Runner.
- Die Logs der Deploys liegen nicht mehr neben Code und CI, sondern pro
  Betreiber an einem eigenen Ort. Das Projekt sieht nicht, ob Staging eines
  Betreibers gerade kaputt ist.
- ADR-0003 (Neuaufbau bei jedem Merge) setzt den GitHub-Runner voraus: Der
  Terraform-State der Staging-VM liegt dort als Datei unter
  `/var/lib/tf-state/staging/` auf der Runner-VM. Fällt sie weg, muss der
  State vorher umziehen — in den Forgejo-Runner oder in ein Backend
  außerhalb beider VMs —, sonst sieht Terraform die bestehende VM nicht mehr.
  ADR-0003 ist dafür neu zu bewerten.

## Verworfene Alternativen

**Beim GitHub-Runner aus ADR-0002 bleiben.** Erfüllt die Automatik, scheitert
aber an der neuen Anforderung: Ein zweiter Betreiber müsste seine Secrets in
ein GitHub-Repository legen, und der Runner hinge an einem öffentlichen
Repository, wovon GitHub ausdrücklich abrät.

**Jeder Betreiber spiegelt in ein privates GitHub-Repository mit eigenem
Runner.** Behebt das Problem mit dem öffentlichen Repository. Die Secrets
lägen aber weiter bei GitHub, was der Stakeholder ausdrücklich nicht will, und
ein Fork eines öffentlichen Repositories kann nicht privat sein — es braucht
einen händisch gepflegten Spiegel.

**GitLab statt Forgejo.** Für die Anforderung gleichwertig und vom
Stakeholder ausdrücklich zugelassen. Der Aufbau unter `forgejo/` und der
frühere Workflow existieren aber schon, und Forgejo Actions nimmt die
bestehende GitHub-Actions-Syntax fast unverändert; für GitLab wäre die
Pipeline als `.gitlab-ci.yml` neu zu schreiben.

**Automatischer Deploy aus Forgejo per Mirror-Sync.** Wäre die Automatik aus
ADR-0002 ohne GitHub. Laut ADR-0002 löst ein Mirror-Sync in Forgejo Actions
nicht zuverlässig aus. Solange das nicht mit einer aktuellen Forgejo-Version
nachgemessen ist, wird darauf nichts gebaut.
