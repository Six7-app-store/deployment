# Moodle-Testinstanz für die LTI-1.3-Anbindung

Diese Anleitung beschreibt das lokale Moodle, das als **LTI 1.3 Platform** dient. Der App Store ist in dieser Beziehung das **Tool**: Moodle stellt beim Klick auf eine Aktivität ein signiertes `id_token` aus, das Backend prüft die Signatur gegen Moodles öffentlichen Schlüssel und meldet den Nutzer damit an.

Der Stack liegt in [`docker-compose.moodle.yml`](../docker-compose.moodle.yml) und ist vom Dev-Stack getrennt (eigener Compose-Projektname `appstore-moodle`, eigenes Netz, eigene Datenbank). Er ist ausschließlich für die Entwicklung gedacht.

| | |
|---|---|
| Image | `erseco/alpine-moodle:v5.2.2` (Moodle 5.2.2, Build 20260810) |
| Datenbank | `postgres:16-alpine`, nur intern erreichbar |
| URL | <http://host.docker.internal:8081> |
| Zugang | `admin` / `Moodle#2026` |

> Die Container liefen seit dem 04.09.2026, aber die zugehörige Compose-Datei war verlorengegangen — sie waren also nicht mehr reproduzierbar. Diese Datei beschreibt den Stack wieder und greift die bestehenden Volumes über `external: true` auf. Die Installation ist erhalten geblieben.

## Warum `host.docker.internal` und nicht `localhost`

Der `iss`-Claim jedes LTI-Tokens ist Moodles `wwwroot`. Das Backend muss unter genau dieser URL Moodles JWKS abrufen. Stünde dort `http://localhost:8081` — wie ursprünglich konfiguriert — würde der Backend-Container sich selbst befragen statt Moodle. Der Launch scheitert dann mit einem Signaturfehler, dessen Ursache nicht offensichtlich ist.

`host.docker.internal` löst auf beiden Seiten auf dieselbe Maschine auf:

| Von | Nach | URL |
|---|---|---|
| Browser | Moodle | `http://host.docker.internal:8081` |
| Browser | Backend | `http://host.docker.internal:8000` |
| Moodle-Container | Backend (Keyset-Abruf) | `http://host.docker.internal:8000` |
| Backend-Container | Moodle (JWKS-Abruf) | `http://host.docker.internal:8081` |

Beide Richtungen sind geprüft: `GET /login/index.php` antwortet mit 200 sowohl vom Host als auch aus einem Container mit `host-gateway`-Eintrag.

Aus demselben Grund hat der Stack **kein** gemeinsames Docker-Netz mit dem App Store. Ein zweiter Pfad über Docker-DNS (`http://moodle:8080`) würde genau die Issuer-Verwechslung wieder einladen — und der Moodle-Start hinge am Dev-Netz.

Der Preis: Frontend und Backend müssen im Dev-Setup ebenfalls über `host.docker.internal` erreichbar sein, nicht nur über `localhost`. Konkret:

* `CORS_ORIGINS` in der `.env` um `http://host.docker.internal:5173` erweitern
* `VITE_API_URL=http://host.docker.internal:8000`, wenn der Launch im Moodle-Kontext getestet wird
* Keycloak-Client `appstore-frontend`: `http://host.docker.internal:5173/*` als Redirect-URI ergänzen

## Betrieb

```bash
cd deployment
docker compose -f docker-compose.moodle.yml up -d
docker compose -f docker-compose.moodle.yml ps
docker compose -f docker-compose.moodle.yml logs -f moodle
```

Stoppen: `docker compose -f docker-compose.moodle.yml stop`

Die drei Volumes (`moodle_html_dev`, `moodle_data_dev`, `moodle_postgres_data_dev`) sind als `external` deklariert. Compose fasst sie deshalb auch bei `down -v` nicht an — die Installation überlebt einen versehentlichen Aufruf. Wer wirklich zurücksetzen will, muss sie ausdrücklich löschen:

```bash
docker compose -f docker-compose.moodle.yml down
docker volume rm moodle_html_dev moodle_data_dev moodle_postgres_data_dev
```

Auf einer frischen Maschine müssen sie einmalig angelegt werden, sonst startet der Stack nicht:

```bash
docker volume create moodle_html_dev
docker volume create moodle_data_dev
docker volume create moodle_postgres_data_dev
```

