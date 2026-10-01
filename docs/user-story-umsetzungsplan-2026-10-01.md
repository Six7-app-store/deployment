# Umsetzungspläne für die offenen User Stories

Stand: **01.10.2026**. Grundlage: [Prüfbericht mit allen 35 Stories](user-story-audit-2026-10-01.md).

Die folgenden **14 Arbeitspakete decken alle 21 teilweise umgesetzten und 4 offenen Stories ab**. Dies ist ein Umsetzungsbacklog; die vorgeschlagenen Funktionen wurden noch nicht gebaut. Bereits funktionierende Komponenten werden weiterverwendet. Ein Architekturvorschlag in diesem Dokument ist noch keine beschlossene Architekturänderung.

## Priorisierung und Abhängigkeiten

| Paket | Priorität | Stories | Ergebnis | Voraussetzung |
| --- | --- | --- | --- | --- |
| P01 | Hoch | US-31, US-32 | Anonymer Zugriff auf öffentliche Repos und GitHub-App-Zugriff auf private Repos | Betreiberkonfiguration für GitHub App |
| P02 | Hoch | US-15, US-16 | Durchgängiger Portal-/Keycloak-/Cloud-Dienst-Verbund | Tatsächlicher Portal-Dienstvertrag und Rollenmodell |
| P03 | Hoch | US-18 | Abgestimmte Moodle-Kontext-/Rollenübernahme | Vertrauensregeln und P02-Auth-Vertrag |
| P04 | Hoch | US-03, US-10 | Ubuntu-Lehrdesktop mit Java, Eclipse und IntelliJ | Abgestimmte Labor-Softwareliste |
| P05 | Hoch | US-01, US-04 | Persönliche SSH-Keys und getrennte Nutzerbereiche | Erweiterung des Account-/Template-Vertrags |
| P06 | Mittel | US-08, US-09 | Ausreichende Ressourcen und mehrere App-Instanzen pro VM | Softwareprofil P04, Isolation P05 |
| P07 | Hoch | US-13 | Anwendung/VM gezielt neu starten und Konfiguration ändern | App-Aktionsvertrag; P05/P06 für gemeinsame VMs |
| P08 | Hoch | US-05, US-27, US-29, US-30 | Mehr-VM-Übungsnetz und geprüfte IPv4-/IPv6-/Dual-Stack-Templates | Quellcode aller unterstützten App-Templates |
| P09 | Hoch | US-02, US-22 | Nachgewiesener Zugriff von privaten Rechnern und Heimnetzen | P08 und Zugang P05 |
| P10 | Hoch | US-28 | Bereitmeldung erst nach nachgewiesener Anwendungsbereitschaft | Referenz-App; P01/P08 für integrierte Abnahme |
| P11 | Hoch | US-14, US-15, US-20 | Zutreffende Softwareangaben und konsistente Übergabedokumentation | Erste Bereinigung sofort; Abschluss nach anderen Paketen |
| P12 | Mittel | US-12, US-25 | Einfacher, fachlich abgenommener Bereitstellungsablauf | P02, P04, P06, P08 |
| P13 | Mittel | US-26 | Abgestimmter Katalog tatsächlich deploybarer Apps | P01, P04, P08, P10 |
| P14 | Hoch | US-34 | Staging/Produktion ohne Secret-Ablage bei GitHub | Betreiberseitiger Secret-Speicher und Runner |

Hoch = zentraler Lehrbedarf, Integrationslücke oder Betriebsgrundlage; Mittel = Ausbau auf einer funktionsfähigen Grundlage. Keine Tages- oder Fertigstellungszusage, solange Umfang, externe Dienste und App-Repositories nicht vollständig vorliegen.

## P01 – Öffentliche Repositories und GitHub App

**Ist:** Backend verlangt einen allgemeinen Git-Token schon bei Zugriffsprüfung und Versionsauflistung. Beide Git-Services verwenden tokenhaltige URLs. Die in Compose vorhandenen GitHub-App-Variablen werden von den Settings nicht ausgewertet.

**Betroffene Stellen:** `backend/app/services/git_service.py`, `worker/app/services/git_service.py`, beide `app/config.py`, `backend/app/routers/apps.py`, `deployment/.env.example`, alle Compose-Umgebungen. Vorhandene Tests: `backend/tests/unit/test_git_service.py`, `worker/tests/test_git_service.py`.

**Schritte:**

1. Gemeinsamen fachlichen Vertrag für Repository-Adresse, Provider und Authentifizierungsstrategie festlegen. Öffentliche Repositories zunächst anonym prüfen, Tags/Releases lesen und klonen; die App-Sichtbarkeit im Katalog ist kein zuverlässiger Ersatz für die Git-Repository-Sichtbarkeit.
2. Token-Pflicht aus anonym nutzbaren Backend-Abläufen entfernen. Fehler „kein Zugriff“, „keine Releases“, Rate Limit und temporäre Provider-Störung getrennt behandeln.
3. GitHub-App-Konfiguration in Backend und Worker tatsächlich einlesen. Installation anhand des angefragten Repositorys ermitteln, kurzlebige Installationstokens anfordern und nur für das betreffende Repository verwenden. Backend braucht ebenfalls Zugriff für Metadaten und Variablenscan, nicht nur der Worker.
4. GitLab-Token und ausdrücklich aktivierten Legacy-Fallback separat behandeln. Vorhandene Invite-Funktion als Legacy kennzeichnen; fehlende GitHub-App-Installation verständlich melden.
5. Tokens nicht dauerhaft in Clone-URLs/Remote-Konfiguration speichern; temporäres Credential-Verfahren verwenden. Fehlermeldungen, Tasklogs und Exceptions redigieren, Cleanup auch im Fehlerfall prüfen.
6. Betreiberweise App-ID/Schlüssel konfigurieren, keine globalen Zugangsdaten mehr voraussetzen. Neue optionale Funktionen gemäß AGENTS mit Kill-Switch einführen; Beispielkonfiguration und alle Stacks gemeinsam pflegen.

