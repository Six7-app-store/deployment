# 0008 — Eine Studiengruppe entsteht auf Knopfdruck aus einem Moodle-Kurs

**Status:** Vorschlag
**Datum:** 19.09.2026
**Beteiligt:** Projektteam
<!-- TODO: Namen eintragen und Status auf „Angenommen" setzen, bevor das ADR in die Abgabe geht. -->

## Kontext

Ein Launch aus Moodle legt eine Zeile in `lti_contexts` an und lässt
`courseId` leer. Die Zuordnungsseite bot danach genau eine Handlung an:
eine **bestehende** Studiengruppe auswählen. Für einen Kurs, den es nur
in Moodle gibt, gab es also nichts, worauf man hätte zeigen können — der
Weg endete dort, und Teilnehmende mussten von Hand nachgetragen werden.

Drei Randbedingungen bestimmen, was überhaupt möglich ist:

**LTI kann keine Kurse aufzählen.** Der `context`-Claim trägt genau den
einen Kurs, aus dem geklickt wurde. Ein „gib mir alle Moodle-Kurse"
existiert im Protokoll nicht. Wer das will, braucht Moodle Web Services
— einen zweiten Integrationsweg mit eigenem Token.

**Die Mitgliederliste eines Kurses ist dagegen abrufbar.** LTI 1.3
kennt dafür NRPS (Names and Role Provisioning Service). Die Moodle-Seite
war bereits registriert (`ltiservice_memberships = 1`), die eingesetzte
`pylti1p3` unterstützt es. Aufgerufen hat es nur niemand.

**Die E-Mail-Adresse in einer Mitgliedschaft beweist nichts.** Sie
stammt aus einem Moodle-Profilfeld, das die Person selbst bearbeiten
kann. Das ist dieselbe Tatsache, die den Launch dazu bringt, eine
unbekannte Identität mit bekannter Adresse abzulehnen und stattdessen
eine Link-Challenge auszustellen.

Hinzu kam ein Betriebsdetail, das den Dienst vorher unbenutzbar machte:
Für NRPS muss **Moodle das Tool erreichen**, um dessen JWKS zu prüfen —
die umgekehrte Richtung zum Launch. Moodles `curlsecurityblockedhosts`
und `curlsecurityallowedport` blockieren genau das in einer lokalen
Docker-Umgebung. Siehe `docs/moodle-lti-dev.md`.

## Entscheidung

Wir legen die Studiengruppe auf **ausdrücklichen Knopfdruck** aus dem
Moodle-Kurs an und füllen sie über NRPS:
`POST /lti/contexts/{id}/import`, erreichbar für Lehrende und Admins,
angeboten auf derselben Seite wie die Zuordnung.

Dabei gilt:

- **Gematcht wird ausschließlich über `(provider, issuer, user_id)`.**
  `user_id` einer Mitgliedschaft ist derselbe Wert, den ein Launch als
  `sub` schickt. Eine bereits vergebene E-Mail-Adresse führt **nie** zu
  einem Treffer, sondern zu einem gemeldeten Übersprung — verknüpfen
  darf weiterhin nur die Link-Challenge.
- **Die globale Rolle entscheidet weiterhin `LTI_TRUST_INSTRUCTOR_ROLE`.**
  Ein Moodle-Trainer wird nicht dadurch zur Dozentin, dass sie in einer
  Mitgliederliste steht.
- **Studierende werden nur einer Studiengruppe zugeordnet, wenn sie in
  keiner sind.** Wer bereits in einer anderen ist, bleibt dort und wird
  gemeldet.
- **Jeder Übersprung wird berichtet**, mit Grund, an die Person, die den
  Import ausgelöst hat.

## Konsequenzen

**Leichter:** Ein Kurs, den es nur in Moodle gibt, wird mit einem Klick
zur Studiengruppe samt Teilnehmenden. Die Lehrperson, die ihn anlegt,
ist danach als Dozentin eingetragen und kann ihn bearbeiten — dieselbe
Mechanik wie bei `POST /courses/`.

**Leichter nachvollziehbar:** Wer nicht übernommen wurde, steht mit
Grund auf dem Ergebnisbildschirm, statt still zu fehlen.

**Schwerer:** `LtiContext.courseId` wird jetzt an zwei Stellen gesetzt
statt an einer. Die Regel aus `backend/AGENTS.md` — „`courseId` nie
automatisch füllen" — bleibt gültig und ist hier nicht verletzt: gesetzt
wird sie nur durch einen Endpunkt, den ein Mensch auslöst. Automatisiert
ist das Tippen, nicht die Entscheidung.

**Schwerer im Betrieb:** Der Import hängt an einer Verbindung, die es
vorher nicht gab — Moodle muss das Tool erreichen. Das ist eine neue
Fehlerquelle, und zwar eine, die im Launch nicht auffällt. Deshalb
unterscheidet der Endpunkt „Moodle verweigert" (502
`lti_nrps_failed`), „Moodle nicht erreichbar" (502
`lti_nrps_unreachable`) und „Dienst gar nicht angeboten" (409
`lti_nrps_unavailable`), statt alles als einen Fehler zu melden.

**Schwerer, weil Momentaufnahme:** Der Import läuft einmal. Wer sich
später in Moodle einschreibt, kommt nicht automatisch dazu. Das ist
bewusst — siehe unten.

## Verworfene Alternativen

**`LtiContext.courseId` beim Launch automatisch füllen.** Wäre der
kürzeste Weg und ist genau das, was `backend/AGENTS.md` verbietet. Ein
Moodle-Kurs und eine Studiengruppe sind verschiedene Dinge: derselbe
Moodle-Kurs kann von zwei Studiengruppen belegt werden, und eine
Studiengruppe besucht mehrere Moodle-Kurse. Automatisch geraten hängt
Leute an die falsche Gruppe, und zwar unbemerkt.

**Mitglieder über die E-Mail-Adresse zuordnen.** Der naheliegende Weg,
weil die Adresse in jeder Mitgliedschaft steht. Er übergibt ein
bestehendes Konto — mit OpenStack-Zugangsdaten, Deployments und
Teammitgliedschaften — an jede Person, die diese Adresse in ihr
Moodle-Profil eintragen kann. Dieselbe Überlegung wie beim Launch, und
dieselbe Antwort: die Adresse ist ein Hinweis, kein Nachweis.

**Bei jedem Launch neu synchronisieren.** Hielte den Stand aktuell.
Verworfen für den ersten Schritt: ein Sync muss Austritte behandeln, und
„in Moodle ausgetragen" auf „aus der Studiengruppe entfernen"
abzubilden, entfernt Leute aus einer Gruppe, die ihr Studium bestimmt,
nicht ihre Moodle-Einschreibung. Das ist eine eigene Entscheidung und
gehört in ein eigenes ADR.

**Moodle Web Services statt LTI.** Ein nächtlicher Job über
`core_course_get_courses` würde Kurse auch ohne Klick liefern und wäre
das, was „alle Kurse rausziehen" wörtlich verlangt. Er braucht einen
Moodle-Service-Account, ein dauerhaftes Token mit weitreichenden Rechten
und einen Platz, an dem dieses Token liegt — für den Prototyp ein
deutlich größerer Angriffs- und Betriebsaufwand als der Knopf, den eine
Lehrperson ohnehin einmal drückt. Bleibt die Option, wenn Kurse ohne
jede Interaktion erscheinen sollen.
