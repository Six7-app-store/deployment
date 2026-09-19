# 0005 — Der Terraform-State der App-Deployments gehört von der Staging-VM herunter

**Status:** Angenommen
**Datum:** 19.09.2026
**Beteiligt:** Projektteam

## Kontext

Die Plattform legt für jedes App-Deployment eigene OpenStack-Ressourcen an. Der
Worker verwaltet sie mit Terraform und schreibt den State in eine Postgres-
Datenbank, ein Schema je Deployment:

```
deployment_8462675e_a4a5_409f_97f0_545208213d15 | states
deployment_7bafc1b3_9242_40fb_9eba_c0e75972f710 | states
deployment_26ac076d_1925_4aec_9a83_245b0b5eaee8 | states
   … am 19.09.2026 insgesamt zehn Schemata
```

Diese Datenbank ist der Container `postgres-tfstate` aus
`docker-compose.staging.yml`. Sie läuft damit **auf der Staging-VM** — also auf
genau der Maschine, die der Staging-Deploy verwaltet.

Seit [ADR-0003](0003-staging-wird-bei-jedem-merge-neu-gebaut.md) reißt jeder
Merge auf `main` die Staging-VM ab und baut sie neu auf. Seit
[ADR-0004](0004-staging-kommt-ohne-cinder-volume-aus.md) gibt es kein
Cinder-Volume mehr; die Docker-Daten liegen auf der Instanzplatte und
verschwinden mit der Instanz.

Was ein Merge damit auslöst, lässt sich genau beziffern:

| | |
|---|---|
| Staging-VM | wird gelöscht und neu gebaut |
| `postgres-tfstate` | verschwindet mit ihr, ohne Sicherung |
| VMs der App-Deployments | laufen unverändert weiter |
| Kenntnis über diese VMs | ist weg |

Die App-VMs stehen in einem anderen State als `envs/staging`. Ein
`terraform destroy` auf `envs/staging` spricht sie nicht an — es fährt sie weder
herunter noch löscht es sie. Sie bleiben als Waisen zurück: laufend,
Kontingent verbrauchend, nur noch von Hand in Horizon auffindbar.

Mit den States gehen auch die Zugangsdaten verloren. Die Passwörter der
Studierenden entstehen in Terraform über `random_password` und existieren
ausschließlich im State. Am 19.09.2026 waren die Passwörter der drei
Windows-VMs allein aus `deployment_8462675e_…` zu holen.

Dieselbe Zirkularität bestand für den Staging-State selbst und wurde in
ADR-0003 aufgelöst: er liegt seither als Datei auf der Runner-VM, einer
Maschine, die dieses Terraform nicht verwaltet. Für die App-Deployments gilt sie
unverändert weiter.

Der Umfang wächst mit der Nutzung. Bei drei VMs ist das Aufräumen von Hand
lästig; bei einem Kurs mit zwölf Studierenden ist es eine halbe Stunde
Handarbeit — und die Gewissheit, dass irgendwann eine VM übersehen wird.

Entscheidend ist aber nicht das Aufräumen, sondern der Neuaufbau. Wer die
verlorenen Deployments wiederherstellen will, muss sie neu ausrollen:

| App-Art | Dauer je Deployment |
|---|---|
| Ubuntu-App | 3 bis 5 Minuten |
| Windows-App | 30 bis 60 Minuten, zuzüglich Packer-Build bei neuem Commit |

Solange nur Linux-Apps liefen, war ein Merge ärgerlich. Mit der Windows-App
legt er einen laufenden Kurs für eine Dreiviertelstunde still.

## Entscheidung

Wir betreiben die Terraform-State-Datenbank auf der Runner-VM, außerhalb des
Staging-Stacks.

Konkret: Postgres 16 direkt über `apt` auf `github-runner`, lauschend auf
`10.200.1.55` und `localhost`, erreichbar allein aus `10.200.0.0/19` über die
Security Group `tfstate-db`. Der Container `postgres-tfstate` entfällt aus
`docker-compose.staging.yml`; der Worker verbindet sich über
`TFSTATE_DB_HOST` aus der `.env`.

Die Runner-VM ist damit zum zweiten Mal der Ort, an dem Zustand liegt, der
einen Neuaufbau überstehen muss — beim Staging-State hat ADR-0003 dieselbe
Wahl getroffen. Das ist bewusst dieselbe Maschine und nicht eine dritte: eine
weitere VM wäre sauberer getrennt, aber niemand betreibt sie.

## Konsequenzen

**Leichter:**