**Abnahme:** Öffentliches GitHub-Repo lässt sich ohne jeden Git-Secret registrieren, versionieren, scannen und deployen. Privates Repo funktioniert nach Installation der jeweiligen Betreiber-App. Fehlende Installation, abgelaufener Token und API-Limit ergeben erklärbare Fehler. Ein für Betreiber A bestimmter Token wird nie für Betreiber B verwendet; Secrets erscheinen weder im Repo-Remote noch in Logs. GitLab und expliziter Fallback bleiben funktionsfähig.

**Verifikation:** Mocktests für anonymen Erstversuch, App-Installation, Token-Erneuerung, Providertrennung, Fallback und Redigierung; anschließend kontrollierter Integrationstest mit öffentlichem und privatem Testrepo. Während Unit-Tests keine externen Git-Aufrufe.

## P02 – Bestehende Portal-Dienste durchgängig nutzen

**Ist:** React-Bereich für Katalog und Deployment-Liste vorhanden. Bedienaktionen verbleiben in Vue. Caddy erwartet vom vorgeschalteten oauth2-proxy einen Access-Token. Projekt-/Budget-Dienst und persönliche Credential-Eingabe sind noch kein gemeinsamer Ablauf.

**Betroffene Stellen:** `self-service-ui/APP-STORE.md`, `self-service-ui/Caddyfile`, `self-service-ui/web/app-store/`, Portal-Auth-/Client-Provider, `backend/app/utils/auth.py`, `backend/app/utils/keycloak_auth.py`, `backend/app/routers/openstack_credentials.py`, `deployment/docker-compose.*.yml`, `deployment/docs/architektur.md`.

**Schritte:**

1. Ist-Vertrag des betriebenen Portals aufnehmen: Keycloak-Issuer/Realm, Audience, Rollen, oauth2-proxy-Tokenweitergabe sowie Projekt-/Budget-/Credential-APIs. Kein vorhandenes Budget-API als Credential-Ausgabedienst voraussetzen.
2. Portal und Backend auf den vorhandenen Keycloak abstimmen; API-Anfragen über BFF/Proxy mit passendem Access-Token versorgen. Fehlende Sitzung muss als 401 beim Client ankommen. Weitergabe von ID-Token oder unbestätigter E-Mail reicht nicht.
3. Autorisierte Projektwahl und Zuordnung zu Deployments ergänzen. Falls der bestehende Cloud-Dienst keine passenden kurzlebigen Credentials ausstellen kann, dafür einen klaren Dienstvertrag planen; bis dahin explizite, dokumentierte Credential-Eingabe beibehalten.
4. Dauerhafte UI-Grenze in einem ADR festlegen. Vorschlag: Portal wird Einstieg und Bedienoberfläche; Vue bleibt während der Migration nutzbar. Wizard, Kurs-/Teamverwaltung, persönliche Zugänge und Lifecycle-Aktionen schrittweise in den Portal-Bereich übernehmen, dieselbe Backend-API nutzen.
5. Bestehenden direkten Login und Moodle-Launch bei jeder Etappe als Regression prüfen. Bei eingebetteter Moodle-Nutzung Frame-/Cookie-/CSP-Regeln des Portals gesondert betrachten; dessen aktuelles `frame-ancestors 'none'` erlaubt kein einfaches Einbetten.

**Abnahme:** Ein echter Portal-Login reicht für Katalog, Details und berechtigte Deployments; keine Dummy-Authentifizierung als Nachweis. Projekt-/Budgetberechtigungen werden serverseitig eingehalten. Abmelden, abgelaufene Sitzung und Rollenwechsel funktionieren. Keine Secret-/Tokenkopie im Browser. Der dauerhaft zu wartende UI-Umfang ist beschrieben und fachlich abgestimmt.

**Verifikation:** Portal-Browsertests mit realem Test-Keycloak/BFF/Backend für Dozent, Student und Admin, einschließlich 401/403. Bestehende Auth-/Berechtigungstests und direkter Login bleiben grün.

## P03 – Moodle-Kurs und Rolle sicher übernehmen

**Ist:** Kurskontext/Kursrolle werden gelesen, aber Moodle-Kurs und Studiengruppe sind verschiedene Objekte. Globaler Teacher-Status wird nur bei aktiviertem Vertrauen übernommen.

**Betroffene Stellen:** `backend/app/services/lti_service.py`, `backend/app/routers/lti.py`, `backend/app/models.py`, `frontend/src/views/LtiCourseMapView.vue`, Portal-LTI-Ziel gemäß P02. Vorhandene Tests: `test_lti_launch.py`, `test_lti_context_mapping.py`, `test_lti_roster_import.py`.

