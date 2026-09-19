# Moodle für die Staging-Vorführung herrichten

Diese Anleitung richtet die **deployte** Moodle-Instanz so ein, dass die
komplette Anbindung vorführbar ist: Anmeldung per Launch, Studiengruppe aus
einem Moodle-Kurs anlegen, Aktivität an eine App binden.

Sie gilt für die Instanz aus [`moodle-infrastruktur.md`](moodle-infrastruktur.md),
nicht für das Dev-Moodle aus `docker-compose.moodle.yml` — das beschreibt
[`moodle-lti-dev.md`](moodle-lti-dev.md).

Gebraucht werden:

* SSH auf die Moodle-VM und `docker exec` auf den Container `moodle`
* Moodle-Administrationszugang im Browser (für Schritt 6 und den Durchlauf)
* die URL des App Stores, im Folgenden `https://appstore.<zone>.users.dhbw.site`
* ein App-Store-Konto mit der Rolle **Dozent** (siehe Schritt 5)

Reihenfolge einhalten. Schritt 1 muss vor allem anderen laufen, Schritt 5 vor
dem Durchlauf.

---

## 1. Werkzeug registrieren und die Dienste einschalten

```bash
docker exec moodle php /var/www/html/local_register_lti_tool.php \
    --appstore=https://appstore.<zone>.users.dhbw.site
```

Das Skript ist idempotent: ein bereits registriertes Werkzeug wird nicht
erneut angelegt, sondern nur ergänzt und ausgelesen.

**Auch dann laufen lassen, wenn das Werkzeug längst registriert ist.** Es
schaltet zwei Dienste ein, die `lti_add_type()` nicht von selbst setzt und die
älteren Registrierungen deshalb fehlen:

| Dienst | Wofür | Fehlt er, dann |
|---|---|---|
| `ltiservice_memberships` | Teilnehmerliste abrufen (NRPS) | „Studiengruppe aus Moodle anlegen" bricht mit `lti_nrps_unavailable` ab |
| `contentitem` | Deep Linking | kein Knopf „Inhalt auswählen", jede Aktivität bleibt ungebunden |

Die Ausgabe nennt sie beim Namen:

```
Dienst ltiservice_memberships eingeschaltet.
Dienst contentitem eingeschaltet.
```

Kommen diese Zeilen beim zweiten Aufruf nicht mehr, ist alles gesetzt.

### Gegenprobe

```bash
docker exec moodle-postgres psql -U moodle -d moodle -c \
  "select name, value from mdl_lti_types_config
   where name in ('contentitem','ltiservice_memberships','sendname','sendemailaddr')
   order by name;"
```

Alle vier müssen auf `1` stehen. `sendname` und `sendemailaddr` setzt das
Skript beim Anlegen; ohne sie kommen Name und Adresse leer an, und ein Launch
scheitert mit `lti_missing_email`.

Die sieben `LTI_*`-Zeilen aus der Ausgabe gehören in `STAGING_ENV_FILE` —
zusammen mit `LTI_PRIVATE_KEY_B64` und `LTI_SESSION_SECRET`, die Moodle nicht
ausstellt. Siehe [`moodle-infrastruktur.md`](moodle-infrastruktur.md),
Schritt 6.

---

## 2. Testkonten anlegen

Am schnellsten über die CLI. **Die Adressen entscheiden über das Verhalten**,
deshalb lohnt ein Blick darauf, bevor die Datei geschrieben wird:

* Eine Adresse, die im App Store **noch nicht** existiert → der Import legt ein
  neues Konto an.
* Eine Adresse, die dort **schon** zu einem Konto gehört → der Import
  überspringt sie mit `link_required`. Das ist kein Fehler, sondern der
  Schutz: die Adresse ist ein Moodle-Profilfeld, das die Person selbst ändern
  kann. Für die Vorführung ist genau ein solches Konto sehr nützlich.

```bash
docker exec -i moodle sh -c 'cat > /tmp/demo-users.csv' <<'CSV'
username;password;firstname;lastname;email;course1;role1
demo.dozent;<PASSWORT>;Dana;Dozent;demo.dozent@dhbw.de;DEMO25;editingteacher
demo.eins;<PASSWORT>;Alina;Eins;demo.eins@dhbw.de;DEMO25;student
demo.zwei;<PASSWORT>;Bela;Zwei;demo.zwei@dhbw.de;DEMO25;student
demo.drei;<PASSWORT>;Cem;Drei;demo.drei@dhbw.de;DEMO25;student
CSV
```

`<PASSWORT>` vorher ersetzen. Moodles Standardrichtlinie verlangt acht Zeichen
mit Groß-, Kleinbuchstabe, Ziffer und Sonderzeichen. **Nicht ins Repository
committen** und nach der Vorführung ändern oder die Konten löschen.

Wer den Übersprung zeigen will, hängt eine fünfte Zeile mit der Adresse eines
bestehenden App-Store-Kontos an, Rolle `student`.

Der Kurs muss vor den Nutzern existieren — also erst Schritt 3, dann der
Upload. Die Reihenfolge hier ist absichtlich andersherum beschrieben, weil die
Adressüberlegung die wichtigere ist.

