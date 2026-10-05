# 0010 — Die Plattform verwaltet Infrastruktur nur noch mit OpenTofu, ohne Image-Bau

**Status:** Angenommen
**Datum:** 05.10.2026
**Beteiligt:** Projektteam

## Kontext

Die Anforderungen haben sich geändert: Statt Terraform und Packer soll
ausschließlich OpenTofu eingesetzt werden, ohne Rückwärtskompatibilität zu
Terraform.

Bis dahin lief ein App-Deployment in zwei Werkzeugen. Packer baute aus
`packer/template.pkr.hcl` (oder einem `packer/<key>/` je Image) ein
Glance-Image mit vorinstallierter Software, Terraform startete aus
`terraform/` die VMs von diesem Image. Der Worker koordinierte das: ein
Redis-Lock gegen doppelte Builds, eine Prüfung, ob das Image schon in Glance
liegt, und `image_name`-Variablen, die er in Terraform einspeiste. Das
Backend las Packer- und Terraform-Variablen getrennt, das Frontend zeigte
sie in zwei Spalten.

OpenTofu ersetzt Terraform eins zu eins. Für Packer gibt es dagegen keinen
Ersatz in OpenTofu. Geprüft am 05.10.2026:

- OpenTofu selbst baut keine Images; auch das Changelog bis v1.14 enthält
  nichts dergleichen.
- Der OpenStack-Provider kennt keinen Snapshot einer laufenden Instanz.
  `openstack_images_image_v2` lädt nur fertige Image-Dateien hoch,
  etwa von einer URL.

Die Infrastruktur dieses Repositorys verwaltet neben Staging zwei
dauerhafte VMs: `moodle` (State auf der Runner-VM) und `forgejo` (State
beim Operator). Beide laufen und sollen nicht neu gebaut werden.

## Entscheidung

Wir verwalten die Infrastruktur der Plattform und der App-Deployments mit
OpenTofu und bauen keine Images mehr; eine App richtet ihre VM beim Boot über
cloud-init (`user_data`) in ihrem OpenTofu-Code selbst ein.

Im Einzelnen:

- **App-Vertrag:** genau ein Verzeichnis `tofu/` mit `*.tofu`-Dateien,
  Variablen in `tofu/variables.tofu`. Ein Repo mit `packer/` oder
  `terraform/` lehnt der Worker mit einer Meldung ab, die den Umbau nennt;
  das Backend antwortet auf `GET /apps/{id}/variables` mit 422.
- **Endung `.tofu`:** Terraform liest diese Dateien nicht. Damit ist
  nachweisbar, dass nichts mehr unbemerkt mit Terraform läuft.
- **Kein Altbestand:** Alle App-Deployments und Staging werden vor dem
  Umstieg mit dem alten Stand abgerissen. OpenTofu beginnt mit leerem State;
  der Staging-State liegt deshalb in einem neuen Verzeichnis
  `/var/lib/tofu-state/staging/`, damit der alte Terraform-State unter
  `/var/lib/tf-state/` nie versehentlich gelesen wird.
- **Version:** OpenTofu 1.13.1, mit festen SHA256-Summen im Worker-Image und
  im Forgejo-Job-Image, per `opentofu/setup-opentofu` in den Workflows.
- **Übergangsinsel:** `infrastructure/terraform/` behält nur `envs/moodle`,
  `envs/forgejo` und deren Kopie von `modules/openstack_vm` und bleibt bei
  Terraform, bis die beiden VMs umgezogen sind. Alles andere liegt unter
  `infrastructure/tofu/`.

Nicht umbenannt wird, was OpenTofu selbst so nennt: der `terraform { }`-Block,
`TF_VAR_*`/`TF_LOG`, `.terraform/`, `.terraform.lock.hcl`, `terraform.tfstate`
und die Provider-Adresse `terraform-provider-openstack/openstack`.

## Konsequenzen

Leichter wird:

- Ein Werkzeug statt zwei. Im Worker fallen Packer-Executor,
  Template-Erkennung, Build-Lock und die Image-Variablen weg; ein Deploy hat
  acht Phasen statt elf oder mehr.
- Das Backend kennt nur noch eine Variablenquelle. `source` und
  `template_key` verschwinden aus der API, `userInputVar` hat einen Block
  `tofu`, das Ergebnisfeld heißt `tofu_outputs`. Gespeicherte Zeilen stellt
  Migration `661aa473b510` um.
- Der Wizard zeigt eine Variablenkarte statt einer Packer- und einer
  Terraform-Spalte.
- Die `.trivyignore` des Workers unterdrückt drei statt 48 Befunde: so
  viele brachten die Go-Module in den Terraform- und Packer-Binaries mit.

Schwerer wird:

- **Erster Boot dauert länger.** Was Packer einmal ins Image gebacken hat,
  installiert cloud-init jetzt bei jedem Start. Eine App mit viel Software
  braucht entsprechend länger, bis sie bereit ist.
- **Kein Image-Cache.** Zwei Deployments derselben App installieren beide
  von vorn; Paketquellen müssen beim Boot erreichbar sein.
- **Alle App-Repos müssen umgebaut werden**, bevor sie wieder deploybar
  sind: `terraform/` → `tofu/`, `*.tf` → `*.tofu`, Provisionierung aus
  `packer/` in `user_data`. Bis dahin scheitert jedes Deploy einer Alt-App
  mit der Ablehnungsmeldung. Der Marker `@platform:internal` entfällt; außer
  `users` injiziert die Plattform nichts mehr.
- **Umstieg von Hand:** Deployments und Staging abreißen, den
  State-Speicher der App-Deployments leeren und im Dev-Stack das Volume
  `postgres_tfstate_data` neu anlegen (der Default-Benutzer heißt jetzt
  `tofu`). Die Reihenfolge steht in `docs/deploy-runbook.md`.
- **Zwei Werkzeuge in der Übergangszeit.** Solange `moodle` und `forgejo`
  bei Terraform bleiben, prüft `infra-qa.yml` beide Bäume, und das Modul
  `openstack_vm` liegt doppelt vor. Änderungen am Modul müssen bis dahin in
  beiden Kopien landen.

## Verworfene Alternativen

**Packer behalten, nur Terraform ersetzen.** Hätte den Image-Cache
erhalten. Widerspricht aber der Anforderung, ausschließlich OpenTofu
einzusetzen.

**Image-Bau mit OpenTofu nachbauen.** Eine Builder-VM per OpenTofu starten,
provisionieren und als Image sichern. Weil der Provider keinen
Instanz-Snapshot kennt, ginge das nur über `local-exec` mit der
`openstack`-CLI — also nicht mehr „nur OpenTofu", und mit eigener
Fehlerbehandlung für hängende Builds und verwaiste Builder-VMs.

**Terraform-State übernehmen.** OpenTofu kann State von Terraform in vielen
Fällen lesen. Für App-Deployments und Staging hätte das Migrationscode und
eine Prüfung gegen State aus Terraform 1.16 verlangt, für Ressourcen, die
ohnehin neu gebaut werden dürfen. Für `moodle` und `forgejo` ist genau das
der spätere Weg; deshalb bleiben sie vorerst unangetastet.

**`.tf` beibehalten.** OpenTofu liest `.tf` genauso. Dann ließe sich aber
nicht mehr erkennen, ob ein Repo schon umgestellt ist, und Terraform könnte
denselben Code weiter ausführen.
