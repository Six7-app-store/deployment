# 0020 — Windows-Apps werden unterstützt

**Status:** Angenommen
**Datum:** 22.10.2026
**Beteiligt:** Projektteam
<!-- TODO: Wer hat die Entscheidung getragen? Namen eintragen, bevor das ADR in die Abgabe geht. -->

## Kontext

[ADR 0001](0001-keine-windows-apps.md) hat Windows-Apps ausgeschlossen. Seine
Gründe waren die Lizenzlage und die Gleichbehandlung: Für die OpenStack-Server
gab es keine Windows-Lizenz, und die M365-A3-Lizenz der Studierenden greift
nur mit einer zusätzlichen Basislizenz, die sich nicht prüfen lässt. Dazu
kam, dass die Pipeline im Code keine einzige Windows-Stelle kannte.

Seitdem ist die technische Seite entstanden. Die Windows-App (`Six7-app-store/Windows-App`)
legt je Studierendem eine Windows-11-VM aus dem Basis-Image `Windows 11 25H2 (UEFI)`
an und richtet sie über cloudbase-init ein (siehe `docs/pipeline.md`, Abschnitt
„Die Windows-App"). Mit [ADR 0010](0010-opentofu-statt-terraform-und-packer.md)
ist sie auf OpenTofu umgestellt und baut kein Abbild mehr.

<!-- TODO: Wie wird die Lizenzlage aus ADR 0001 jetzt behandelt? Das Projektteam
muss hier festhalten, auf welcher Grundlage Windows-VMs betrieben werden
(beschaffte Lizenz, Vereinbarung mit der DHBW, Beschränkung auf einen
Nutzerkreis) und wie die Ungleichbehandlung von Nutzern ohne Basislizenz
vermieden wird. Diese Begründung stammt vom Team und ist hier nicht erfunden. -->

## Entscheidung

Der App Store unterstützt Windows-Apps. Dieses ADR löst ADR 0001 ab.

<!-- TODO: Bedingungen der Lizenzlösung ergänzen (siehe oben). -->

## Konsequenzen

**Leichter:**

- Software, die es nur für Windows gibt, lässt sich über den Store bereitstellen.
- Die Plattform zeigt mit der Windows-App, dass sie nicht auf Linux beschränkt ist.

**Schwerer:**

- Die Pipeline kennt zwei Betriebssysteme: cloud-init für Linux, cloudbase-init
  für Windows. Der Worker wartet nach ADR 0011 auf das Ende der Einrichtung über
  die serielle Konsole. Ob cloudbase-init dort ein erkennbares Ende schreibt, ist
  nicht geprüft; sonst gilt die 10-Minuten-Regel, und der Worker wartet nicht auf
  Windows-VMs.
- Windows 11 erlaubt nur eine Sitzung gleichzeitig. Jede Person braucht eine
  eigene VM (2 vCPU, 8 GB RAM), deshalb gilt eine Obergrenze von zwölf.
- Offen bleibt, was ADR 0001 als Problem benannt hat, bis das Team die Lizenzfrage
  oben beantwortet hat.

## Verworfene Alternativen

**Beim Ausschluss aus ADR 0001 bleiben.** Hätte die Lizenzfrage offen gelassen,
aber die vorhandene Windows-App ohne Einsatzmöglichkeit.
