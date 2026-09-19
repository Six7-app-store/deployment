# 0004 — Staging kommt ohne Cinder-Volume aus

**Status:** Angenommen
**Datum:** 19.09.2026
**Beteiligt:** Projektteam

## Kontext

Die Staging-VM lief auf dem Flavor `gp1.large` mit einem angehängten
Cinder-Volume von 50 GB, auf dem `/var/lib/docker` und `/var/lib/containerd`
lagen.

Am 18.09.2026 um 20:49 lief der erste automatische Deploy nach ADR-0003. Er
scheiterte um 21:01 in `terraform apply`:

```
Error: Error waiting for openstack_blockstorage_volume_v3
94cb2762-05f5-4f8b-8457-4d6c3754fc59 to become ready: context deadline exceeded
```

Der Bestand im Projekt zu diesem Zeitpunkt und noch Stunden danach:

| Volume | Größe | Status | angelegt |
|---|---|---|---|
| `staging-dhbw-appstore-docker-data` | 50 GB | `creating` | 18.09. 20:51 |
| (ohne Namen) | 10 GB | `creating` | 18.09. 18:55 |
| (ohne Namen) | 10 GB | `in-use` | 18.09. 19:00 |
| (ohne Namen) | 10 GB | `available` | 18.09. 18:37 |

Das Kontingent lag bei 4 von 30 Volumes und 80 von 256 GB, die Compute-Werte
bei 3 von 30 Instanzen und 6 von 50 vCPU. Das 10-GB-Volume von 18:55 hing
bereits, bevor an diesem Abend irgendetwas am Deploy geändert wurde.

Zum Zeitpunkt des Abbruchs hatte `terraform destroy` die alte VM samt ihrem
Volume bereits entfernt. Die neue VM lief (`ACTIVE` seit 20:51), Ansible war
nie gestartet.

Der Flavor-Katalog des Projekts enthält unter anderem:

| Flavor | vCPU | RAM | Systemplatte |
|---|---|---|---|
| `gp1.large` | 4 | 8 GB | 10 GB |
| `k8s.node` | 4 | 8 GB | 50 GB |
| `general.small` | 2 | 8 GB | 50 GB |

Die gesamten Familien `gp1`, `cb1` und `mb1` haben 10 GB Systemplatte.

Seit ADR-0003 wird der Stack bei jedem Merge abgerissen und neu gebaut. Das
Volume wurde dabei mitgelöscht.

## Entscheidung

Wir wechseln den Flavor auf `k8s.node` und legen kein Cinder-Volume mehr an:
`docker_data_volume_size_gb = 0` in `envs/staging`, `docker_data_device: ""` im
Playbook.

## Konsequenzen

**Leichter:**

- Der Deploy hängt nicht mehr an Cinder. Das war die einzige Komponente, die
  ausgefallen ist, und sie hat den Stack in einem Zustand hinterlassen, in dem
  die alte VM weg und die neue leer war.
- Ein Schritt weniger im Playbook: kein Formatieren, kein Einhängen, kein
  Überhängen von `/var/lib/docker` und `/var/lib/containerd`. Die Tasks bleiben
  stehen, laufen aber nicht mehr.
- Ein Ausfall von Cinder kostet jetzt nichts mehr. Die VM bootet vom Image, wie
  der Lauf vom 18.09. gezeigt hat: sie war `ACTIVE`, während ihr Volume noch in
  `creating` stand.
- 50 GB statt der 10 GB, die `gp1.large` als Systemplatte hat. Der dokumentierte
  Fehlerfall „no space left on device" beim Caddy-Build ist damit ebenso weit
  weg wie vorher.

**Schwerer:**

- **Der Speicher ist an die Instanz gebunden.** Ein Volume ließe sich von einer
  Instanz lösen und an eine andere hängen; eine Systemplatte nicht. Wer Daten
  aus einer laufenden Umgebung retten will, muss sie über das Netz kopieren.
- **Es gibt keinen Weg zurück zu „Daten überleben das Ersetzen der Instanz".**
  Solange ADR-0003 gilt, ist das kein Verlust — sollte Staging wieder dauerhaft
  werden, ist diese Entscheidung als erstes zu prüfen.
- **Der Flavor heißt `k8s.node`.** Er steht im Katalog des Projekts und ist
  nicht anderweitig gebunden, aber der Name legt eine Verwendung nahe, die hier
  nicht vorliegt. Ob die DHBW das anders sieht, ist nicht dokumentiert und wurde
  nicht erfragt.
- **Die Größe ist nicht mehr frei wählbar.** Sie kommt aus dem Flavor. Mehr
  Platz heißt jetzt: anderer Flavor, und damit auch andere CPU- und RAM-Werte.
- Zwei Werte müssen weiter von Hand im Gleichklang bleiben —
  `docker_data_volume_size_gb` und `docker_data_device`. Nichts erzwingt das;
  nur die Kommentare an beiden Stellen weisen darauf hin.

## Verworfene Alternativen

**Beim Volume bleiben und auf Cinder warten.** Der einfachste Weg, und wenn der
Dienst sich fängt, funktioniert wieder alles wie zuvor. Er lässt aber offen,
wann das ist — nach über vier Stunden standen beide Volumes unverändert in
`creating` —, und er behält eine Abhängigkeit, die für diesen Aufbau keinen
Nutzen mehr hat.

**Das Zeitlimit für das Volume hochsetzen.** Hätte gegen ein *langsames* Cinder
geholfen. Hier liefert es gar nicht: ein Volume hing bereits über vier Stunden.
Ein höheres Limit hätte den Deploy nur länger blockieren lassen, bevor er
dasselbe meldet.

**`gp1.large` behalten und ohne Volume fahren.** Der dokumentierte
Rückfallweg, und er brauchte keinen Flavor-Wechsel. Bleiben aber 10 GB
Systemplatte, von denen ~7 GB frei sind, für Postgres, Keycloak, RabbitMQ,
Redis, drei Anwendungs-Images und einen Caddy-Build aus dem Quelltext. Genau
dafür ist „no space left on device" der dokumentierte Fehlerfall.

**`general.small` statt `k8s.node`.** Ebenfalls 50 GB Systemplatte und ein
Name ohne Beigeschmack. Hat aber 2 statt 4 vCPU. Der Caddy-Build aus dem
Quelltext ist der längste Schritt des Deploys; ihn auf der halben CPU laufen zu
lassen, um einen Flavor-Namen zu vermeiden, ist der schlechtere Tausch.

**Die Systemplatte über ein Boot-Volume vergrößern.** Bei Boot-from-Volume
lässt sich die Größe frei wählen, unabhängig vom Flavor. Das legt die Instanz
aber erst recht in Cinders Hand: dann hängt nicht mehr nur das Datenverzeichnis
am ausgefallenen Dienst, sondern das Booten selbst.