Eine Neuinstallation dauert danach 3–8 Minuten. Der Healthcheck hat deshalb `start_period: 600s` — „unhealthy" ist in dieser Zeit kein Fehler, sondern der laufende Setup.

## Testdaten anlegen

Die Instanz ist leer: ein Site-Record, `admin` und `guest`, keine Kurse, keine LTI-Tools.

1. **Kurs:** *Website-Administration → Kurse → Kurs hinzufügen*. Einer reicht; der Kurskontext landet später als `context_id` im Token.
2. **Nutzer:** *Website-Administration → Nutzer/innen → Nutzerkonten → Neues Nutzerkonto anlegen*. Mindestens zwei — einer für Trainer/in, einer für Teilnehmer/in. Beide brauchen eine E-Mail-Adresse, sonst fehlt der `email`-Claim.
3. **Einschreiben:** Im Kurs → *Teilnehmer/innen → Nutzer/innen einschreiben*, Rolle jeweils explizit setzen. Die Kursrolle bestimmt den `roles`-Claim (`#role/Instructor` vs. `#role/Learner`).

## Tool registrieren (der eigentliche LTI-Teil)

*Website-Administration → Plugins → Aktivitätsmodule → Externes Tool → Tools verwalten → **Tool manuell konfigurieren***

| Feld | Wert |
|---|---|
| Toolname | `Click'n Deploy App Store` |
| Tool-URL | `http://host.docker.internal:8000/lti/launch` |
| LTI-Version | **LTI 1.3** |
| Public-Key-Typ | **Keyset-URL** |
| Public-Keyset | `http://host.docker.internal:8000/lti/jwks` |
| Initiate-Login-URL | `http://host.docker.internal:8000/lti/login` |
| Redirection-URI(s) | `http://host.docker.internal:8000/lti/launch` |
| Standardstartcontainer | *Neues Fenster* (siehe Cookie-Hinweis unten) |

Unter *Dienste* zusätzlich **IMS LTI Names and Role Provisioning** auf „Kursmitglieder abrufen" stellen, falls die Kursliste später über NRPS geholt werden soll. Unter *Datenschutz* Name und E-Mail-Adresse freigeben — ohne das kommen die Claims leer an.

Damit `/lti/jwks` beim Registrieren schon antwortet, muss im Backend vorher `LTI_ENABLED=true` und `LTI_PRIVATE_KEY_B64` gesetzt sein — mehr nicht. Der Endpunkt hängt bewusst nur am Schlüssel und nicht an der Tool-Konfiguration, weil Client-ID und Deployment-ID erst durch diese Registrierung entstehen.

Nach dem Speichern liefert Moodle über *Tools verwalten → Zahnrad → Toolkonfigurationsdetails ansehen* die Gegenwerte:

| Moodle-Feld | Gehört ins Backend als |
|---|---|
| Plattform-ID | `LTI_PLATFORM_ISSUER` (= `http://host.docker.internal:8081`) |
| Client-ID | `LTI_CLIENT_ID` |
| Deployment-ID | `LTI_DEPLOYMENT_ID` |
| Public-Keyset-URL | `LTI_JWKS_URL` (`.../mod/lti/certs.php`) |
| Zugriffstoken-URL | `LTI_TOKEN_URL` (`.../mod/lti/token.php`) |
| Authentifizierungsanfrage-URL | `LTI_AUTH_LOGIN_URL` (`.../mod/lti/auth.php`) |