**Schritte:**

1. Fachliche Abnahme klärt, ob „automatisch übernommen“ den Moodle-Kontext oder auch automatische Studiengruppenanlage und globale Dozentenrechte bedeutet. Den bestehenden bewussten Schutz nicht stillschweigend deaktivieren.
2. Kontext und Kursrolle ohne Nutzereingriff übernehmen; bestehende bestätigte Zuordnung beim nächsten Launch automatisch wiederverwenden. Unzugeordnete Kurse verständlich zum bisherigen Zuordnungs-/NRPS-Import führen.
3. Wenn automatische Anlage ausdrücklich gewünscht ist: als optionale Betreiberpolicy mit Default aus implementieren, eindeutig über `(issuer, context_id)` identifizieren, idempotent anlegen und nicht anhand gleicher Titel zusammenführen.
4. Kontextbezogene Lehrrechte von globalen OpenStack-/Adminrechten trennen. Globale Teacher-Zuordnung nur durch vertrauenswürdige Betreiberkonfiguration oder bestätigte lokale Identität; Moodle-Admin nie automatisch App-Store-Admin.
5. Änderungen an Mitgliedschaft, Kursrollen und fehlenden NRPS-Daten behandeln, bestehende explizite Identitätsverknüpfung erhalten. Jede Datenmodelländerung mit neuer Alembic-Migration begleiten.

**Abnahme:** Wiederholter Launch desselben Kurses erzeugt keine Duplikate, wählt richtigen Kontext und eigene Umgebung. Zwei Plattformen mit gleichen Kurs-IDs bleiben getrennt. Rollenwechsel gewährt keine fremden Projekte oder globale Adminrechte. Die verbleibende manuelle Erstzuordnung ist entweder fachlich akzeptiert oder durch die beschlossene optionale Automatik ersetzt.

**Verifikation:** Tests für fremden Issuer, Rollenwechsel, wiederholten Import, unzugeordneten Kurs, bestehende Zuordnung und Identitätskonflikt; kompletter Moodle-Launch mit Lehrperson und zwei Studierenden.

## P04 – Mac-Labor-Ausstattung als Ubuntu-Lehrdesktop

**Ist:** Terminal-App und beschriebene code-server-App ersetzen nicht automatisch das Mac-Labor. Java, Eclipse und IntelliJ sind lokal nicht als installierte Kombination nachgewiesen.

**Betroffene Stellen:** Neues versioniertes App-Template nach dem vorhandenen Packer-/Terraform-Muster, `Ubuntu-App/packer/` als Referenz, `deployment/seed/seed_data.py`, App-Beschreibung, Zugangsdatenvertrag in `backend/app/services/deployment_notifier.py`.

**Schritte:**

1. Mit der Lehrperson Laborinventar und eine repräsentative Übung festlegen: JDK, Eclipse, IntelliJ-Edition, Buildwerkzeuge, Plugins, Projektdateien sowie Desktop-/Remotezugang. Auf Windows verzichten; konkrete Editionen und Nutzungsbedingungen vor Paketwahl prüfen.
2. Eigenständiges Ubuntu-Lehrdesktop-Template erstellen, damit die kleine Terminal-App ihren bisherigen Zweck behält. Vorinstallierte Software mit nachvollziehbaren Versionen und prüfbaren Installationsquellen bauen.
3. Grafischen Zugang für Eclipse/IntelliJ bereitstellen, passend für macOS/Windows/Linux und Online-Lehre. Remoteprotokoll auswählen und als `protocol` im Account-Output angeben; bei mehreren Sitzungen auf derselben VM P05/P06 beachten.
4. Kursübung und vorbereitete Projekte in persönliche Bereiche ausliefern. Softwareliste und Ressourcenbedarf in App-Details anzeigen, Release freigeben und dem Katalog hinzufügen.

**Abnahme:** Frisch bereitgestellter Nutzer startet Java, Eclipse und IntelliJ ohne Paketinstallation. Die vereinbarte Laborübung lässt sich vom privaten Rechner durchführen. Versionsangaben stimmen mit dem gebauten Image überein und die gewählten Ressourcen tragen die vereinbarte Teilnehmerzahl.

**Verifikation:** Image-Smoke-Test für CLI und GUI, neue Nutzeranmeldung, Build/Run eines Java-Projekts in beiden IDEs, Test von zwei gleichzeitigen Sitzungen und anschließend vereinbarter Kurslast.

## P05 – SSH-Keys und persönliche Bereiche

**Ist:** Persönliche Konten existieren, aber nur Passwort-Provisionierung. Alle Ubuntu-Nutzer können mit sudo Rootrechte erhalten. Die Plattform kann bereits `ssh_key`-Zugangsdaten darstellen.

**Betroffene Stellen:** `backend/app/models.py`/`schemas.py` und neue Migration, Nutzer-API, `frontend/src/views/UserView.vue` bzw. Portal-Profil, Worker-Aufbau von `users`, `Ubuntu-App/terraform/variables.tf`, `Ubuntu-App/terraform/cloud-init-multi-user.yml.tpl`, Account-Outputs.

**Schritte:**

