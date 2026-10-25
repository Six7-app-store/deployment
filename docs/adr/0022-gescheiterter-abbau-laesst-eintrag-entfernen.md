# 0022 — Nach einem gescheiterten Abbau lässt sich der Eintrag entfernen

**Status:** Angenommen
**Datum:** 25.10.2026
**Beteiligt:** Projektteam
<!-- TODO: Wer hat die Entscheidung getragen? Namen eintragen, bevor das ADR in die Abgabe geht. -->

## Kontext

[ADR 0021](0021-fehlende-vms-werden-markiert-nicht-geloescht.md) erlaubt
„Eintrag entfernen“ (Soft-Delete ohne `tofu destroy`) nur, wenn alle VMs eines
Deployments in OpenStack fehlen.

Auf Staging ließ sich ein Deployment der GitLab-App nicht mehr löschen. Der
Worker klont für den Abbau das App-Repository in der Version des Deploys, und
`six7-click-n-deploy/GitLab-App` war gelöscht worden. Der Destroy scheiterte
schon beim Klonen. Danach stand das Deployment auf `failed`, und für `failed`
startet „Löschen“ wieder einen Destroy, der wieder scheitert. Die Prüfschleife
aus ADR 0021 schaut `failed`-Deployments gar nicht an. Das Deployment hing
damit fest, ohne Ausweg in der Oberfläche.

Dasselbe passiert bei jedem Destroy, der dauerhaft nicht durchgeht: gelöschtes
Tag, kaputter OpenTofu-Code in der alten Version, ein State, den der Provider
nicht mehr auflösen kann.

## Entscheidung

`DELETE /deployments/{id}?entry_only=true` ist zusätzlich erlaubt, wenn der
letzte Task des Deployments ein **gescheiterter Destroy** ist. Die Oberfläche
zeigt dann einen Hinweis „Abbau gescheitert“ mit „Eintrag entfernen“.

## Konsequenzen

- Kein Deployment kann mehr dauerhaft festhängen: Wo „Löschen“ nicht
  durchkommt, bleibt der Ausweg, den Eintrag zu entfernen.
- Wer das nutzt, übernimmt das Aufräumen in OpenStack selbst. Hinweis und
  Bestätigung sagen das. Die IDs der Ressourcen stehen im Infrastruktur-Tab,
  solange der Eintrag noch da ist.
- Ein vorübergehender Fehler (OpenStack kurz weg) bietet den Ausweg ebenfalls
  an. Der Hinweis verweist deshalb auf die Logs, damit die Ursache erst
  geprüft wird; wer vorschnell entfernt, hinterlässt eventuell laufende VMs.
- Ein gescheiterter **Deploy** bekommt den Ausweg nicht. Dort kann „Löschen“
  den Destroy noch versuchen, und der räumt halb angelegte Ressourcen auf.

## Verworfene Alternativen

**Destroy ohne App-Code.** Mit einer leeren Konfiguration, die nur die Provider
und das State-Backend nennt, würde OpenTofu alle Ressourcen im State abreißen.
Das hilft nur beim fehlenden Repository, nicht bei den anderen Ursachen, und
reißt auf Basis einer selbst gebauten Konfiguration Infrastruktur ab. Für einen
Fall, der selten vorkommt, ist das zu viel Risiko.

**Den Eintrag direkt in der Datenbank löschen.** Hilft einmal und kommt beim
nächsten gelöschten Repository wieder. Außerdem muss dafür jemand an die
Datenbank von Staging oder Produktion.
