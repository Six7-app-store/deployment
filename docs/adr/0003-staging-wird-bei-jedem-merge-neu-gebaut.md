# 0003 — Staging wird bei jedem Merge abgerissen und neu gebaut

**Status:** Angenommen
**Datum:** 18.09.2026
**Beteiligt:** Projektteam

## Kontext

Mit dem self-hosted Runner (ADR-0002) kann ein Merge wieder einen Deploy
auslösen. Damit stellt sich die Frage, was dieser Deploy tut: die laufende VM
ändern oder sie ersetzen.

Die Lage zum Zeitpunkt der Entscheidung:

- Der Staging-Stack ist über Monate von Hand nachgebessert worden. Ob der
  Zustand der laufenden VM dem entspricht, was das Repository beschreibt, weiß
  niemand sicher.
- `envs/staging/main.tf` beschreibt die VM vollständig: Image, Flavor,
  Netz, Security Group, 50-GB-Datenvolume. Das Ansible-Playbook richtet sie
  vollständig ein. Es gibt keinen Schritt, der nur von Hand ginge.
- Der Terraform-State lag in einem Postgres, das als Container
  `postgres-tfstate` **im Staging-Stack selbst** lief — also auf der VM, die ein
  `destroy` abräumen würde.
- `docker_data_volume_size_gb = 50`. Das Volume hält beide Datenbanken unter
  `/var/lib/docker` und überlebt laut Kommentar in `main.tf` ein Ersetzen der
  Instanz.
- Der Keycloak-Realm-Export bringt nur das Dienstkonto des Backends mit. Ohne
  den Seed-Lauf gibt es auf einem frischen Stack keinen Benutzer, mit dem man
  sich anmelden könnte.
- Caddy holt sein Zertifikat über `acme_ca {$ACME_CA_URL}`. Ist die Variable
  leer, gilt der Standard, also Let's Encrypt. Let's Encrypt erlaubt fünf
  identische Zertifikate pro Woche und Namensmenge.

## Entscheidung

Der Deploy führt `terraform destroy -auto-approve` aus und baut den Stack
danach mit `plan`/`apply` neu auf. Der Terraform-State wandert dafür in eine
Datei unter `/var/lib/tf-state/staging/` auf der Runner-VM, die von diesem
Terraform nicht verwaltet wird. Der Seed-Lauf ist bei einem automatischen
Deploy eingeschaltet.

## Konsequenzen

**Leichter:**

- Der Zustand von Staging ist wieder ableitbar. Was läuft, steht im Repository
  — nicht im Gedächtnis derer, die es angefasst haben.
- Terraform und Ansible werden bei jedem Merge tatsächlich ausgeführt. Ein
  Fehler in der Infrastrukturbeschreibung fällt beim nächsten Merge auf und
  nicht erst beim nächsten Neuaufbau in drei Monaten.
- Kein Zustandsdrift, keine Reste abgeschalteter Dienste, keine Datei, die
  jemand vor Wochen von Hand hingelegt hat.
- `destroy` vor `apply` ist zugleich der Nachweis, dass sich der Stack aus dem
  Nichts aufbauen lässt. Das ist sonst die Sorte Annahme, die erst im Ernstfall
  geprüft wird.

**Schwerer:**

- **Staging ist nicht mehr dauerhaft.** Ein Merge nimmt die Umgebung für die
  Dauer eines Neuaufbaus vom Netz. Wer gerade etwas vorführt oder testet, steht
  vor einer VM, die es nicht mehr gibt.
- **Die VM bekommt bei jedem Neuaufbau eine neue IPv6-Adresse.** Der
  DNS-Eintrag zieht über RFC 2136 nach, aber alles, was die Adresse
  zwischengespeichert hat, zeigt ins Leere.
- **Das Zertifikat wird jedes Mal neu ausgestellt.** Ab dem sechsten Merge
  innerhalb einer Woche verweigert Let's Encrypt, und der Stack steht ohne
  gültiges Zertifikat da. Der Hebel dagegen ist `ACME_CA_URL` in der `.env`.
- **Anwendungsdaten überleben den Neuaufbau nicht verlässlich.** Das
  50-GB-Volume soll das Ersetzen der Instanz überstehen, aber das ist eine
  Zusicherung von Cinder und keine Sicherung. Staging taugt damit nicht als Ort
  für irgendetwas, das nicht anderswo auch steht.
- **Ein Deploy dauert jetzt den vollen Aufbau**, nicht mehr die paar Sekunden
  eines Container-Austauschs. Das Timeout im Workflow steht auf 90 Minuten.
- **Ein verlorener State ist teurer als vorher.** Verschwindet die Datei auf der
  Runner-VM, sieht Terraform die vorhandenen Ressourcen nicht mehr und scheitert
  beim Anlegen am schon vergebenen Namen `staging-dhbw-appstore`. Aufräumen geht
  dann nur von Hand in Horizon.
- Der `local`-Backend kennt kein verteiltes Locking. Dass nur ein Deploy
  gleichzeitig läuft, hängt jetzt an der `concurrency`-Gruppe im Workflow und
  daran, dass es genau einen Runner gibt.

## Verworfene Alternativen

**In-place aktualisieren, also nur `terraform apply` ohne `destroy`.** Der
normale Weg, schnell und ohne Ausfallzeit. Er erhält aber genau den Zustand, der
das Problem ist: was einmal von Hand auf der VM gelandet ist, bleibt dort, und
kein Lauf würde es je bemerken. Die Anforderung war ausdrücklich ein
vollständiger Neuaufbau.

**Den Terraform-State in Postgres lassen.** Hat funktioniert, solange der Deploy
in einem Job-Container lief, und bot Locking über Advisory Locks. Die Datenbank
lief aber als Container im Staging-Stack. Beim ersten `destroy` hätte sich
Terraform die Datenbank weggelöscht, in der steht, was es gerade löscht — der
nächste Lauf hätte mit leerem State begonnen und verwaiste Ressourcen
hinterlassen, die beim Neuanlegen über den Namen kollidieren.

**Postgres auf die Runner-VM umziehen statt auf eine Datei.** Hätte das
Locking erhalten und die Zirkelabhängigkeit ebenso aufgelöst. Kostet dafür einen
weiteren dauerhaften Dienst samt Sicherung auf einer VM mit 2 GB RAM, für ein
Locking-Problem, das es nicht gibt: es existiert genau ein Runner, und die
`concurrency`-Gruppe serialisiert die Läufe ohnehin.

**Den systemd-Timer weiter benutzen und nur die Container austauschen.**
Braucht keinen Deploy und keine Ausfallzeit; er bleibt als Sicherheitsnetz
aktiv. Er tauscht aber nur Images aus — Terraform und Ansible laufen dabei nie,
und eine Änderung an der Infrastruktur erreicht Staging damit gar nicht.

**Neu bauen, dann erst das Alte abreißen (blau/grün).** Würde die Ausfallzeit
beseitigen. Setzt aber voraus, dass zwei vollständige Stacks gleichzeitig
laufen können — zweimal `gp1.large` plus zweimal 50 GB Volume — und dass die
Ressourcennamen nicht kollidieren, was sie in `main.tf` derzeit tun. Beides
wäre zu bauen; das Kontingent des Tenants dafür ist ungeprüft.