1. Öffentliche SSH-Keys erfassen, Format/Größe validieren, anzeigen und entfernen lassen. Private Schlüssel werden weder angefordert noch erzeugt oder gespeichert. Teacher-/User-Zuständigkeiten für fremde Keys ausdrücklich festlegen.
2. `users`-Vertrag rückwärtskompatibel um öffentliche Schlüssel erweitern; Worker liefert sie aus bestätigten Profildaten, cloud-init schreibt `ssh_authorized_keys` pro Nutzer. Modus Passwort/Key/Mischbetrieb als Template-Einstellung definieren.
3. Key-only-Zugänge ohne nutzbares Passwort konfigurieren, vorhandene Passwort-Apps weiter unterstützen. Für Änderungen laufender Konten einen gezielten Provisionierungsweg statt VM-Ersetzen vorsehen.
4. Allgemeine sudo-Rechte in geteilter Standard-Lehrumgebung entfernen und Home-Berechtigungen explizit setzen. Für administrative/Pentest-Übungen getrennte VMs oder ein ausdrücklich beschriebenes gesondertes Profil bereitstellen.
5. Kollisionsfreie Kontonamen und eindeutige Nutzerzuordnung sichern; nur E-Mail-Localpart zu verwenden reicht bei gleichen Namen unterschiedlicher Domains nicht. Bestehende `my-access`-Filter beibehalten.

**Abnahme:** Nutzer A meldet sich mit eigenem Key ohne Passwort an; Key von B funktioniert für A nicht. B kann As persönliche Dateien weder lesen noch verändern und keine Rootrechte erlangen. Nach Keyentzug verliert dieser Key den Zugang. Passwortmodus funktioniert weiterhin. Gleiche Localparts führen zu getrennten Konten.

**Verifikation:** Schema-/API-/Worker-/cloud-init-Tests, bestehende `my-access`-Tests und kontrollierter SSH-Test mit zwei Nutzern; neue Migration testen.

## P06 – Ressourcenprofile und mehrere Instanzen je VM

**Ist:** Ubuntu verwendet fest `gp1.small`. Mehrere code-server-Sitzungen werden in der Online-IDE-Beschreibung behauptet, deren Template muss erst geprüft werden.

**Betroffene Stellen:** App-Templates, `Ubuntu-App/terraform/variables.tf`/`main.tf`, generische Variablen-/Scope-Verträge, `backend/app/routers/quotas.py`, Wizard und Portal-Projektwahl.

**Schritte:**

1. Kapazität je Lehrprofil und Anzahl gleichzeitiger Teilnehmer bestimmen; CPU, RAM und Speicher gemeinsam betrachten. App-Manifest/Beschreibung nennt Mindest- und empfohlenes Profil.
2. Wählbares Flavor und je nach Cloud Bootvolume/Datenvolume ergänzen. Keine freien unprüfbaren Zahlen verwenden: passende vorhandene Ressourcen und Quotas berücksichtigen.
3. Für geeignete App konkrete Instanzanzahl je VM bzw. pro Nutzer anbieten. Ports, Datenverzeichnisse und Dienstnamen eindeutig vergeben; Instanzen unabhängig starten/stoppen können. Packer-Multi-Image-Support nicht als mehrere laufende App-Instanzen zählen.
4. Quota-/Budgetprüfung vor Start ergänzen; Fehler benennt fehlende Kapazität. Persistente Daten bei Redeploy/Resize und Entfernen von Instanzen ausdrücklich behandeln.

**Abnahme:** Gewählte Ressourcen werden tatsächlich provisioniert. Zwei Instanzen derselben Anwendung laufen gleichzeitig auf einer VM mit getrennten Ports und Daten; Stoppen einer Instanz beeinträchtigt die andere nicht. Die vereinbarte Kursgröße erreicht akzeptierte Reaktionszeiten und Speicherkapazität; Quotaüberschreitung wird verständlich gemeldet.

**Verifikation:** Template-/Scope-Tests, Quota-Negativfälle, Zwei-Instanz-Test und reproduzierbarer Lasttest mit vereinbarter Teilnehmerzahl. Messwerte und verwendetes Flavor dokumentieren.

## P07 – Neu starten und neu konfigurieren

**Ist:** Ganze Deployments können pausiert/fortgesetzt werden, einzelne VMs ersetzt werden. Dienstneustart und Konfigurationsänderung bestehender Apps fehlen.

**Betroffene Stellen:** `backend/app/routers/deployments.py`, `backend/app/services/lifecycle.py`, Task-/Deployment-Modelle, `worker/app/tasks.py`, Executor-Services, Lifecycle-API/Store/Composables sowie Portal-Aktionen.

**Schritte:**

1. Drei getrennte Aktionen definieren: VM-Reboot, einzelner Anwendungsneustart und Neukonfiguration. Bestehenden VM-Ersatz als separate Aktion mit klar beschriebenem Datenverhalten beibehalten.
2. App-seitige erlaubte Dienste/Instanzen und deklarative Konfiguration definieren; serverseitig validieren. Keine beliebigen Shellkommandos oder frei eingegebenen Dienstnamen aus dem Browser akzeptieren.
3. Backend berechtigt Aktion anhand Deployment, Ressource und Instanz; Tasktypen, Sperren, Statusmatrix und Auditdaten ergänzen. Worker führt Aktionen über Executor-Services aus. Ein gemeinsamer Deployment-Lock verhindert Konflikte zwischen mehreren berechtigten Personen.
4. Neukonfiguration verwendet aktuelle validierte Variablen und zeigt erwartete Änderungen vor Ausführung. Rebuild/Replace wird nicht als harmlose Konfiguration verborgen; für persistente Daten und fehlerhafte Änderungen Rollback-/Wiederherstellungsweg festlegen.
5. Nach Aktion Bereitschaft gemäß P10 prüfen, neue Zugänge/Outputs aktualisieren und anderen Teammitgliedern keine Credentials offenlegen.

