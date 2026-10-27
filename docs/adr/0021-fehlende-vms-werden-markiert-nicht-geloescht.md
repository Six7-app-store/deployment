# 0021 — Außerhalb gelöschte VMs werden markiert, nicht automatisch entfernt

**Status:** Angenommen
**Datum:** 25.10.2026
**Beteiligt:** Projektteam
<!-- TODO: Wer hat die Entscheidung getragen? Namen eintragen, bevor das ADR in die Abgabe geht. -->

## Kontext

VMs eines Deployments lassen sich außerhalb des App Stores löschen — über
Horizon, die OpenStack-CLI oder beim Aufräumen eines Projekts. Der App Store
hat davon nichts mitbekommen: Das Deployment stand weiter mit Status
`success` in der Liste, Studierende sahen „Bereit" für eine Umgebung, die es
nicht mehr gab.

Die Server-IDs stehen im OpenTofu-State, den jeder Task in `tasks.tf_state`
ablegt. Der Infrastruktur-Tab fragt sie schon live bei OpenStack ab und
unterscheidet „nicht gefunden" (`drift = missing`) von „Abfrage gescheitert"
(`drift = stale`). Das passierte aber nur beim Öffnen des Tabs und wurde nicht
gespeichert.

Ein „nicht gefunden" hat neben dem Löschen weitere mögliche Ursachen: Zeigen
die OpenStack-Zugangsdaten einer Person inzwischen auf ein anderes Projekt,
findet die Abfrage die VMs ebenfalls nicht.

## Entscheidung

Eine Schleife im Backend prüft alle zehn Minuten die VMs jedes Deployments, das
laut Status OpenStack-Ressourcen haben sollte, und setzt
`deployments.vm_missing_since`, wenn **alle** VMs eindeutig nicht gefunden
werden. Findet sie wieder eine, löscht sie die Markierung. Entfernt wird der
Eintrag nur auf Knopfdruck eines Menschen
(`DELETE /deployments/{id}?entry_only=true`), ohne `tofu destroy`.

## Konsequenzen

- Die Liste und die Detailseite zeigen ehrlich an, dass die VMs fehlen;
  Studierende sehen „Nicht verfügbar" statt „Bereit".
- Ein OpenStack-Ausfall oder abgelaufene Zugangsdaten markieren nichts: Nur
  eine Abfrage, die erfolgreich „nicht gefunden" meldet, zählt.
- Ein Fehlalarm wegen gewechselter Zugangsdaten kostet nur einen Hinweis, der
  von selbst verschwindet, sobald die VMs wieder gefunden werden. Kein Eintrag
  geht verloren, ohne dass jemand es bestätigt hat.
- „Eintrag entfernen" räumt nicht auf. Übrig gebliebene Netzwerke, Ports oder
  Volumes bleiben im OpenStack-Projekt. Wer aufräumen lassen will, nimmt das
  normale „Löschen" (Destroy); scheitert es, bleibt „Eintrag entfernen" als
  Ausweg.
- Die Schleife fragt OpenStack mit den Zugangsdaten jeder Person ab. Bei sehr
  vielen Deployments wächst die Last linear; zehn Minuten Abstand halten sie
  klein.

## Verworfene Alternativen

**Eintrag nach einer Wartezeit automatisch entfernen.** Wäre ohne Zutun
sauber, löscht bei gewechselten Zugangsdaten aber Einträge, deren VMs noch
laufen. Die Entscheidung „das ist wirklich weg" bleibt deshalb bei einem
Menschen.

**Automatisch `tofu destroy` auslösen.** Räumt die Reste mit auf, ist aber
der destruktivste Weg auf der unsichersten Grundlage: Bei einem Fehlalarm
würde er laufende Infrastruktur abreißen.

**Neuer synthetischer Status `vm_missing`.** Der Status wird an drei Stellen
aus dem letzten Task abgeleitet (einzeln, gebündelt für die Liste, als
SQL-Filter). Ein Zustand, der nicht aus einem Task kommt, hätte alle drei
verbogen. Eine eigene Spalte neben dem Status hält beides auseinander.

**Eigene IDs für VMs in der Datenbank.** Unnötig: Die Server-IDs stehen schon
im gespeicherten OpenTofu-State, und der bleibt bei jedem Redeploy aktuell.
