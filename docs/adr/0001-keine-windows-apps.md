# 0001 — Windows-Apps werden nicht unterstützt

**Status:** Angenommen
**Datum:** 17.09.2026
**Beteiligt:** Projektteam; Gesprächspartner Infrastruktur/Lehre am 16.09.2026
<!-- TODO: Namen des Gesprächspartners eintragen, bevor das ADR in die Abgabe geht. -->

## Kontext

Der App Store soll Anwendungen für die Lehre bereitstellen. Ein Teil der
angefragten Software läuft nur unter Windows. Aus einem Gespräch am
16.09.2026 ergibt sich folgende Lage:

- **Infrastruktur.** BWCloud bietet kein Windows an. Für die OpenStack-Server
  existiert keine Windows-Lizenz; sie müsste eigens beschafft werden.
- **Aktivierung ist keine Lizenzierung.** Die DHBW betreibt einen
  Aktivierungsserver. Der *aktiviert* eine Windows-Installation, er
  *lizenziert* sie nicht. Die Lizenz bleibt ein getrenntes Problem.
- **M365 A3.** Studierende haben eine A3-Lizenz und dürften damit beliebig
  Windows-VMs erstellen und deployen, auch mit Desktop Experience — aber
  nur, wenn sie zusätzlich eine Windows-Basislizenz besitzen, mindestens
  Win10 Home, privat oder über einen Arbeitgeber. Unter Win10 Home allein
  greift die A3-Lizenz nicht.
- **Ungleiche Voraussetzungen.** Wer einen Mac nutzt, hat keine
  Basislizenz und fällt damit heraus. Im Labor hat jeder Rechner eine,
  am privaten Gerät nicht zwangsläufig.
- **Nicht prüfbar.** Das System könnte Studierende fragen, ob sie eine
  Basislizenz haben, und die Antwort speichern. Diese Selbstauskunft ist
  nicht überprüfbar. Wer wahrheitsgemäß „nein" antwortet, verliert den
  Zugang, während jemand mit derselben Ausstattung ihn durch eine falsche
  Angabe behält.

Genau das ist das Ausschlusskriterium: Es lässt sich weder sicherstellen,
dass niemand unberechtigt Windows nutzt, noch dass niemand zu Unrecht
ausgeschlossen wird. Ein Store, der Studierende nach ihrem privaten
Betriebssystem ungleich behandelt, ist hochschulrechtlich angreifbar.

Der technische Befund passt dazu: Die Deployment-Pipeline ist
Packer → Terraform → OpenStack und heute vollständig auf Linux ausgelegt.
Im gesamten Code gibt es keine einzige Windows-spezifische Stelle.

## Entscheidung

Der App Store unterstützt keine Windows-Apps. Wir setzen auf Linux/Ubuntu
und Open-Source-Anwendungen.

Die Lizenzfrage wird nicht im Produkt gelöst. Sollte sie außerhalb des
Projekts geklärt werden — etwa durch beschaffte Serverlizenzen —, entsteht
dazu ein neues ADR.

## Konsequenzen

**Leichter:**

- Jede Person kann jede App nutzen, unabhängig vom eigenen Gerät. Der Store
  braucht keine Lizenzabfrage, kein Rechtemodell auf Lizenzbasis und keine
  Sonderbehandlung für Mac-Nutzer.
- Die Pipeline bleibt einheitlich: ein Packer-Template-Format, ein
  Terraform-Provider, ein Betriebssystem.
- Keine Lizenzkosten, kein Beschaffungsvorgang, keine Abhängigkeit von
  einem Anbieter, aus dem man schwer wieder herauskommt.

**Schwerer:**

- Software, die es nur für Windows gibt, lässt sich über den Store nicht
  bereitstellen. Für solche Fälle bleibt nur der Laborrechner.
- Die Rechner der Fakultät Technik sind alt und müssen ersetzt werden;
  dort läuft teils Software, die es nicht für Windows gibt. Dieser Bedarf
  bleibt offen und ist nicht durch diese Entscheidung gedeckt.

## Verworfene Alternativen

**Windows-VMs über M365 A3.** Technisch möglich und der naheliegende Weg.
Gescheitert an der Basislizenz-Voraussetzung: sie ist nicht überprüfbar und
schließt Mac-Nutzer systematisch aus.

**Lizenzabfrage im Store.** Der Store fragt beim Deployment nach der
Basislizenz und speichert die Antwort. Gescheitert daran, dass eine
Selbstauskunft keine Prüfung ist — sie bestraft ehrliche Antworten und
verlagert ein Rechtsrisiko auf Studierende.

**Windows Data Center-Lizenz für die OpenStack-Hosts.** Würde das
Serverproblem lösen, nicht das der Endnutzer, und ist ein
Beschaffungsvorgang außerhalb der Projektlaufzeit.

**Wine.** Läuft auf Linux und macOS, emuliert Windows-APIs und braucht
keine Windows-Lizenz — auch die Grundlage von CrossOver. Verworfen als
Produktentscheidung: die Kompatibilität ist anwendungsabhängig und damit
nicht zusagbar. Für einen einzelnen, konkret benannten Anwendungsfall kann
Wine im Packer-Template einer App trotzdem der richtige Weg sein; das
bleibt eine Entscheidung je App, keine Eigenschaft des Stores.

**RDP oder TeamViewer auf Laborrechner.** Verlagert das Problem nur: wer
ohnehin eine Remote-Sitzung aufbaut, kann genauso gut eine VM oder die
Cloud nutzen — und die Lizenzfrage bleibt unverändert bestehen.