**Abnahme:** Abgestürzter Ziel-Dienst wird gezielt wieder gestartet, ohne zweite App oder andere VM zu ersetzen. VM-Reboot behält Instanz-ID und vereinbarte Daten. Gültige Konfigurationsänderung wird wirksam; ungültige wird ohne Ausführung abgelehnt. Unberechtigte und konkurrierende Aktionen werden serverseitig verhindert.

**Verifikation:** API-/Worker-Tests mit gemockten Cloud-/Executor-Aufrufen, Berechtigungs-/Locktests, UI-Test der drei Aktionen; Integration mit zwei App-Instanzen und absichtlich fehlerhafter Konfiguration.

## P08 – Übungsnetz und IPv4/IPv6/Dual Stack

**Ist:** Ubuntu unterstützt die drei Modi im Code. Andere bestehende Templates wurden nicht lokal bereitgestellt. Ein Mehr-VM-Lehrnetz fehlt; IPv6-Formatierung ist nicht überall sauber.

**Betroffene Stellen:** Alle unterstützten App-Repositories, lokale Ubuntu-Referenz, `backend/app/routers/apps.py`, Variablenkomponenten, `frontend/src/services/deployment-account-matching.service.ts`, `backend/app/services/deployment_notifier.py`, Template-CI.

**Schritte:**

1. Quellcode und tatsächlich freigegebene Tags aller bestehenden Apps erfassen. Matrix je App für IPv4, IPv6, Dual Stack und benötigte Ports anlegen. Extern nicht geprüfte Templates bleiben ausdrücklich offen.
2. Vertrag für `ip_mode`, IPv4-/IPv6-Netzwahl und Verbindungsoutputs vereinheitlichen. Für Ubuntu vorhandene Umsetzung weiterverwenden; in anderen Templates ergänzen. Defaults dürfen nicht auf nur beim ursprünglichen Betreiber existente Netzwerk-IDs angewiesen sein.
3. Netzwerkbedingungen validieren: vorhandene passende Subnetze, Routing, Security Groups je Familie, Gäste-Firewall, DNS und ausgehender Paket-/Git-Zugriff. „IPv6“ bezeichnet den Nutzungsmodus; zusätzlich vorhandene private NAT-IPv4 im Cluster dokumentieren.
4. Dual-Stack-Routing testen, einschließlich Antworten über die richtige Schnittstelle, ICMPv6 und Dienst-Bind-Adressen. URLs/RDP/VNC/Host-Port-Darstellung nutzen korrekt geklammerte IPv6-Literale; SSH-Darstellung protokollgerecht prüfen.
5. Referenz-App mit mindestens zwei VMs in einem definierten Übungsnetz bereitstellen. Benötigte Kommunikationsports gezielt freigeben; Zugriff zwischen fremden Kursen standardmäßig verhindern. Netzdiagramm/Adressen in Lehrsicht anzeigen.

**Abnahme:** Für jede unterstützte App sind die zugesagten Modi getestet; fehlender Modus wird sichtbar als nicht unterstützt ausgewiesen. Netz und Zugriffsadresse entsprechen der Auswahl. Zwei Übungs-VMs kommunizieren über die vereinbarten Protokolle; fremder Kurs bekommt keinen Zugriff. Mail und UI liefern nutzbare IPv6-Verbindungsdaten.

**Verifikation:** Terraform/Packer-Validierung und Formatprüfung, Output-/Adressformat-Tests, tatsächliche Verbindungen über v4/v6/dual in einem Testprojekt. Kein Terraform-Apply und keine echte Cloud-Ressource innerhalb von Unit-Tests.

## P09 – Zugriff von privatem Rechner und aus Online-Lehre

**Ist:** Zugänge vorhanden, reale externe Erreichbarkeit noch nicht geprüft. Öffentliche IP bedeutet nicht automatisch funktionierenden Zugang aus jedem Heimnetz.

**Betroffene Stellen:** App-Zugangsbeschreibung, Hilfeansicht, Account-/URL-Outputs, Gateway/VPN-/Firewall-Konfiguration des Betreibers.

**Schritte:**

1. Prüffälle für Windows, macOS, Linux sowie Campus, VPN, IPv4-only-Heimnetz, IPv6 und Dual Stack festlegen. SSH und grafischer Zugang P04 getrennt prüfen.
2. Betreiber definiert, ob direkter Zugang, VPN oder bestehender Gateway-/Browserzugang genutzt wird. Für nicht geroutete/IPv4-only-Anschlüsse einen nachweislich funktionierenden Weg bereitstellen; einen neuen Gateway erst bei tatsächlichem Bedarf planen.
3. UI zeigt eindeutige Adresse, Port, Protokoll, persönlichen Login und nötige Netzvoraussetzung. IPv6-/Dual-Stack-Endpunkte sinnvoll anbieten, keine private NAT-Adresse als öffentliches Ziel ausgeben.
4. Kurze Anleitung und überprüfbare Fehlerhilfe für SSH-Hostkey, VPN, fehlende Route und abgelaufene Sitzung ergänzen.

