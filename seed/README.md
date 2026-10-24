# Seed Data

Lädt eine realistische Beispiel-Konfiguration in Keycloak und in die
Backend-Datenbank, damit die App-Store-UI nach dem ersten Hochfahren
nicht leer ist.

## Was angelegt wird

### Keycloak (Realm `dhbw`)

| Rolle    | User                                                                    |
| -------- | ----------------------------------------------------------------------- |
| Admin    | Tobias Admin                                                            |
| Teacher  | Henning Pagnia, Michael Eichberg, Sarah Detzler, Frank Hubert,          |
|          | Andrea Bauer, Thomas Wagner                                             |
| Student  | Luca Bäck, Felix Erhard, Raphael Plett, Mika Jun, Okan Sömnez,          |
|          | Leon Priemer, Tom Weber, Monika Piano, Iven Stahl (alle WI SE B 23)     |
|          | + 10 weitere Studierende verteilt auf WI SE B 24, INF TI 23, WI SE A 23 |

- **Login-Format:** `<vorname>.<nachname>@dhbw.de`
  (Umlaute → `ae/oe/ue/ss`, Bindestriche/Leerzeichen entfernt)
- **Passwort:** `1234` (nicht temporär)

### Backend-DB

- 4 Kurse: `WI SE B 23`, `WI SE B 24`, `INF TI 23`, `WI SE A 23`
- Professoren als Course-Teacher verlinkt (Many-to-Many)
- Studenten via `users.courseId` ihrem Kurs zugewiesen
- 10 Apps im offiziellen DHBW-Katalog, alle mit `Tobias Admin` als Owner
  und je einer freigegebenen Version. Jede zeigt auf ein Repo in
  `Six7-app-store` mit `tofu/` (App-Vertrag aus ADR 0010):

  | App | Version | Sichtbarkeit |
  |---|---|---|
  | Online-IDE | v2.0.0 | public |
  | Ubuntu-App | v2.0.3 | private |
  | Web-LaTeX | v2.0.0 | public |
  | Jupyter-Notebook | v2.0.0 | public |
  | pgAdmin | v2.0.0 | private |
  | Windows-App | v2.1.1 | public |
  | Kali-Linux-App | v2.2.3 | public |
  | VSCode-App | v1.1.0 | public |
  | Kubernetes-App | v2.1.1 | public |
  | group-network-app | v1.0.2 | public |

  Die Texte im Store kommen aus `app_descriptions/<App>.md`.
- Apps aus früheren Seed-Ständen, die nicht mehr deploybar sind
  (`RETIRED_APPS` in `seed_data.py`, z. B. GitLab-CE, Monitoring-Stack und
  die alten Beispiel-Apps auf `six7-click-n-deploy`), werden ausgeblendet,
  falls eine Datenbank sie noch hat.

## Aufruf

```bash
cd deployment
make dev-up           # Falls noch nicht gestartet
make seed-data
```

Das Makefile-Target kopiert das Skript in den Backend-Container und
führt es dort aus (so muss lokal kein Python-Setup vorhanden sein).

### Direktaufruf (alternativ)

```bash
docker compose -f docker-compose.dev.yml cp \
  ./seed/seed_data.py backend:/tmp/seed_data.py
docker compose -f docker-compose.dev.yml exec backend \
  python /tmp/seed_data.py
```

## Idempotenz

Mehrfaches Ausführen ist unkritisch:

- User werden über `email` (exakte Übereinstimmung) gefunden und nur
  ergänzt, nicht dupliziert.
- Kurse werden über `name` gefunden.
- Apps werden über `name` gefunden, Beschreibung/Visibility werden
  bei jedem Lauf neu gesetzt.
- Approval-Records werden über `(appId, version_tag)` upsert-artig
  aktualisiert.
- Apps aus `RETIRED_APPS` bekommen `deleted_at` gesetzt, wie beim
  Löschen in der Admin-Oberfläche. Die Zeile bleibt, damit bestehende
  Deployments ihre App behalten. Zeigt eine solche App auf das Repo einer
  aktuellen Katalog-App, bleibt sie stehen.

Passwörter werden bei jedem Lauf auf den Default zurückgesetzt — so
ist nach dem Seed garantiert, dass `1234` funktioniert.

## Voraussetzungen

- `make dev-up` hat Keycloak und das Backend hochgefahren.
- Keycloak-Admin-Account `admin/admin` (Default) ist erreichbar.
  Davon abweichende Credentials per `KEYCLOAK_ADMIN_USER` /
  `KEYCLOAK_ADMIN_PASSWORD` setzen.
- Die `dhbw`-Realm-Konfiguration ist importiert (Realm-Rollen
  `admin`, `teacher` müssen existieren — beides aus
  `keycloak/realm-export.json`).
