# 0006 — Auch die Anwendungsdaten gehören von der Staging-VM herunter

**Status:** Angenommen
**Datum:** 19.09.2026
**Beteiligt:** Projektteam

## Kontext

[ADR-0005](0005-tfstate-der-app-deployments-gehoert-von-der-staging-vm-herunter.md)
hat den Terraform-State der App-Deployments auf die Runner-VM geholt, damit ein
Merge die Kenntnis über laufende VMs nicht löscht.

Am 19.09.2026 wurde das umgesetzt und gemerged. Der Deploy lief erfolgreich
durch, die Staging-VM wurde neu gebaut — und die Oberfläche war leer. Kein
Deployment, kein Benutzer, kein Kurs.

Der Grund: ADR-0005 hat nur eine von drei Datenbanken betrachtet.

| Container | Inhalt | lag |
|---|---|---|
| `postgres-tfstate` | Terraform-State der Deployments | seit ADR-0005 außerhalb |
| `postgres` | Deployments, Benutzer, Kurse, Zugangsdaten | auf der Staging-VM |
| `keycloak-postgres` | Anmeldungen, Realm, Rollen | auf der Staging-VM |

Die Terraform-States der drei Windows-VMs waren gerettet. Es gab nur keine
Einträge mehr, die auf sie zeigten — die VMs liefen weiter, unsichtbar für die
Plattform. Das Ergebnis war dasselbe wie ohne ADR-0005, nur an anderer Stelle.

Der Aufwand eines Verlusts ist derselbe wie dort beschrieben: ein
Windows-Deployment kostet 30 bis 60 Minuten Neuaufbau je Studierendem.

## Entscheidung

Wir betreiben auch `postgres` und `keycloak-postgres` auf der Runner-VM, in
derselben PostgreSQL-Instanz, die seit ADR-0005 den Terraform-State hält.

Beide Container entfallen aus `docker-compose.staging.yml`; Backend und
Keycloak verbinden sich über `DB_HOST` beziehungsweise `KEYCLOAK_DB_HOST` aus
der `.env`.

## Konsequenzen

**Leichter:**

- Ein Merge auf `main` verliert keine Anwendungsdaten mehr. Deployments,
  Benutzer, Kurse und Zugangsdaten überstehen den Neuaufbau.
- Damit wirkt ADR-0005 erst: die geretteten Terraform-States haben wieder
  Einträge, die auf sie zeigen.
- Die Staging-VM wird deutlich kleiner — drei Datenbankcontainer und drei
  Datenverzeichnisse weniger auf einer Maschine, die ohnehin bei jedem Merge
  neu entsteht.

**Schwerer:**

- **Die Runner-VM ist jetzt der Einzelpunkt, an dem alles hängt.** Sie führt
  den Deploy aus, hält den Terraform-State und die Anwendungsdaten. Fällt sie
  aus, ist nicht nur das Ausrollen blockiert, sondern die Plattform unbenutzbar.
  Das ist ein deutlich größeres Gewicht als in ADR-0005 und der stärkste Grund,
  die dort verworfene eigene State-VM später doch zu bauen.
- **Die Sicherung ist jetzt Pflicht, nicht Kür.** Bisher war ein Verlust
  ärgerlich; künftig sind es alle Daten der Plattform.
- **Eine Netzstörung zwischen den VMs legt die Anwendung lahm**, nicht nur das
  Ausrollen. Backend und Keycloak sprechen bei jeder Anfrage über das Netz mit
  der Datenbank statt über den Docker-Socket.
- Die Datenbank läuft auf einer VM mit 1 vCPU und 2 GB RAM, die auch den
  Actions-Runner trägt. Für den Umfang dieses Projekts reicht das; für einen
  Kursbetrieb mit vielen gleichzeitigen Anmeldungen wäre es zu prüfen.

## Verworfene Alternativen

**Nur `postgres` verschieben, Keycloak lassen.** Hätte die Deployments gerettet,
aber nicht die Anmeldungen — ein Benutzer ohne Keycloak-Konto kommt nicht in die
Oberfläche, in der seine Deployments stünden. Die Trennung hätte nichts gespart
und die Hälfte des Problems bestehen lassen.

**Ein Volume für die Datenbanken statt Auslagerung.** ADR-0004 hat das
Cinder-Volume entfernt, weil der Dienst ausfiel; es wieder einzuführen brächte
diese Abhängigkeit zurück. Ein Volume überlebt ein Ersetzen der Instanz
außerdem nur, solange Terraform es nicht mitlöscht — bei `destroy` tut es das.

**Staging nicht mehr bei jedem Merge neu bauen** (ADR-0003 zurücknehmen). Löst
das Problem, nimmt aber den Nutzen. Dieselbe Abwägung wie in ADR-0005, mit
demselben Ergebnis.