**Abnahme:** Die vereinbarte Kursübung ist ohne Laborrechner von den definierten privaten Client-/Netzkombinationen durchführbar. Für IPv4-only-Anschlüsse existiert ein getesteter Zugang. Ein fehlender Zugang wird mit tatsächlicher Ursache und einem brauchbaren Handlungsschritt erklärt.

**Verifikation:** Protokollierter Ende-zu-Ende-Test aus mindestens einem externen IPv4-only-Netz und einem IPv6-/Dual-Stack-Netz, mit repräsentativen Clients. Ergebnis in Zugriffs-Matrix festhalten.

## P10 – Zuverlässigkeit und Anwendungsbereitschaft

**Ist:** Pipeline-/Task-Fehlerbehandlung und Sperren vorhanden. Ubuntu wartet 90 Sekunden, obwohl Installation/Netzinitialisierung länger dauern können. Terraform-Erfolg allein belegt keinen funktionsfähigen Login.

**Betroffene Stellen:** `worker/app/tasks.py`, Executor-Services, App-Template/Health-Vertrag, Backend-Taskstatus/Reconciler, Benachrichtigungen und Deployment-Fortschritt.

**Schritte:**

1. App-Vertrag für Bereitschaft definieren: cloud-init abgeschlossen, Konten angelegt und Zielservice erreichbar. Reine TCP-Portprüfung ist für fertige Benutzerkonten nicht immer ausreichend.
2. Explizite Phase „Anwendung wird vorbereitet“ nach Ressourcenbereitstellung ergänzen. Begrenztes Polling mit Timeout und erklärbarer Diagnose ersetzt pauschales Erfolgsmelden nach Wartezeit.
3. Erfolg/Zugangs-Mail erst nach Bereitschaft senden. Infrastrukturstatus, Anwendungsstatus und Mailfehler trennen, damit ein SMTP-Ausfall keinen erfolgreichen VM-Aufbau als fehlgeschlagen darstellt.
4. Szenarien Worker-Abbruch, Git-/Packer-Fehler, Quota, langsamer Boot, Interface-Wait, verlorenes Event, Backend-Neustart und konkurrierender Start testen. Wiederholung muss bestehende Terraform-States berücksichtigen und Doppelressourcen vermeiden.
5. Erste und wiederholte Deploymentdauer sowie gleichzeitige Kursstarts messen. Vorbereitung vor Vorlesung, Image-Wiederverwendung und Wiederherstellung in Runbook beschreiben; fachlich eine tragbare Vorlaufzeit vereinbaren.

**Abnahme:** „Bereit“ bedeutet funktionierender persönlicher Zugang und Zielanwendung. Langsamer Boot führt zu sichtbarem Warten oder begrenztem Fehler, nicht zu voreiligem Erfolg. Wiederholung nach Abbruch erzeugt keine doppelten Ressourcen. Vereinbarte Vorlaufzeit ist mit Messung belegt.

**Verifikation:** Gemockte Failure-/Timeout-/Recovery-Tests; danach kontrollierte Testprojekt-Läufe für Cold/Warm-Deploy und parallelen Kursstart. App- und Plattform-States sowie Datenhaltung bei Plattform-Neuaufbau prüfen.

## P11 – Softwareangaben und Übergabe

**Ist:** Gute Menge an Dokumentation, aber nachweisliche Widersprüche. Beschreibungen können von tatsächlichen Images abweichen.

**Betroffene Stellen:** `deployment/README.md`, `docs/architektur.md`, `pipeline.md`, `deploy-runbook.md`, Setup-Dokumente/ADRs, `Ubuntu-App/README.md`, `deployment/seed/app_descriptions/`, App-Details beider UIs.

**Schritte:**

1. Die im Prüfbericht aufgeführten Widersprüche unmittelbar gegen aktuelle Workflows/Compose/Terraform bereinigen. Historische Runbooks als überholt kennzeichnen und auf den geltenden Einstieg verweisen.
2. Windows-Entscheidung fachlich bestätigen; historische Windows-Beispiele kenntlich machen. Keine Windows-Funktion als Folgerung aus widersprüchlichen Alttexten bauen. Lizenzhinweise als dokumentierten Gesprächsstand kennzeichnen; bei Änderung aktuell fachlich/rechtlich prüfen lassen.
3. Für jede veröffentlichte App-Version verifizierte Softwareliste mit Betriebssystem, wesentlichen Programmen/Versionen, Zugangsart und Ressourcenempfehlung aus dem Build ableiten. Zunächst reicht eine releasegebundene gepflegte Beschreibung; ein strukturiertes Manifest nur bei erkennbarem Bedarf ergänzen.
4. Übergabeeinstieg für alle sechs lokalen Repositories ergänzen: Start, Konfiguration ohne Secrets, Migrationen, sichere Tests, Auth-/LTI-Flows, App-Vertrag, Plattform- versus App-State, Backup/Restore und Fehlerdiagnose.
5. SMTP-Anleitung auf Hochschul-/Betreiber-SMTP mit konfigurierbarem Host beziehen. Vorhandene Einschränkungen Login und TLS-Verfahren nennen; Gmail bleibt höchstens optionales Beispiel.
6. Nach P02 permanente UI-Grenze dokumentieren; nach weiteren Paketen Beispiele und Kommentare aktualisieren. Architekturänderungen erhalten neue ADRs.