- Ein Merge auf `main` hat keine Folgen mehr für laufende App-Deployments. Die
  Plattform kennt sie nach dem Neuaufbau weiter und kann sie über die
  Oberfläche löschen.
- Die Zugangsdaten der Studierenden überleben einen Neuaufbau der Plattform.
- Kein Aufräumen von Hand in Horizon, und keine stillschweigend weiterlaufenden
  Waisen-VMs.
- Der Staging-Stack wird kleiner: ein Container und ein Datenverzeichnis
  weniger auf einer VM, die ohnehin bei jedem Merge neu entsteht.

**Schwerer:**

- **Ein weiterer dauerhafter Dienst.** Bisher ist außerhalb der Staging-VM nur
  der Runner dauerhaft. Postgres kommt als zweites hinzu, mit allem, was dazu
  gehört: Aktualisierungen, Plattenplatz, Erreichbarkeit.
- **Eine neue Abhängigkeit für jedes Deployment.** Ist der State-Host weg, kann
  der Worker nichts mehr anlegen oder löschen — heute wäre er in demselben
  Moment ohnehin mit ausgefallen, künftig nicht.
- **Jemand muss sichern.** Heute sichert niemand diese Datenbank, was folgenlos
  bleibt, weil sie ohnehin bei jedem Merge verschwindet. Sobald sie überlebt,
  ist sie die einzige Kopie von etwas Wichtigem.
- Die Verbindungszeichenfolge muss in die `.env` der Staging-VM und dort
  gepflegt werden. Ein falscher Wert fällt erst beim nächsten Deployment auf.
- **Die Runner-VM trägt jetzt zwei Rollen.** Sie führt den Staging-Deploy aus
  *und* hält den Zustand der Plattform. Fällt sie aus, steht beides. Das ist der
  bewusst eingegangene Preis dafür, keine dritte Maschine zu betreiben — die
  Last ist gering (die States sind wenige hundert Kilobyte, Packer-Builds laufen
  auf dem Worker, nicht hier), das Ausfallrisiko bleibt.
- **Die Adresse `10.200.1.55` ist per DHCP vergeben.** Wird die Runner-VM je neu
  gebaut, ändert sie sich, und `TFSTATE_DB_HOST` muss nachgezogen werden. Die
  VM steht nicht in Terraform, ein Neubau ist also ohnehin Handarbeit.

## Verworfene Alternativen

**Alles so lassen.** Kostet nichts und funktioniert, solange niemand nach `main`
merged. Genau das ist aber der Normalfall, seit ADR-0003 gilt — die Schwäche
schlägt also nicht selten zu, sondern bei jedem Merge. Sie bliebe zudem
unsichtbar: Der Deploy meldet Erfolg, und dass die Plattform ihre VMs vergessen
hat, bemerkt erst, wer sie später löschen will.

**ADR-0003 zurücknehmen und Staging bestehen lassen.** Würde das Problem
ebenfalls beseitigen, und zwar ohne neuen Dienst. Es nähme aber den Nutzen, um
dessentwillen ADR-0003 geschrieben wurde: dass der Zustand von Staging aus dem
Repository ableitbar ist und Terraform wie Ansible bei jedem Merge tatsächlich
laufen. Das Problem gegen diesen Nutzen einzutauschen, ist der schlechtere
Handel — zumal es an anderer Stelle lösbar ist.

**Eine eigene kleine VM nur für den State.** Sauber getrennt und
ressourcenseitig unkritisch — `gp1.small` genügt. Kostet eine weitere Maschine,
die jemand betreiben, aktualisieren und sichern muss, und für die es bisher
niemanden gibt. Das ist der ehrlichste Kandidat und zugleich der mit dem
höchsten Betriebsaufwand.

**Ein verwalteter Datenbankdienst der DHBW.** Nähme den Betrieb ab. Ob es einen
gibt, der für dieses Projekt nutzbar ist, wurde nicht erfragt; bekannt ist nur
Compute, Netz und Block Storage über Horizon. Nicht weiterverfolgt, weil die
Antwort vor der Abgabe nicht abzuwarten war — bleibt die naheliegendste
Verbesserung, falls die Plattform über das Projekt hinaus bestehen soll.

**Den State in die App-Repositories legen**, wie es Terraform-Anfänger oft tun.
Scheidet aus: Der State enthält die Passwörter der Studierenden im Klartext, und
die Repositories sind öffentlich. Davon abgesehen schreiben mehrere Deployments
gleichzeitig, wofür Git kein Sperrverfahren bietet.