---

## 3. Kurs anlegen

```bash
docker exec -i moodle sh -c 'cat > /tmp/demo-course.csv' <<'CSV'
shortname,fullname,category
DEMO25,Cloud Computing Demo,1
CSV

docker exec moodle php \
  /var/www/html/public/admin/tool/uploadcourse/cli/uploadcourse.php \
  --mode=createnew --file=/tmp/demo-course.csv
```

Danach die Nutzer aus Schritt 2:

```bash
docker exec moodle php \
  /var/www/html/public/admin/tool/uploaduser/cli/uploaduser.php \
  --file=/tmp/demo-users.csv --uutype=2 --uupasswordnew=0 --uuupdatetype=0
```

`SMTP connect() failed` in der Ausgabe betrifft nur die Willkommensmail und ist
folgenlos. Entscheidend sind die Zeilen `In 'DEMO25' als '…' eingeschrieben`.

> Die CLI-Werkzeuge liegen unter `public/`, die Administrations-CLI (`cfg.php`,
> `purge_caches.php`) dagegen unter `/var/www/html/admin/cli/`. Moodle 5 hat
> nur den Web-Root nach `public/` verschoben.

Danach die Anmeldedateien wieder entfernen:

```bash
docker exec moodle rm -f /tmp/demo-users.csv /tmp/demo-course.csv
```

---

## 4. Werkzeug im Kurs sichtbar machen

**Dieser Schritt ist neu in Moodle 5 und wird am häufigsten übersehen.** Ein
Werkzeug lässt sich dort nicht mehr direkt in der Aktivität konfigurieren; es
muss erst als *Kurstool* freigegeben werden. Sonst endet das Anlegen mit:

> Die manuelle Erstellung von Tools ohne die Definition von Kurstools wird
> nicht mehr unterstützt.

Im Browser: **Kurs → Mehr → LTI Externe Tools**, beim Werkzeug
**„In Aktivitätsauswahl anzeigen"** anhaken.

Direkt: `https://<moodle>/mod/lti/coursetools.php?id=<kursid>`

Das Registrierungsskript setzt `coursevisible` bereits auf
`ACTIVITYCHOOSER`, wodurch der Haken bei neuen Kursen in der Regel schon
sitzt. Prüfen kostet zehn Sekunden, Suchen am Vorführungstag deutlich mehr.

---

## 5. Die Rollenfrage klären — vor dem Durchlauf

`LTI_TRUST_INSTRUCTOR_ROLE` steht auf `false`. Eine Moodle-Trainerin **ohne**
App-Store-Konto kommt damit als `STUDENT` an, landet auf `/deployments` und
sieht weder die Zuordnungsseite noch den Import-Knopf. Der Durchlauf unten
bricht dann in Schritt 6.1 ab.

Zwei Wege, einer davon reicht:

**A — Konto verknüpfen (empfohlen, ohne Deploy).** Ein bestehendes
App-Store-Konto mit der Rolle Dozent nehmen und `demo.dozent` in Moodle
**dieselbe E-Mail-Adresse** geben. Dann:

1. Aktivität in Moodle starten → Launch wird abgelehnt, die Seite
   „Konto bestätigen" erscheint.
2. „Jetzt anmelden und verknüpfen" → direkte Keycloak-Anmeldung mit dem
   App-Store-Konto.
3. Aktivität erneut starten → jetzt als Dozent angemeldet.

Das kostet einmal einen direkten Login und gilt danach dauerhaft. Es ist auch
der Weg, den echte Lehrende gehen werden.

**B — Flag umlegen.** `LTI_TRUST_INSTRUCTOR_ROLE=true` in `STAGING_ENV_FILE`
und neu ausrollen. Damit bekommt **jede Person, die in irgendeinem Kurs dieses
Moodles Trainer:in ist**, im App Store die Dozentenrolle — und damit das Recht,
Deployments gegen OpenStack anzulegen. Kostet zusätzlich einen
Staging-Neuaufbau, weil das Secret erst beim nächsten Deploy greift.

---

## 6. Durchlauf

### 6.1 Anmeldung und Zuordnung

Als `demo.dozent` in Moodle anmelden, im Kurs die Aktivität *Externes Tool*
anlegen (Aktivitätsauswahl → das registrierte Werkzeug) und öffnen.

Erwartet: der App Store öffnet sich **ohne Login-Maske** auf der Seite
„Moodle-Kurs zuordnen", mit dem Kursnamen aus Moodle.

Landet ihr stattdessen auf `/deployments`, ist die Rolle das Problem →
Schritt 5.

### 6.2 Studiengruppe aus Moodle anlegen

Auf „Studiengruppe aus Moodle anlegen" klicken.

Erwartet: „Studiengruppe ‚Cloud Computing Demo' angelegt", darunter die Zahlen
und — falls ihr die fünfte Zeile aus Schritt 2 angelegt habt — die
Übersprungsliste mit der Begründung.