**Abnahme:** Eine nachfolgende Person kann anhand der Dokumentation Teststack und isolierte Tests starten, eine Referenz-App verstehen und den Recovery-Weg erklären. Keine Aussage zu CI-Anbieter, State-Ablage oder Datenpersistenz widerspricht dem Code. Softwareangaben je Release stimmen mit dem Image überein.

**Verifikation:** Link-/Pfadprüfung, Vergleich mit Workflow/Compose/Template, Software-Smoke-Test und nachvollziehbarer Übergabe-Probelauf durch eine nicht am Code beteiligte Person.

## P12 – Bedienbarkeit und Dozenten-Wizard

**Ist:** Mehrstufiger Wizard und Picker existieren, aber nicht jeder Schritt ist ohne OpenStack-Wissen verständlich. Portal und Vue teilen die Abläufe noch auf.

**Betroffene Stellen:** Deployment-Wizard/Store/API, `OpenStackResourcePicker`, Quota-/Credential-Hinweise, Portal-App-Store und Hilfetexte.

**Schritte:**

1. Standardpfad „App wählen → Studiengruppe/Teilnehmer → Ressourcenprofil → Prüfen → Starten“ definieren. Geeignete betrieberspezifische Netze, Security Groups und Profile anbieten.
2. Interne Variablen ausblenden, technische Optionen als verständlichen erweiterten Bereich anbieten. Für fehlende Credentials bzw. Projektzuordnung einen klaren nächsten Schritt zeigen.
3. Zusammenfassung nennt Teilnehmerzahl, Ressourcen, Zugangsart und erwartete Dauer; blockierende Anforderungen werden vor Taskstart erklärt. Bestehende Scope-/Datei-/Allowed-Values-Validierung weiterverwenden.
4. Den Standardpfad nach P02 durchgehend im vereinbarten UI anbieten. Test mit fachlichen Dozenten, konkrete Abnahmekriterien und beobachtete Probleme dokumentieren.

**Abnahme:** Eine Dozentin/ein Dozent ohne tiefe OpenStack-Kenntnisse stellt die Referenzumgebung anhand des Wizards bereit, ohne UUIDs nachzuschlagen oder Terraform zu bedienen. Quota-/Credential-/Netzfehler sind verständlich. Studierende sehen ausschließlich ihre vorgesehenen Zugänge und Aktionen.

**Verifikation:** UI-/Browsertests für Standard- und Fehlerpfad; beobachteter Nutzertest mit fachlicher Abnahme. Keine subjektive „einfach“-Bewertung nur anhand vorhandener Komponenten.

## P13 – Deploybarer Lehrkatalog

**Ist:** Sieben Seed-Beispiel-Apps, keine lokale Verifikation der entfernten Releases. „Große Auswahl“ ist quantitativ und fachlich noch offen.

**Betroffene Stellen:** `deployment/seed/seed_data.py`, App-Beschreibungen, Admin-Freigabeworkflow und externe App-Repositories.

**Schritte:**

1. Mit Lehrenden Zielkatalog nach Lehrbedarf festlegen, insbesondere Java-Desktop, Terminal, Online-IDE sowie weitere benötigte Werkzeuge. Zahl/Kategorien als fachliches Abnahmekriterium dokumentieren.
2. Je App Repository, Tag, Verantwortlichen, Softwareinhalt, Zugangsprotokoll, Netzwerkmodi, Ressourcenbedarf und getesteten Zustand erfassen.
3. Vorhandene Referenzen auf Erreichbarkeit und Tags prüfen. Fehlende Templates/Tags reparieren oder klar als nicht verfügbar markieren; Seed-Freigaben nicht als Deploybarkeitsbeleg behandeln.
4. Freigabe an Template-Validierung und kontrollierten Smoke-Deploy binden. Beschreibung/Zugriff für Studierende gemäß bestehendem Berechtigungsmodell beibehalten.

**Abnahme:** Der abgestimmte Zielkatalog erfüllt den Lehrbedarf. Jede als nutzbar angebotene App hat mindestens eine tatsächlich geprüfte freigegebene Version; kaputte Referenzen erscheinen nicht als sofort startbare Umgebung.

**Verifikation:** Matrix aller Katalog-Apps mit Tag, Netzmodi und Ergebnis; Katalog-/Approval-Tests plus je freigegebener Referenz kontrollierter Test-Deploy, Login und Cleanup.

## P14 – Betreiberinstallationen ohne GitHub-Secrets

**Ist:** CI liest OpenStack-Zugang, SSH-Schlüssel und gesamte Stack-Env aus GitHub Secrets. Lokale Deployment-Konfiguration existiert, bildet aber keinen vollständigen automatisierten alternativen Betreiberpfad ab. Forgejo ist derzeit Versuchsaufbau.

**Betroffene Stellen:** `deployment/.github/workflows/staging.yml`, `infrastructure/ansible/staging.yml`, Runner-/Staging-/Prod-Setup, `deploy.local.env.example`, `scripts/deploy.sh`, gegebenenfalls Forgejo-Workflow nach Architekturentscheidung.

