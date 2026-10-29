# 0023 — App-Freigaben binden unveränderliche Git-Commits

**Status:** Vorschlag
**Datum:** 27.10.2026
**Beteiligt:** Projektteam, Codex
**Korrigiert:** 29.10.2026 — „Produktionsmodus“ ist der Schalter `REQUIRE_PINNED_RELEASES`, nicht eine
Umgebung. Das steht jetzt in der Entscheidung.

## Kontext

Ein Git-Tag kann nach einer Freigabe auf einen anderen Commit verschoben
werden. Derselbe Tag wurde auch für spätere Lifecycle-Aktionen erneut geklont.
Damit konnten Review, Deploy und Abbau unterschiedliche Inhalte verwenden.
Historische Datensätze enthalten nicht zwingend einen vollständigen Commit.

## Entscheidung

Wir speichern bei der Einreichung die vollständige Commit-SHA und verwenden
sie im Produktionsmodus (`REQUIRE_PINNED_RELEASES=true`) für Review und
Deployment. Jeder neue Deployment-
Datensatz speichert den tatsächlich vorgesehenen Commit für spätere Aktionen.
Historische Einträge ohne nachweisbaren Commit werden nicht automatisch aus
dem aktuellen Tag ergänzt; im Produktionsmodus bleiben ihre Lifecycle-Aktionen
bis zur geprüften Migration gesperrt.

## Konsequenzen

Ein verschobener Tag ändert den freigegebenen Code nicht. Review und Variable-
Prüfung beziehen sich auf denselben Commit; das Frontend zeigt ihn an. Der
Git-Server muss diesen Commit dauerhaft verfügbar halten. Fehlende Commits und
nicht migrierte historische Deployments können den Abbau blockieren, deshalb
müssen Betreiber die Altbestände vor der Aktivierung prüfen und die Warteschlange
vor dem Wechsel leeren. Für Dev und Staging bleibt die Prüfung bis zur
Umstellung explizit schaltbar.

`docker-compose.prod.yml` setzt den Schalter fest auf `true`.
`docker-compose.staging.yml`, mit der beide Pipeline-Stände und damit auch
die Produktion laufen, übernimmt ihn aus `STAGING_ENV_FILE`, Standard
`false`.

## Verworfene Alternativen

**Tag erneut auflösen:** Ein beweglicher Tag kann seit dem Review geändert
worden sein und beweist den ursprünglichen Inhalt nicht.

**Historische Commits aus aktuellen Tags ergänzen:** Das könnte einen falschen
Stand als historisch ausgeben. Ohne verlässlichen Nachweis bleibt der Wert leer.