Bricht es mit „Moodle gibt die Teilnehmerliste für diesen Kurs nicht heraus"
ab, fehlt `ltiservice_memberships` **oder** der Kurskontext wurde vor Schritt 1
aufgezeichnet. In beiden Fällen: Schritt 1 laufen lassen und die Aktivität
**einmal neu öffnen** — die NRPS-Adresse kommt mit dem Launch, nicht aus der
Datenbank.

### 6.3 Aktivität an eine App binden

Zweite Aktivität *Externes Tool* anlegen. Im Formular erscheint
**„Inhalt auswählen"** — fehlt der Knopf, fehlt `contentitem` aus Schritt 1.

Klicken → der App Store zeigt „Welche App soll diese Aktivität öffnen?" →
App wählen → „Übernehmen".

Erwartet: Moodle füllt den Aktivitätsnamen mit dem App-Namen, und unter
*Mehr anzeigen → Benutzerdefinierte Parameter* steht `app_id=<uuid>`.
Speichern.

### 6.4 Studierendensicht

Abmelden, als `demo.eins` anmelden, beide Aktivitäten öffnen.

Der Unterschied ist der Punkt der Vorführung:

| Aktivität | Ziel |
|---|---|
| ungebunden | Liste der eigenen Umgebungen |
| gebunden | direkt in die Umgebung dieser App |

**Dafür muss die Person Umgebungen haben.** Ohne Umgebungen landen beide auf
derselben leeren Liste und der Unterschied ist unsichtbar. Die Studierenden
entstehen erst durch 6.2 — die Zuweisung geht also erst danach, und sie
braucht mindestens zwei Umgebungen, davon eine der gebundenen App.

Das rechtzeitig einplanen: ein echtes Deployment gegen OpenStack dauert und
kann scheitern. Wer es am Vorführungstag erst startet, führt unter Umständen
einen Fortschrittsbalken vor.

---

## 7. Prüfliste

```bash
# Liefert das Backend sein Keyset?
curl -s -o /dev/null -w '%{http_code}\n' https://appstore.<zone>.users.dhbw.site/lti/jwks   # 200

# Sind die Dienste an?
docker exec moodle-postgres psql -U moodle -d moodle -c \
  "select name, value from mdl_lti_types_config
   where name in ('contentitem','ltiservice_memberships');"                                  # beide 1
```

| Symptom | Ursache |
|---|---|
| Launch endet auf „Konto bestätigen" | Adresse gehört schon zu einem App-Store-Konto — so gewollt, siehe Schritt 5 A |
| Launch endet auf `/deployments` statt Zuordnungsseite | Rolle ist `STUDENT`, siehe Schritt 5 |
| Import: `lti_nrps_unavailable` | `ltiservice_memberships` fehlt, oder Aktivität seither nicht neu geöffnet |
| Import: `lti_nrps_failed` / `lti_nrps_unreachable` | Moodle erreicht den App Store nicht — siehe unten |
| Kein Knopf „Inhalt auswählen" | `contentitem` fehlt |
| „Manuelle Erstellung von Tools …" | Werkzeug nicht als Kurstool freigegeben, Schritt 4 |
| Launch: `lti_missing_email` | `sendemailaddr` steht nicht auf `1` |

### Wenn Moodle den App Store nicht erreicht

Für NRPS muss **Moodle das Backend** aufrufen, um dessen JWKS zu prüfen — die
umgekehrte Richtung zum Launch, und die einzige, die Moodles
cURL-Sicherheitsfilter sieht. Das Symptom führt in die Irre: der Launch läuft
unbeirrt weiter, während der Token-Endpunkt 404 mit einer HTML-Seite antwortet,
darin

```
mod_lti\local\ltiopenid\jwks_helper::fix_jwks_alg(): Argument #1 ($jwks) must be of type array, null given
```

Auf Staging sollte das nicht auftreten: der App Store läuft über HTTPS auf 443
unter einem öffentlich auflösbaren Namen, und genau daran scheitert der Filter
im Dev-Setup (Port 8000, Docker-Gateway in `192.168.0.0/16`). Tritt es doch
auf, stehen die beiden Stellschrauben `curlsecurityallowedport` und
`curlsecurityblockedhosts` mit Befehlen in
[`moodle-lti-dev.md`](moodle-lti-dev.md).

Prüfen lässt es sich direkt:

```bash
docker exec moodle php -r '
define("CLI_SCRIPT", true);
require("/var/www/html/config.php");
require_once($CFG->libdir . "/filelib.php");
$h = new \core\files\curl_security_helper();
var_dump($h->url_is_blocked("https://appstore.<zone>.users.dhbw.site/lti/jwks"));'
```

`bool(false)` heißt: erlaubt.

---

## 8. Nach der Vorführung

Die Testkonten tragen echte Anmeldedaten und sind über Moodle erreichbar.
Löschen oder Passwörter ändern — *Website-Administration → Nutzer/innen →
Nutzerkonten*. Der Demo-Kurs kann bleiben; er kostet nichts und die
Zuordnung im App Store bleibt gültig.

Der App Store behält die angelegte Studiengruppe samt Mitgliedern. Wer sie
loswerden will, löscht sie über die Kursverwaltung — die `lti_contexts`-Zeile
verliert dabei ihre Zuordnung und der nächste Launch bietet die Zuordnung
erneut an.
