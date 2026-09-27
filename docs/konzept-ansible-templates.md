# Konzept: App-Templates mit Ansible

**Stand:** 27.09.2026 — Entwurf, nichts davon ist gegen OpenStack erprobt.

Anlass ist eine Rückmeldung eines Stakeholders: Die Templates richten ihre
Systeme bisher allein über cloud-init und Shell-Skripte ein. Aus cloud-init
heraus ließe sich auch Ansible starten, womit deutlich komplexere Templates
möglich wären — etwa ein vollständiges Kubernetes-Cluster aus einem einzigen
App-Template.

Dieses Dokument hält fest, was die Plattform dafür heute hergibt, welcher Weg
passt und was für einen ersten Proof of Concept offen ist. Die Plattform selbst
muss dafür **nicht** geändert werden: Ansible läuft auf den VMs, nicht im
Worker.

## Was die Plattform vorgibt

Belegt im Code, Stand `main` am 27.09.2026:

| Grenze | Wert | Quelle |
|---|---|---|
| cloud-init `user_data` | ~64 KB komprimiert (Nova-Metadatendienst) | `worker/app/tasks.py`, Warnung vor dem Plan |
| `terraform apply` | bricht nach 30 Minuten ab | `worker/app/services/terraform_executor.py` (`timeout=1800`) |
| Variablen | per `-var`; eine nicht deklarierte bricht den Lauf ab | `terraform_executor.py` |
| Packer | optional; `image_name` nur Pflicht, wenn `packer/` existiert | `template-app/README.md`, `tasks.py` |
| Zugangsdaten | Output `user_accounts`, mit `protocol` (`ssh`, `web`, …) | ADR-0007 |
| Ausgang der Worker-VM zu den App-VMs | nicht vorausgesetzt — der Worker spricht nur mit der OpenStack-API | Architektur, keine SSH-Schritte im Worker |

Die letzte Zeile ist die wichtigste: **Der Worker fährt kein Ansible gegen die
VMs.** Das bleibt so, sonst bräuchte er SSH-Zugang in jedes Projektnetz und
jede App ein Inventar. Ansible läuft deshalb auf der VM selbst (`connection:
local`) — gestartet von cloud-init.

## Drei Wege, wie das Playbook auf die VM kommt

**A — Playbook im `user_data`.** cloud-init installiert Ansible, legt das
Playbook per `write_files` ab und startet `ansible-playbook -c local`.
Einfach, keine Abhängigkeit nach außen. Scheitert an der 64-KB-Grenze, sobald
Rollen, Templates und Galaxy-Abhängigkeiten dazukommen — für ein Cluster zu
knapp.

**B — `ansible-pull` aus dem App-Repository.** cloud-init installiert Ansible
und zieht das Playbook beim ersten Boot aus Git. Keine Größengrenze. Aber:
Die VM braucht Zugriff auf das Repository (bei privaten Repos ein Token *auf
der VM*), und der Worker übergibt dem Template weder URL noch Git-Ref — das
Template müsste beides fest eintragen und zieht dann womöglich einen anderen
Stand, als die Plattform deployt hat.

**C — Ansible zur Image-Zeit, Parameter zur Boot-Zeit (Empfehlung).** Packer
baut das Image und führt dabei den Großteil des Playbooks aus
(`ansible-local`-Provisioner: Pakete, Binärdateien, Rollen). Playbook und
Rollen liegen im Image unter `/opt/app/ansible`. cloud-init startet beim Boot
nur noch den Teil, der von der Instanz abhängt, mit den Werten aus Terraform
als Extra-Vars (`ansible-playbook -c local site.yml -e @/etc/app/vars.json`).

C passt zur Plattform, weil Packer dort schon eingebaut ist: Das Image ist an
die App-Version gebunden, der Stand ist also derselbe, den die Plattform
deployt. Die VM braucht keinen Git-Zugang, und `user_data` bleibt klein. Der
Boot wird schneller, weil das Herunterladen schon im Image passiert ist. Der
Preis: Der erste Deploy einer neuen Version wartet auf den Image-Build
(heute 10–15 Minuten).

## Beispiel: k3s-Cluster aus einem Template

Skizze für den Proof of Concept, Weg C:

```
terraform/
  main.tf          1 Server + var.agent_count Agents, Security Groups
  variables.tf     users, image_name, agent_count, ip_mode, network_*
  outputs.tf       user_accounts (ssh auf den Server, kubectl eingerichtet)
  user-data.yml.tpl  schreibt /etc/app/vars.json, startet ansible-playbook
packer/
  template.pkr.hcl   Ubuntu + ansible-local
  ansible/site.yml   Rollen k3s_common (Image), k3s_server / k3s_agent (Boot)
```

- **Join-Token:** `random_password` in Terraform, per `vars.json` an Server
  und Agents. Kein Austausch zwischen den VMs nötig.
- **Reihenfolge:** Die Agents brauchen die Adresse des Servers. Terraform
  kennt sie, sobald dessen Instanz existiert, und reicht sie per
  `templatefile` weiter; die Agent-Rolle wartet, bis `:6443` antwortet.
- **Zugänge:** Je Nutzer ein Linux-Konto auf dem Server mit eigener
  kubeconfig, `protocol = "ssh"` im Vertrag. Namespaces je Team wären der
  nächste Schritt.
- **Security Groups:** 6443/tcp (API) nach außen je Adressfamilie, wie in
  Ubuntu-App (`ip_mode`). Intern zwischen den Knoten per `remote_group_id`
  auf die eigene Gruppe: 10250/tcp (kubelet), 8472/udp (Flannel VXLAN).

## Offene Fragen

1. **Wann ist ein Deploy fertig?** Terraform meldet Erfolg, sobald die
   Instanzen laufen. Das Playbook läuft danach noch Minuten. Die Templates
   überbrücken das heute mit `time_sleep`. Für ein Cluster reicht eine feste
   Wartezeit nicht. Denkbar: eine Konvention, dass das Playbook das Ende in
   eine Datei schreibt und ein Terraform-`http`-Data-Source oder ein
   Plattform-Check darauf wartet. Das wäre eine Änderung am Vertrag → eigenes ADR.
2. **Fehler im Playbook** sieht heute niemand: Die Ausgabe landet in
   `/var/log/cloud-init-output.log` auf der VM, nicht im Deployment-Log der
   Plattform. Zumindest das Ergebnis sollte als Instanz-Metadatum oder Output
   zurückkommen.
3. **Größe:** Ein Cluster je Team sprengt schnell die Quota eines Projekts.
   Die Plattform kennt Quoten (`useQuotas`); die App-Beschreibung muss den
   Bedarf nennen.

## Nächste Schritte

1. Proof of Concept als eigenes Repository nach dem Muster von `template-app`,
   zunächst mit einem Server und einem Agent.
2. Einmal von Hand mit `terraform apply` gegen ein Testprojekt, danach über die
   Plattform.
3. Offene Frage 1 entscheiden, bevor ein zweites Ansible-Template entsteht.

Für Schritt 2 braucht es Zugang zu einem OpenStack-Projekt. Ohne ihn lässt
sich der Proof of Concept nur mit `terraform validate` und
`ansible-playbook --syntax-check` prüfen.
