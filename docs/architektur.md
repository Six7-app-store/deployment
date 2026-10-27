# Architektur: Self-Service-Portal und Moodle/LTI-Anbindung

Stand: 23.10.2026

Der App Store hat einen zweiten Weg hinein bekommen. Bisher meldeten sich
alle direkt über Keycloak an; jetzt kommen Studierende aus Moodle, ohne zu
wissen, dass es einen App Store gibt. Das ändert drei Dinge an der
Architektur: eine zweite Sitzungsart, zwei neue Tabellen und eine
rollenabhängige Ansicht.

## Bausteine

Zwei Grafiken: die erste zeigt, wer mit dem Backend spricht, die zweite, was
hinter „Deployment starten" passiert.

**Lesehilfe.** Ein Pfeil zeigt vom Aufrufer zum Aufgerufenen, die Antwort
läuft jeweils zurück. Eine Linie ohne Pfeil ist ein Zugriff auf Datenbank,
Redis oder RabbitMQ; die Beschriftung sagt, was der Dienst dort tut. Blau sind
die drei eigenen Dienste, grau die Infrastruktur im Compose-Stack, gestrichelt
umrandet alles außerhalb davon. Orange ist LTI.

```mermaid
%%{init: {"flowchart": {"nodeSpacing": 40, "rankSpacing": 50, "curve": "monotoneY"}}}%%
flowchart TB
  M["<b>Moodle</b><br/>LTI-1.3-Plattform"]:::extern
  F["<b>Frontend</b><br/>Vue 3 im Browser"]:::code
  B["<b>Backend</b><br/>FastAPI"]:::code
  P[("<b>PostgreSQL</b><br/>App-Daten")]:::infra
  R[("<b>Redis</b><br/>DB 1")]:::infra
  D["<b>Deployment-Pfad</b><br/>nächste Grafik"]:::code
  K["<b>Keycloak</b><br/>direkter Login"]:::infra

  M -->|"Launch über den Browser,<br/>Abruf /lti/jwks"| B
  B -->|"certs.php, token.php,<br/>Mitgliederliste (NRPS)"| M
  F -->|"REST-API,<br/>Live-Status (SSE)"| B
  F -->|"Login (OIDC)"| K
  B ---|"lesen/schreiben"| P
  B ---|"nonce,<br/>Launch-Daten"| R
  B -->|"Deployment<br/>starten"| D
  B -->|"Schlüssel,<br/>Admin-API"| K

  classDef code fill:#dbe9fb,stroke:#1c5fb4,stroke-width:2px,color:#0b1f3a
  classDef infra fill:#e3e7ec,stroke:#5c6b7a,stroke-width:1px,color:#1b2430
  classDef extern fill:#ffffff,stroke:#3d4a57,stroke-width:2px,stroke-dasharray:6 4,color:#1b2430
  linkStyle 0,1 stroke:#d9480f,stroke-width:3px
```

```mermaid
%%{init: {"flowchart": {"nodeSpacing": 60, "rankSpacing": 90, "curve": "monotoneY"}}}%%
flowchart TB
  B["<b>Backend</b><br/>FastAPI"]:::code
  S["<b>SMTP</b><br/>Mailversand"]:::extern
  Q["<b>RabbitMQ</b><br/>Task-Queue"]:::infra
  R[("<b>Redis</b><br/>DB 0")]:::infra
  W["<b>Worker</b><br/>Celery"]:::code
  G["<b>Git-Repos</b><br/>der Apps"]:::extern
  T[("<b>OpenTofu-State</b><br/>eigene PostgreSQL")]:::infra
  OS["<b>OpenStack</b><br/>bwCloud"]:::extern

  B -->|"Zugangsdaten<br/>mailen"| S
  B ---|"Tasks einstellen,<br/>Events empfangen"| Q
  B ---|"Ergebnisse<br/>lesen"| R
  Q ---|"Tasks abholen,<br/>Fortschritt senden"| W
  R ---|"Ergebnisse<br/>schreiben"| W
  W -->|"App-Repo<br/>klonen"| G
  W ---|"State lesen/<br/>schreiben"| T
  W -->|"OpenTofu: anlegen,<br/>ändern, löschen<br/>API: stoppen, starten,<br/>neu starten, Konsolen-Log"| OS
  B -->|"Versionen und<br/>Variablen lesen"| G
  B -->|"Zugangsdaten prüfen,<br/>Ressourcen lesen"| OS

  classDef code fill:#dbe9fb,stroke:#1c5fb4,stroke-width:2px,color:#0b1f3a
  classDef infra fill:#e3e7ec,stroke:#5c6b7a,stroke-width:1px,color:#1b2430
  classDef extern fill:#ffffff,stroke:#3d4a57,stroke-width:2px,stroke-dasharray:6 4,color:#1b2430
```

