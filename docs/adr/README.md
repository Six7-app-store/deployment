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

## Verzeichnis

| Nr. | Titel | Status |
|---|---|---|
| [0001](0001-keine-windows-apps.md) | Windows-Apps werden nicht unterstützt | Angenommen |
| [0002](0002-self-hosted-runner-auf-eigener-vm.md) | Der Staging-Deploy läuft auf einem self-hosted GitHub-Runner auf eigener VM | Angenommen |
| [0003](0003-staging-wird-bei-jedem-merge-neu-gebaut.md) | Staging wird bei jedem Merge abgerissen und neu gebaut | Angenommen |
| [0004](0004-staging-kommt-ohne-cinder-volume-aus.md) | Staging kommt ohne Cinder-Volume aus | Angenommen |
