# 0009 — Eine deep-verlinkte Moodle-Aktivität bindet an eine App, nicht an eine Umgebung

**Status:** Vorschlag
**Datum:** 19.09.2026
**Beteiligt:** Projektteam
<!-- TODO: Namen eintragen und Status auf „Angenommen" setzen, bevor das ADR in die Abgabe geht. -->

## Kontext

Bisher hieß jede Moodle-Aktivität nur „der App Store". Wo ein Klick
landet, riet `resolve_launch_target`: Kurs-Mapping anwenden, unter den
Umgebungen suchen, in denen die Person Mitglied ist, und bei **genau
einem** Treffer direkt hineinspringen — sonst Liste. Das ist eine
Heuristik, und sie versagt zuverlässig, sobald jemand zwei Umgebungen
hat.

LTI 1.3 kennt dafür **Deep Linking**: Beim Anlegen der Aktivität fragt
Moodle das Tool, worauf sie zeigen soll. Das Tool zeigt eine Auswahl,
die Lehrperson entscheidet, und die Entscheidung wird als
`custom`-Parameter **in der Moodle-Aktivität** gespeichert. Jeder
spätere Launch trägt sie mit. Das Raten entfällt für gebundene
Aktivitäten.

Die Frage war, *worauf* gebunden wird. Das Schema lässt beides zu:
`user_to_deployments` ist many-to-many, eine Umgebung kann viele Nutzer
haben und ein Nutzer viele Umgebungen. Aus dem Datenmodell allein ist
nicht abzuleiten, ob ein Kurs eine gemeinsame Umgebung hat oder jede:r
Studierende eine eigene — beides kommt vor.

## Entscheidung

Wir binden an eine **App** (`custom: { app_id: … }`), nicht an eine
konkrete Deployment-Instanz.

Beim Launch aus einer gebundenen Aktivität filtert
`resolve_launch_target` die Umgebungen der Person auf diese App. Bleibt
genau eine übrig, wird sie direkt geöffnet; sonst die Liste.

Die Auswahlseite liegt unter `/lti/auswahl` hinter derselben Schranke
wie die Kurs-Zuordnung (`teacher`/`admin`). Die signierte Antwort wird
**aus dem Browser** an Moodles `deep_link_return_url` gepostet, nicht
vom Backend: diese URL authentifiziert die *Moodle-Sitzung der
Lehrperson*, und die hat nur deren Browser.

## Konsequenzen

**Leichter:** Eine Aktivität „Nextcloud" führt jede:n Studierende:n in
die eigene Nextcloud-Umgebung, auch wenn jemand daneben noch drei andere
Umgebungen hat. Genau der Fall, an dem die bisherige Heuristik scheitert.

**Robuster:** Die Bindung überlebt das Abreißen und Neuanlegen einer
Umgebung, weil sie keine Deployment-ID enthält. Sie funktioniert
unverändert, egal ob der Kurs sich eine Umgebung teilt oder jede:r eine
eigene hat.

**Sicherheitsneutral:** Die Bindung ist ein **Wegweiser, keine
Berechtigung** — dieselbe Eigenschaft wie beim Kurs-Mapping. Gefiltert
wird nur unter den Umgebungen, in denen die Person ohnehin Mitglied ist.
Ein manipulierter `app_id`-Parameter kann deshalb nichts freischalten;
er kann die Auswahl nur leeren, und dann landet man auf der Liste.

**Schwerer:** `POST /lti/launch` beantwortet jetzt zwei Nachrichtentypen.
Die Verzweigung hängt an `is_deep_link_launch()` und ist damit an einer
Stelle, aber der Endpunkt hat zwei Ausgänge statt einem.

**Schwerer:** Hat jemand zwei Umgebungen **derselben** App, bleibt es bei
der Liste. Die Bindung macht diesen Fall nicht schlimmer als vorher,
löst ihn aber auch nicht.

**Betrieblich:** Moodle bietet die Auswahl nur an, wenn am Tool
`contentitem = 1` gesetzt ist. Ohne das ändert sich nichts und
Aktivitäten bleiben ungebunden — bestehende Aktivitäten laufen
unverändert weiter, weil ein fehlender `custom`-Parameter genau der alte
Pfad ist.

## Verworfene Alternativen

**An eine konkrete Umgebung binden (`deployment_id`).** Wäre eindeutig
und ohne jede Auflösung zur Launch-Zeit. Scheitert an dem Fall, dass
jede:r Studierende eine eigene Umgebung hat: die Aktivität zeigt dann
auf die Umgebung einer einzelnen Person, alle anderen sind dort keine
Mitglieder und fallen auf die Liste zurück — schlechter als vorher.
Zusätzlich zeigt die Aktivität ins Leere, sobald die Umgebung neu
gebaut wird. Bleibt denkbar als *zusätzlicher* Ressourcentyp, wenn
gemeinsame Kursumgebungen der Normalfall werden.

**Beides anbieten und die Lehrperson entscheiden lassen.** Deckt beide
Betriebsarten ab, kostet aber zwei Auflösungspfade, zwei Fehlerbilder
und eine Erklärung, die im Moment niemand braucht. Nachrüstbar, ohne
das Bestehende anzufassen: ein zweiter `custom`-Schlüssel.

**Die Antwort vom Backend an Moodle posten.** Wäre ein Schritt weniger
im Frontend. Geht nicht: `deep_link_return_url` erwartet die
Moodle-Sitzung der Lehrperson, und die liegt im Browser. Das Backend
signiert, der Browser überbringt.