Diese Werte sind die komplette Vertrauensbeziehung. Sie kommen in die `.env` (Block „Moodle-Anbindung über LTI 1.3"), danach `docker compose -f docker-compose.dev.yml up -d backend` — ein `restart` reicht nicht, geänderte `.env`-Werte erreichen nur einen neu erzeugten Container.

Für die Prototyp-Phase reichen Environment-Variablen; sobald eine zweite Moodle-Instanz dazukommt, gehören sie in eine Tabelle. Im Code ist dafür nur `get_tool_conf()` in `app/services/lti_service.py` anzufassen — die Struktur, die PyLTI1p3 erwartet, ist ein Dict mit dem Issuer als Schlüssel.

Moodles eigenes Keyset liefert bereits einen RS256-Schlüssel — prüfbar ohne Login:

```bash
curl -s http://host.docker.internal:8081/mod/lti/certs.php
```

## Launch testen

> **Moodle 5 hat diesen Weg geändert.** Ein Tool direkt in der Aktivität zu konfigurieren geht nicht mehr — `modedit.php?add=lti` ohne `typeid` antwortet mit „Die manuelle Erstellung von Tools ohne die Definition von Kurstools wird nicht mehr unterstützt." Das site-weit registrierte Tool muss erst im Kurs sichtbar gemacht werden: *Kurs → Mehr → LTI Externe Tools* (`/mod/lti/coursetools.php?id=<kursid>`), dort beim Tool **„In Aktivitätsauswahl anzeigen"** anhaken. Danach steht es in der Aktivitätsauswahl.

Im Testkurs → *Aktivität oder Material anlegen* → das registrierte Tool auswählen → speichern. Ein Klick darauf löst die Kette aus:

```
POST /lti/login   (Moodle → Backend, iss + login_hint + target_link_uri)
302               (Backend → Moodle/auth.php, state + nonce)
POST /lti/launch  (Moodle → Backend, id_token)
302               (Backend → Frontend, eigenes Session-Token)
```

Erfolg sieht so aus: das Dashboard erscheint mit dem Namen des Testnutzers, ohne Login-Maske. In der Datenbank steht danach je eine Zeile in `users`, `user_identities` und `lti_contexts`; ein zweiter Klick legt nichts Neues an.

Wenn der Launch abgelehnt wird, steht der Grund im Backend-Log — PyLTI1p3 benennt die fehlgeschlagene Prüfung genau:

```bash
docker compose -f docker-compose.dev.yml logs backend | grep -i lti
```

## Wenn die Adresse schon vergeben ist

Ein Launch, dessen Moodle-Identität unbekannt ist, dessen E-Mail-Adresse aber bereits zu einem Konto gehört, wird **abgelehnt**. Die Adresse stammt aus einem Moodle-Profilfeld, das die Person selbst ändern kann — sie beweist nichts darüber, wem das Konto gehört. Statt anzumelden schickt das Backend einen Redirect auf `LTI_LINK_REDIRECT_URL` und gibt eine kurzlebige *Link-Challenge* mit:

```
POST /lti/launch   → 302 auf /lti/link?challenge=…   (10 Minuten, einmal einlösbar)
Direkte Anmeldung  → POST /lti/link {challenge}       (nur mit Keycloak-Token)
Nächster Launch    → Identity-Treffer → angemeldet
```

Erst beide Hälften zusammen verknüpfen: Moodle hat für die Identität signiert, der direkte Login für das Konto. Eine aus Moodle gestartete Sitzung wird an `/lti/link` mit 403 `direct_login_required` abgewiesen — sie stammt selbst aus der Behauptung, die geprüft werden soll.

### `LTI_LINK_REDIRECT_URL` zeigt auf `localhost`, nicht auf `host.docker.internal`

Anders als der Launch selbst. Die Link-Seite verlangt eine Keycloak-Anmeldung, und deren PKCE braucht `crypto.subtle`. Das gibt der Browser nur in einem *secure context* her — über http gilt das ausschließlich für `localhost`. Unter `host.docker.internal:5173` bricht der Login ab mit:

```
Login failed: Error: Crypto.subtle is available only in secure contexts (HTTPS).
```

Der Launch-Redirect (`LTI_LAUNCH_REDIRECT_URL`) bleibt auf `host.docker.internal`, weil er nur ein vom Backend ausgestelltes Token entgegennimmt und kein PKCE fährt. In Produktion läuft alles über HTTPS, dort entfällt die Unterscheidung.

### Frontend-Container sieht Dateiänderungen nicht

Der Bind-Mount unter Windows liefert keine inotify-Events, Vite bemerkt neue Dateien und Routen deshalb nicht. Symptom: eine neu angelegte Route endet im App-Layout statt in ihrer View, und `curl http://localhost:5173/src/router/index.ts` zeigt noch den alten Stand. Abhilfe:

```bash
docker restart frontend-dev
```

Beim Backend reicht aus demselben Grund kein `restart`, wenn sich `.env` oder Compose-Variablen geändert haben — dort `up -d --force-recreate backend`.

## Teilnehmerliste abrufen (NRPS)

Der App Store kann aus einem Moodle-Kurs eine **Studiengruppe anlegen** und die Teilnehmenden übernehmen: `POST /lti/contexts/{id}/import`, ausgelöst über den Knopf „Studiengruppe aus Moodle anlegen" auf der Zuordnungsseite. Die Liste kommt über **NRPS** (Names and Role Provisioning Service). Warum das so und nicht als Vollsync gebaut ist: [ADR 0008](adr/0008-studiengruppe-aus-moodle-kurs-anlegen.md).

Moodle-seitig muss dafür unter *Tools verwalten → Zahnrad → Dienste* **IMS LTI Names and Role Provisioning** auf „Kursmitglieder abrufen" stehen. Gegenprobe in der Tool-Konfiguration: `ltiservice_memberships = 1`.

### Moodle muss den App Store erreichen können

Das ist die Richtung, die beim Launch **nicht** vorkommt. Für NRPS holt sich das Backend zuerst ein Access-Token bei `/mod/lti/token.php`, und Moodle prüft dieses Token gegen das Keyset unter `http://host.docker.internal:8000/lti/jwks`. Dieser Abruf geht durch Moodles cURL-Sicherheitsfilter — und der blockt ihn im Standard doppelt:

| Einstellung | Standard | Problem |
|---|---|---|
| `curlsecurityallowedport` | `80`, `443` | Backend läuft auf `8000` |
| `curlsecurityblockedhosts` | u. a. `192.168.0.0/16` | `host.docker.internal` → `192.168.65.254` (Docker-Desktop-Gateway) |

Das Symptom ist irreführend: `token.php` antwortet mit **404** und einer HTML-Fehlerseite statt mit JSON, darin

```
mod_lti\local\ltiopenid\jwks_helper::fix_jwks_alg(): Argument #1 ($jwks) must be of type array, null given
```

Der Launch funktioniert dabei unverändert weiter, weil dort das Backend Moodles Keyset holt und nicht umgekehrt. Fix für die Dev-Instanz:

```bash
docker exec moodle-dev php /var/www/html/admin/cli/cfg.php \
  --name=curlsecurityallowedport --set="443
80
8000"

docker exec moodle-dev php /var/www/html/admin/cli/cfg.php \
  --name=curlsecurityblockedhosts --set="127.0.0.0/8
10.0.0.0/8
172.16.0.0/12
0.0.0.0
localhost
169.254.169.254
0000::1"
```

Die CLI liegt unter `/var/www/html/admin/cli/`, **nicht** unter `public/` — Moodle 5 hat nur den Web-Root nach `public/` verschoben. Beide Werte hängen an der Datenbank, überleben also einen Neustart, aber **nicht** ein frisches Volume.

Prüfen, ob Moodle den Abruf jetzt zulässt:

```bash
docker exec moodle-dev php -r '
define("CLI_SCRIPT", true);
require("/var/www/html/config.php");
require_once($CFG->libdir . "/filelib.php");
$h = new \core\files\curl_security_helper();
var_dump($h->url_is_blocked("http://host.docker.internal:8000/lti/jwks"));'
```

`bool(false)` heißt: erlaubt. In Produktion entfällt die Anpassung — dort läuft alles über HTTPS auf 443 und über öffentlich auflösbare Namen.

### Was der Import tut und was nicht

- Gematcht wird über `(issuer, user_id)` — denselben Wert, den ein Launch als `sub` schickt. Eine **bereits vergebene E-Mail-Adresse führt nie zu einem Treffer**, sondern zu einem gemeldeten Übersprung `link_required`: die Adresse ist ein bearbeitbares Moodle-Profilfeld.
- Ein Moodle-Trainer wird nur dann Dozent:in im App Store, wenn `LTI_TRUST_INSTRUCTOR_ROLE=true` gesetzt ist. Sonst erscheint er als `instructor_not_trusted` in der Übersprungsliste.
- Studierende, die schon in einer anderen Studiengruppe sind, bleiben dort (`already_in_another_group`).
- Der Import läuft **einmal**. Wer sich später in Moodle einschreibt, kommt nicht automatisch dazu.

## Deep Linking: Aktivität an eine App binden

Ohne Deep Linking heißt jede Aktivität nur „der App Store", und wohin ein Klick führt, rät `resolve_launch_target`. Mit Deep Linking fragt Moodle beim **Anlegen** der Aktivität, worauf sie zeigen soll; die Lehrperson wählt eine App, und die Wahl steckt danach als `custom`-Parameter in der Aktivität. Warum an eine App und nicht an eine konkrete Umgebung: [ADR 0009](adr/0009-deep-link-bindet-an-app.md).

Moodle bietet die Auswahl nur an, wenn am Tool **„Tool unterstützt Deep Linking (Content-Item Message)"** gesetzt ist — *Tools verwalten → Zahnrad → Deep Linking unterstützen*. Gegenprobe:

```bash
docker exec moodle-postgres-dev psql -U moodle -d moodle \
  -c "select name, value from mdl_lti_types_config where typeid=1 and name='contentitem';"
```

`1` heißt an. Per CLI setzen und Caches leeren:

```bash
docker exec moodle-postgres-dev psql -U moodle -d moodle \
  -c "update mdl_lti_types_config set value='1' where typeid=1 and name='contentitem';"
MSYS_NO_PATHCONV=1 docker exec moodle-dev php /var/www/html/admin/cli/purge_caches.php
```

Danach zeigt Moodle beim Anlegen der Aktivität *Externes Tool* den Knopf **„Inhalt auswählen"**. Er öffnet `/lti/auswahl` im App Store, dort wird die App gewählt, und Moodle legt die Aktivität mit Titel und Bindung an.

Ablauf, mit den beteiligten Nachrichtentypen:

```
Klick "Inhalt auswählen"
POST /lti/launch        LtiDeepLinkingRequest  (gleicher Endpunkt wie ein Launch)
302                     -> /lti/callback -> /lti/auswahl?dl=<handle>
POST /lti/deep-link/select   { handle, appId }  -> signiertes JWT
Formular-POST           JWT -> Moodles deep_link_return_url
Moodle legt Aktivität an, custom: { app_id: ... }
```

Der Handle ist **einmal einlösbar** und an das Konto gebunden, dem er ausgestellt wurde; Gültigkeit über `LTI_DEEP_LINK_TTL_MINUTES` (Standard 30 Minuten). Die signierte Antwort wird bewusst **aus dem Browser** gepostet, nicht vom Backend — `deep_link_return_url` erwartet die Moodle-Sitzung der Lehrperson.

Bestehende Aktivitäten ohne Bindung laufen unverändert weiter: ein fehlender `custom`-Parameter ist genau der alte Pfad.

## Troubleshooting

**Port 8081 belegt.** `MOODLE_PORT` **und** `MOODLE_SITE_URL` in `deployment/.env` gemeinsam ändern. Passen sie nicht zusammen, zeigt `wwwroot` ins Leere und jeder Aufruf endet in einer Weiterleitungsschleife. Belegten Port finden: `Get-NetTCPConnection -State Listen -LocalPort 8081`.

**Weiterleitungsschleife oder „Incorrect access detected".** `wwwroot` passt nicht zur aufgerufenen URL. Prüfen:

```bash
docker compose -f docker-compose.moodle.yml exec moodle grep wwwroot /var/www/html/config.php
```

Das Entrypoint-Skript schreibt `wwwroot` bei jedem Start aus `SITE_URL` neu — ein geänderter Wert wirkt also nach `up -d`, ohne dass die Installation neu aufgesetzt werden muss.

**Backend erreicht das JWKS nicht.** Aus dem Backend-Container testen:

```bash
docker compose -f docker-compose.dev.yml exec backend curl -sS http://host.docker.internal:8081/mod/lti/certs.php
```

Kommt hier kein JSON mit `keys`, fehlt dem Backend-Service der Eintrag `extra_hosts: ["host.docker.internal:host-gateway"]` (auf Docker Desktop normalerweise nicht nötig, auf Linux-Engines schon).

**Launch im Moodle-Frame verliert die Session.** Der App Store läuft dann als Third-Party-iframe; Browser blockieren dort Cookies ohne `SameSite=None; Secure`, und `Secure` gibt es über `http://` nicht. Für lokale Tests deshalb *Neues Fenster* als Startcontainer. Das ist derselbe Mechanismus, der später auch Keycloaks Silent-Refresh im Frame blockiert — der Grund, warum der App Store nach dem Launch ein eigenes Session-Token ausstellt.

**Moodle-Version.** Das Image ist auf `v5.2.2` gepinnt, passend zur installierten DB-Version. `latest` würde beim nächsten Pull ungefragt hochziehen und einen Upgrade-Lauf gegen die bestehende Datenbank auslösen. `AUTO_UPDATE_MOODLE=false` verhindert dasselbe auf Code-Ebene.
