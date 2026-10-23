# Architecture Decision Records

Hier steht, **warum** etwas so ist, wie es ist. Der Code zeigt das Was,
diese Dateien das Warum — besonders für die Fälle, in denen etwas
bewusst *nicht* gebaut wurde.

Ein ADR wird fällig, sobald eine Entscheidung eine der folgenden
Eigenschaften hat:

- sie ist teuer zurückzunehmen (Datenmodell, Schnittstelle, Betriebsmodell)
- sie schließt eine naheliegende Alternative aus
- jemand wird in sechs Monaten fragen „warum eigentlich nicht einfach …?"

Kleine Entscheidungen brauchen keins. Ein Kommentar im Code reicht.

## Format

Eine Datei je Entscheidung, fortlaufend nummeriert:
`NNNN-kurzer-titel.md`. Nummern werden nie wiederverwendet.

```markdown
# NNNN — Titel im Aussagesatz

**Status:** Vorschlag | Angenommen | Abgelöst durch ADR-NNNN
**Datum:** TT.MM.JJJJ
**Beteiligt:** wer die Entscheidung getragen hat

## Kontext
Was war der Fall, als die Entscheidung anstand. Fakten, keine Wertung.

## Entscheidung
Ein Satz im Aktiv: „Wir tun X."

## Konsequenzen
Was dadurch leichter wird — und was schwerer. Beides.

## Verworfene Alternativen
Je Alternative: was sie gewesen wäre und woran sie gescheitert ist.
```

Ein ADR wird nach dem Schreiben **nicht mehr geändert**. Wenn sich die
Lage ändert, entsteht ein neues, und das alte bekommt den Status
„Abgelöst durch ADR-NNNN". Die Historie ist der Punkt an der Sache.

## Für Agenten

Wer eine Architekturentscheidung trifft, legt im selben Commit ein ADR an.
Das ist Teil der Definition of Done in den `AGENTS.md` aller vier Repos.
Wie, und was danach an Doku und Diagrammen nachzuziehen ist: Skill
`adr-schreiben`.

`make docs-check` prüft dieses Verzeichnis gegen die Dateien: jede Nummer
genau einmal, lückenlos, Status hier wie im ADR.

## Verzeichnis

| Nr. | Titel | Status |
|---|---|---|
| [0001](0001-keine-windows-apps.md) | Windows-Apps werden nicht unterstützt | Abgelöst durch ADR-0020 |
| [0002](0002-self-hosted-runner-auf-eigener-vm.md) | Der Staging-Deploy läuft auf einem self-hosted GitHub-Runner auf eigener VM | Angenommen |
| [0003](0003-staging-wird-bei-jedem-merge-neu-gebaut.md) | Staging wird bei jedem Merge abgerissen und neu gebaut | Angenommen |
| [0004](0004-staging-kommt-ohne-cinder-volume-aus.md) | Staging kommt ohne Cinder-Volume aus | Angenommen |
| [0005](0005-tfstate-der-app-deployments-gehoert-von-der-staging-vm-herunter.md) | Der Terraform-State der App-Deployments gehört von der Staging-VM herunter | Angenommen |
| [0006](0006-auch-die-anwendungsdaten-gehoeren-von-der-staging-vm-herunter.md) | Auch die Anwendungsdaten gehören von der Staging-VM herunter | Angenommen |
| [0007](0007-protokoll-statt-type-im-account-vertrag.md) | Das Zugangsprotokoll ist ein eigenes Feld, kein Wert in `type` | Angenommen |
| [0008](0008-studiengruppe-aus-moodle-kurs-anlegen.md) | Eine Studiengruppe entsteht auf Knopfdruck aus einem Moodle-Kurs | Vorschlag |
| [0009](0009-deep-link-bindet-an-app.md) | Eine deep-verlinkte Moodle-Aktivität bindet an eine App, nicht an eine Umgebung | Vorschlag |
| [0010](0010-opentofu-statt-terraform-und-packer.md) | Die Plattform verwaltet Infrastruktur nur noch mit OpenTofu, ohne Image-Bau | Angenommen |
| [0011](0011-deploy-wartet-auf-die-einrichtung-der-vms.md) | Ein Deploy ist erst fertig, wenn cloud-init in allen VMs durchgelaufen ist | Angenommen |
| [0012](0012-design-v2-tokens-als-einzige-quelle.md) | Das Design v2 hat die Tokens als einzige Quelle, Light ist Standard | Angenommen |
| [0013](0013-develop-ist-staging-main-ist-produktion.md) | `develop` ist Staging, `main` ist Produktion | Angenommen |
| [0014](0014-zwei-staende-develop-und-main.md) | Die Pipeline baut zwei Stände: `develop` und `main` | Vorschlag |
| [0015](0015-agent-baut-develop-stand-selbst-nie-produktion.md) | Der Agent baut den develop-Stand selbst neu, den main-Stand und die Produktion nie | Vorschlag |
| [0016](0016-user-stories-leben-als-issues-in-deployment.md) | Offene User Stories leben als Issues in Six7-app-store/deployment | Vorschlag |
| [0017](0017-commit-gate-mit-doku-zuordnung-und-tests.md) | Vor jedem Agenten-Commit laufen Doku-Zuordnung und die Tests der CI | Vorschlag |
| [0018](0018-forgejo-wird-nicht-weiterbetrieben.md) | Forgejo wird nicht weiterbetrieben | Angenommen |
| [0019](0019-terraform-uebergangsinsel-ist-aufgeloest.md) | Die Terraform-Übergangsinsel ist aufgelöst | Angenommen |
| [0020](0020-windows-apps-werden-unterstuetzt.md) | Windows-Apps werden unterstützt | Angenommen |