Redis steht in beiden Grafiken: dieselbe Instanz, zwei getrennte Datenbanken
(siehe [Betrieb](#betrieb)).

Neu gegenüber dem letzten Stand sind die beiden **orangefarbenen Kanten**
zwischen Moodle und Backend, dazu Redis DB 1 für die Launch-Daten. Der
Deployment-Pfad und das Frontend-REST bleiben unverändert — die
LTI-Anbindung hängt sich an die Authentifizierung, nicht an die Fachlogik.

Der Deployment-Pfad läuft seit [ADR 0010](adr/0010-opentofu-statt-terraform-und-packer.md)
nur noch mit OpenTofu, ohne Image-Bau: Jede App bringt `tofu/` mit und
richtet ihre VMs beim ersten Start per cloud-init ein. Der Worker meldet ein
Deployment erst als fertig, wenn cloud-init in allen VMs durchgelaufen ist —
er liest dafür das Konsolen-Log über die OpenStack-API
([ADR 0011](adr/0011-deploy-wartet-auf-die-einrichtung-der-vms.md)). Der
State liegt in einer eigenen PostgreSQL außerhalb der Staging-VM
([ADR 0005](adr/0005-tfstate-der-app-deployments-gehoert-von-der-staging-vm-herunter.md)).

Werden die VMs eines Deployments außerhalb des App Stores gelöscht, merkt das
eine Schleife im Backend (`app/services/vm_presence.py`, alle zehn Minuten):
Sie liest die Server-IDs aus dem gespeicherten OpenTofu-State, fragt sie mit
den Zugangsdaten der Eigentümer:in ab und setzt `deployments.vm_missing_since`,
wenn keine VM mehr gefunden wird. Die Oberfläche zeigt dann einen Hinweis und
bietet „Eintrag entfernen" an; automatisch gelöscht wird nichts
([ADR 0021](adr/0021-fehlende-vms-werden-markiert-nicht-geloescht.md)).
Denselben Ausweg gibt es, wenn der letzte Abbau gescheitert ist, etwa weil das
App-Repository gelöscht wurde
([ADR 0022](adr/0022-gescheiterter-abbau-laesst-eintrag-entfernen.md)).

## Zwei Wege hinein

| | Direkter Login | Launch aus Moodle |
|---|---|---|
| Wer | Lehrende, Admins, Studierende am Rechner | Studierende, die in Moodle auf die Aktivität klicken |
| Identität | Keycloak (OIDC) | Moodle signiert ein `id_token` (LTI 1.3) |
| Sitzung | Keycloak-Token mit stiller Erneuerung | eigenes Token des Backends, 120 Minuten, ohne Erneuerung |
| Einstiegspunkt | `/login` | `/lti/callback` |

**Warum eine eigene Sitzung statt Keycloak?** Aus Moodle heraus ist der App
Store ein Drittanbieter-Frame. Keycloaks stille Token-Erneuerung läuft über
ein verstecktes iframe, und Browser blockieren dort die Cookies — der Nutzer
flöge mitten in der Sitzung raus. Deshalb stellt das Backend nach dem Launch
ein eigenes, kurzlebiges Token aus. Läuft es ab, klickt man in Moodle erneut;
das kostet einen Klick und prüft nebenbei die Kursmitgliedschaft neu.

Beide Wege münden in **eine** Authentifizierungs-Abhängigkeit
(`app/utils/auth.py`), die anhand des `iss`-Claims entscheidet, welcher
Prüfer läuft. Für jeden Endpunkt dahinter ist der Unterschied unsichtbar.

## Der Launch

In beiden Ablaufgrafiken sind durchgezogene Pfeile Anfragen und gestrichelte
die Antworten darauf. Die Nummern geben die Reihenfolge an; Kästen ohne Pfeil
sind Erläuterungen, etwa was ein Dienst dabei intern prüft oder speichert.

```mermaid
%%{init: {"sequence": {"width": 110, "actorMargin": 30}}}%%
sequenceDiagram
    autonumber
    participant M as Moodle
    participant U as Browser
    participant B as Backend
    participant F as Frontend (Vue)

    rect rgba(28, 95, 180, 0.12)
    Note over M,F: Phase 1 · Login-Initiierung
    U->>M: Klick auf die Aktivität
    M-->>U: Formular, das sich<br/>selbst absendet
    U->>B: POST /lti/login (iss, login_hint, target_link_uri)
    Note over U,B: dazwischen: eine Prüfseite<br/>testet Cookies, dann kommt<br/>/lti/login noch einmal
    Note right of B: nonce in Redis DB 1<br/>ablegen
    B-->>U: 302 → Moodle<br/>/mod/lti/auth.php<br/>(state + nonce,<br/>state auch als Cookie)
    end

    rect rgba(217, 72, 15, 0.12)
    Note over M,F: Phase 2 · Launch
    U->>M: GET /mod/lti/auth.php
    M-->>U: Formular mit id_token<br/>(signiert, mit nonce)
    U->>B: POST /lti/launch<br/>(id_token, state)
    Note right of B: state mit Cookie<br/>vergleichen, nonce<br/>in Redis prüfen<br/>und löschen
    B->>M: GET /mod/lti/<br/>certs.php
    M-->>B: öffentliche<br/>Schlüssel
    Note right of B: Signatur, iss,<br/>aud, exp,<br/>deployment_id<br/>prüfen, Identität<br/>(issuer, sub) in<br/>user_identities<br/>suchen
    end

    alt Identität unbekannt, E-Mail gehört schon einem Konto
        B-->>U: 302 → Frontend<br/>/lti/link?challenge=…
        Note over U,B: einmal direkt anmelden,<br/>dann wird verknüpft
    else Identität bekannt oder neu
        Note right of B: Nutzer anlegen<br/>oder aktualisieren,<br/>Kurs in lti_contexts<br/>merken, Sitzungs-<br/>token (120 min)<br/>ausstellen, Ziel<br/>berechnen
        B-->>U: 302 → Frontend<br/>/lti/callback<br/>?token=…&target=…
        U->>F: lädt<br/>/lti/callback
        Note left of F: Token aus der<br/>URL nehmen,<br/>Ziel prüfen (nur<br/>In-App-Pfade)
        F->>B: GET /users/me<br/>(Bearer: Sitzungstoken)
        B-->>F: Nutzerdaten
        Note left of F: zeigt das Ziel,<br/>z. B. /deployments/<br/>{id}
    end
```

Der Umweg in Phase 1 ist Absicht: das Tool muss den Austausch anfangen, damit
es die `nonce` vergibt, die im Token zurückkommen muss. Weil das Backend
sie beim Prüfen aus Redis löscht, lässt sich ein abgefangenes Token nicht
wiederholen.

`target` ist neu. Das Backend rechnet **vor** dem Redirect aus, wo dieser
Launch landen soll, statt alle auf ein Dashboard zu schicken. Das Frontend
nimmt nur In-App-Pfade an; alles andere fällt auf das Dashboard zurück, damit
ein manipulierter Launch-Link keine Weiterleitung nach außen erzeugen kann.

## Datenmodell: zwei Tabellen dazu

| Tabelle | Zweck |
|---|---|
| `user_identities` | Ein lokales Konto kann mehrere Identitäten haben. Schlüssel ist `(provider, issuer, subject)` — die Moodle-Nutzer-ID, nicht die E-Mail-Adresse. |
| `lti_contexts` | Merkt sich den Moodle-Kurs, aus dem ein Launch kam, und die Studiengruppe, der er zugeordnet wurde. |

Zwei Entwurfsentscheidungen stecken darin:

**Die E-Mail-Adresse identifiziert niemanden.** Sie ist ein bearbeitbares
Moodle-Profilfeld. Trifft ein unbekannter Launch auf eine Adresse, die schon
einem Konto gehört, wird er abgelehnt und der Mensch muss sich einmal direkt
anmelden — erst diese beiden Hälften zusammen verknüpfen die Identität.

**Ein Moodle-Kurs ist keine Studiengruppe.** `lti_contexts.courseId` bleibt
leer, bis jemand, der den Kurs unterrichtet, die Zuordnung setzt. Raten würde
Leute an die falsche Gruppe hängen. Die Zuordnung ist ein **Wegweiser, keine
Berechtigung**: sie wählt unter den Umgebungen aus, in denen jemand ohnehin
Mitglied ist, und fügt keine hinzu.

## Die dritte Kante: Mitgliederliste aus Moodle

Zum Zuordnen gehört der Fall, dass es noch nichts zum Zuordnen gibt. Dann legt
eine Lehrperson die Studiengruppe **aus dem Moodle-Kurs** an und übernimmt die
Teilnehmenden über **NRPS** (`POST /lti/contexts/{id}/import`). Begründung und
verworfene Alternativen: [ADR 0008](adr/0008-studiengruppe-aus-moodle-kurs-anlegen.md).

Das ist die erste Stelle, an der **das Backend Moodle nach Kursdaten fragt**,
statt nur Launches entgegenzunehmen:

```mermaid
%%{init: {"sequence": {"width": 110, "actorMargin": 30}}}%%
sequenceDiagram
    autonumber
    participant L as Lehrende:r<br/>(im Frontend)
    participant B as Backend
    participant M as Moodle

    L->>B: POST /lti/contexts/{id}/import<br/>(Name der Studiengruppe)
    Note over B: Kurs prüfen: noch nicht zugeordnet,<br/>memberships_url bekannt?

    rect rgba(217, 72, 15, 0.12)
    Note over B,M: Access Token holen
    B->>M: POST /mod/lti/token.php<br/>(client_credentials,<br/>JWT mit Tool-Schlüssel signiert)
    opt Tool-Schlüssel nicht in Moodles Cache
        M->>B: GET /lti/jwks
        Note over B,M: Schritt 3 scheitert lokal, siehe unten
        B-->>M: öffentlicher Tool-Schlüssel
    end
    M-->>B: Access Token
    end

    B->>M: GET memberships_url (NRPS)<br/>(Bearer: Access Token)
    M-->>B: Mitglieder + Rollen
    Note over B: Studiengruppe anlegen,<br/>Mitglieder über (issuer, user_id)<br/>zuordnen oder anlegen,<br/>lti_contexts.courseId setzen
    B-->>L: 201: Studiengruppe + Bericht,<br/>wer nicht übernommen wurde
```

Schritt 3 ist der, der lokal scheitert: Moodles cURL-Sicherheitsfilter lässt
weder Port 8000 noch das Docker-Gateway zu, und der Launch merkt davon
nichts, weil er ohne diese Richtung auskommt. Siehe `docs/moodle-lti-dev.md`.

Die beiden Entscheidungen von oben gelten hier unverändert: gematcht wird über
`(issuer, user_id)`, nie über die Adresse, und `courseId` setzt weiterhin nur
ein Mensch — der Knopf ist die Entscheidung, der Import nur ihre Ausführung.

## Rollen und Sichten

Drei Schichten, bewusst getrennt:

| Schicht | Wo | Frage |
|---|---|---|
| Rolle | `app/utils/permissions.py` | Darf diese *Art* Mensch das überhaupt? |
| Capability | `app/utils/capabilities.py` | Darf *dieser* Mensch *dieses* Objekt? |
| Ansicht | `src/router/index.ts`, `useRole` | Was zeige ich, damit niemand ins Leere klickt? |

**Das Frontend versteckt nur, das Backend verbietet.** Die Router-Guards und
ausgeblendeten Knöpfe sind Bequemlichkeit; jede Entscheidung fällt noch einmal
serverseitig.

Daraus folgt die Rollenteilung im Self-Service-Portal: **Lehrende richten
Umgebungen ein, Studierende bekommen Zugang.** Eine Studierende kann kein
Deployment anlegen — der Endpunkt lehnt es mit `role_required` ab —, sieht
dieselbe Liste unter dem Namen „Meine Umgebungen", und erhält über
`/deployments/{id}/my-access` ausschließlich ihre **eigenen** Zugangsdaten;
die der Teamkolleg:innen stecken in denselben OpenTofu-Outputs und werden
serverseitig herausgefiltert.

Eine Trainerrolle in Moodle macht dabei niemanden zum Lehrenden im App Store.
Die Rolle regelt den Zugriff auf fremde OpenStack-Ressourcen; wer in irgendeinem
Moodle-Kurs Trainer ist, darf darüber nicht entscheiden. Der Schalter dafür
(`LTI_TRUST_INSTRUCTOR_ROLE`) steht auf `false`.

## Was bewusst gleich geblieben ist

- **Der Deployment-Pfad.** OpenTofu → OpenStack (seit ADR 0010 ohne
  Packer). Ein aus Moodle gestarteter Nutzer durchläuft dieselbe Kette wie
  jeder andere.
- **Ein Satz Endpunkte.** Es gibt keine „LTI-Variante" der Fach-API. Der
  Unterschied endet bei der Authentifizierung.
- **Eine Ansicht pro Seite.** Keine zweite Oberfläche für Studierende, sondern
  dieselbe Seite mit zwei Datenquellen — sonst driften beide auseinander und
  jede Korrektur fällt doppelt an.

## Betrieb

Moodle läuft im Dev-Stack als eigenes Compose-Projekt, getrennt vom App Store
(eigenes Netz, eigene Datenbank). Aufbau und Registrierung stehen in
[`moodle-lti-dev.md`](moodle-lti-dev.md).

Die LTI-Launch-Daten liegen in **Redis DB 1**, Celery benutzt **DB 0** — sonst
räumt ein Broker-Flush die laufenden Launches mit weg.

`LTI_ENABLED` ist der Kill-Schalter. Steht er auf `false`, antworten alle
`/lti`-Endpunkte mit 503, und der direkte Login bleibt davon unberührt.
