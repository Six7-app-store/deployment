# 0002 — Das Zugangsprotokoll ist ein eigenes Feld, kein Wert in `type`

**Status:** Angenommen
**Datum:** 19.09.2026
**Beteiligt:** Projektteam
<!-- TODO: Namen eintragen, bevor das ADR in die Abgabe geht. -->

## Kontext

Eine App liefert ihre Zugangsdaten über den Terraform-Output
`user_accounts`. Je Konto standen darin bisher `username`, `ip`, `port`,
`auth` und `type`. `type` beantwortet **was** `auth` ist:
`password | ssh_key | oauth | none`.

Die Plattform braucht daneben eine zweite Auskunft: **wie** die Person
die Maschine erreicht. Sie stand nirgends, also hat die
Deployment-Seite sie geraten — ein Konto ohne Web-URL wurde als SSH
behandelt. Für eine App, die über RDP erreichbar ist, kam dabei
`ssh -p 3389 …` heraus: ein Kommando, das der Zielrechner nicht
beantwortet. Zusätzlich verlinkte die Oberfläche `http://<ip>:3389` als
wäre es eine Web-Oberfläche.

Der naheliegende Vorschlag war, `type: "rdp"` zu setzen. Das
vermischt zwei Fragen in einem Feld: eine RDP-Maschine hat trotzdem ein
Passwort, und die Mail müsste dann aus `type` gleichzeitig ableiten,
welche Zeile sie druckt und welches Feld sie als Credential behandelt.

Ein Konto trägt beide Angaben unabhängig voneinander: eine
Linux-VM ist `password` + `ssh`, eine Windows-VM `password` + `rdp`,
eine Maschine mit hinterlegtem Schlüssel `ssh_key` + `ssh`.

## Entscheidung

Wir führen im `user_accounts`-Vertrag das eigene Feld `protocol` ein:

```hcl
protocol = "ssh" | "rdp" | "vnc" | "web" | "none"
```

`type` bleibt unverändert die Aussage über `auth`. Beide Felder setzt
die App in ihrem eigenen Terraform-Output; die Plattform reicht sie
unverändert durch und rendert daraus die Zugangszeile — ein
SSH-Kommando, eine `host:port`-Adresse für einen RDP/VNC-Client oder
eine URL.

`protocol` ist optional. Fehlt es, wird es hergeleitet, damit bereits
ausgerollte Apps unverändert dargestellt werden: aus dem Altfeld
`authtype`, aus `type == "ssh_key"`, aus dem bekannten Port
(22/3389/5900) und zuletzt aus der bisherigen Annahme „`ip` plus `port`
ist eine Web-Oberfläche". Eine ausdrückliche Angabe der App schlägt
jede Herleitung.

Die Herleitung steht zweimal im Code — in
`backend/app/services/deployment_notifier.py` für die Mail und in
`frontend/src/services/deployment-account-matching.service.ts` für die
Deployment-Seite. Das ist bewusst: beide Repos sind getrennt
deploybar, und dieselbe Doppelung besteht bereits für die Zuordnung
Mitglied ↔ Konto.

Dieses ADR sagt nichts über Windows aus. `protocol` ist Mechanik, die
jedes Protokoll gleich behandelt; die Lizenzfrage aus
[ADR-0001](0001-keine-windows-apps.md) bleibt unberührt und offen. Eine
App, die RDP ausliefert, wird durch dieses Feld nicht zu einer vom
Store unterstützten Windows-App.

## Konsequenzen

**Leichter:**

- Eine App sagt selbst, wie man sie erreicht, statt dass die Plattform
  aus Portnummern rät. Neue Protokolle sind ein Wert mehr in einer
  Liste, keine neue Bedingung in der Vue-Vorlage.
- Mail und Deployment-Seite zeigen dieselbe Zeile, weil beide dieselbe
  Auflösung fahren.
- Kein Datenbankfeld, keine Migration: `user_accounts` wird ohnehin
  unverändert durchgereicht.

**Schwerer:**

- Zwei Felder, die man verwechseln kann. Wer `type: "rdp"` schreibt,
  bekommt weiterhin die Herleitung — nicht eine Fehlermeldung.
- Die Herleitungsregeln liegen doppelt vor und müssen zusammen
  geändert werden. Beide Stellen verweisen im Kommentar aufeinander,
  Tests halten die Regeln je Repo fest.
- Die Protokollliste ist ein Vertrag: ein Wert, den eine App schreibt
  und die Plattform nicht kennt, fällt still in die Herleitung zurück.

## Verworfene Alternativen

**`type: "rdp"`.** Ein Feld für zwei Fragen. Eine RDP-Maschine mit
Passwort hätte danach keine Möglichkeit mehr zu sagen, dass `auth` ein
Passwort ist; Mail und Oberfläche müssten das wieder raten.

**Nur aus dem Port herleiten, ohne neues Feld.** Deckt 3389 und 5900 ab
und sonst nichts. Eine App, die RDP auf einem anderen Port anbietet
oder SSH auf 2222, bliebe falsch dargestellt — und die App hätte kein
Mittel, die Fehlannahme zu korrigieren.

**Das Protokoll je App in der Datenbank pflegen.** Eine Spalte auf
`apps`, gesetzt beim Anlegen. Verworfen, weil die App-Vorlage die
Wahrheit hält und sie je Team oder je Konto unterschiedlich sein kann;
eine Spalte wäre eine zweite Quelle, die mit dem Terraform-Output
auseinanderläuft.