**Schritte:**

1. Konkreten Betreiberpfad festlegen. Vorschlag: dedizierter self-hosted Runner liest kurzlebige Credentials oder lokale Dateien aus einem Betreiber-Secret-Speicher; GitHub erhält nur öffentliche Konfiguration und Auftrag. Alternativ vollständig selbst gehostete CI als eigenes ADR beschließen.
2. Alle Secret-Abhängigkeiten erfassen, nicht nur OpenStack: SSH, Stack-Env, Datenbank-/State-Zugänge, GitHub-App-Key, SMTP und DNS-TSIG. Öffentliche Parameter strikt getrennt konfigurieren.
3. Workflow-Secret-Referenzen durch Betreiberauflösung am Runner ersetzen. Ansible erhält Secrets aus diesem Pfad mit passenden Dateirechten und `no_log` bei sensitiven Tasks. Keine Secrets in Git, Workflow-Artefakten, Compose-Dumps oder Logs.
4. Runner-Berechtigungen und Trigger gemäß AGENTS erhalten: keine Ausführung fremder Fork-PRs auf dem Runner mit Cloud-Zugang. Staging/Produktion verwenden getrennte Credentials und States; Produktion bleibt beim vorgesehenen Ausrollverfahren.
5. GitHub-unabhängigen Secret-Pfad mit zwei getrennten Betreiber-Konfigurationen dokumentieren; manuelles altes Deploy-Skript und aktuellen State-Vertrag abgleichen, bevor es als Alternative empfohlen wird.

**Abnahme:** Ein Staging-Aufbau funktioniert ohne in GitHub gespeicherte Infrastruktur-/Betreiber-Secrets. Alle benötigten Secrets kommen ausschließlich aus dem Betreiberpfad; keine Cross-Betreiber-Nutzung. Separates Produktionssetup ist dokumentiert, Secretwechsel und Wiederherstellung funktionieren. US-33 bleibt mit dem gewählten CI-Pfad automatisiert erfüllt.

**Verifikation:** Konfigurations-/Workflow-Prüfung mit nicht sensitiven Dummydaten, Probelauf auf dediziertem Testrunner ohne GitHub-Secrets, Log-/Artefaktprüfung und dokumentierter Rotations-/Restore-Test. Keine produktiven Zugangsdaten für die Prüfung verwenden.

## Empfohlene Umsetzungsetappen

1. **Grundlagen:** P11-Dokumentationsbereinigung; P01-Repository-Zugriff; P02-Dienstverträge; P14-Secret-Pfad. Ziel: Betreiber und nächste Entwickler können den tatsächlich geltenden Aufbau nachvollziehen.
2. **Lehrumgebung:** P04-Softwareprofil, P05-Konten/Keys, P06-Kapazität, P08-Netzwerk. Ziel: fachlich passende Referenz-App statt nur allgemeiner Deploymentmechanik.
3. **Integration und Betrieb:** P02 durchgängiger Portalablauf, P03 Moodle, P07 Aktionen, P10 Bereitschaft/Fehlerbehandlung, P09 externe Zugriffsabnahme.
4. **Abschluss:** P12 Nutzertest, P13 Katalogabnahme und Abschluss P11 Übergabe. Danach Story-Matrix mit tatsächlichen Abnahmeergebnissen aktualisieren.

Unabhängige Arbeiten können zeitlich überlappen; Abnahmen hängen von den genannten Voraussetzungen ab. Der Plan benötigt keine Veränderung laufender Produktion und keine pauschale Freigabe aller Infrastrukturaktionen.

## Prüfvorgaben je Umsetzung

| Bereich | Erforderliche Prüfung bei betreffenden Codeänderungen |
| --- | --- |
| Backend | `ruff check .` und `make test-backend-isolated` aus `deployment/`; niemals unisoliertes pytest gegen Dev-DB. Neue Modelle mit neuer Alembic-Migration. |
| Frontend | Im Container `npx vue-tsc -b` und `npx vitest --run`; Coverage-Schwelle einhalten. |
| Worker | Im Container `poetry run ruff check .`, `black --check .`, `isort --check-only .` und `pytest`; keine echten OpenStack-Aufrufe in Tests. |
| Portal | `npm run check`, Build und relevante Playwright-Tests gemäß `self-service-ui/APP-STORE.md`; echte BFF-Integration zusätzlich prüfen. |
| Infrastruktur/Templates | Terraform formatieren/validieren, Packer validieren, Konfiguration für alle betroffenen Umgebungen ergänzen; Integration nur auf vorgesehenem Test-/CI-Pfad. |
| Fachliche Abnahme | Reale Lehrübung, passende Teilnehmerzahl und privater Clientzugang; qualitative Ziele explizit bestätigen. |

## Vollständigkeitskontrolle

Die 25 noch nicht vollständig erfüllten Stories sind zugeordnet: **US-01, 02, 03, 04, 05, 08, 09, 10, 12, 13, 14, 15, 16, 18, 20, 22, 25, 26, 27, 28, 29, 30, 31, 32, 34**. US-15 ist bewusst sowohl P02 als auch P11 zugeordnet. Für bereits umgesetzte Stories sind in den Paketen gegebenenfalls Regressionen oder Dokumentationsabgleiche vorgesehen, keine unnötige Neuimplementierung.
