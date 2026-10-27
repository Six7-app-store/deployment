# Kubernetes-Lernumgebung

Eine Kubernetes-Lernumgebung für Hochschulkurse. Jedes Team bekommt einen **eigenen
Kubernetes-Cluster** (k3s, ein Node) auf einer eigenen VM. Jedes Teammitglied meldet
sich per SSH an und findet `kubectl` fertig eingerichtet vor — mit einem eigenen
Namespace und einem gemeinsamen Team-Namespace.

## Vorinstallierte Software

- k3s (stable channel) mit Traefik als Ingress-Controller und local-path-Storage
- kubectl (inkl. Tab-Vervollständigung, Alias `k`)
- helm
- k9s
- Git, curl, jq, vim, nano, htop

## Lernverzeichnis

Jeder Nutzer findet nach dem Login unter `~/k8s-kurs/` eine `LIES_MICH.txt` mit
Kurzreferenz und ersten Schritten sowie Beispiele unter `beispiele/` (einzelner Pod,
Deployment mit Service, NodePort-Service und weitere).

## VM-Deployment

Es wird **eine VM pro Team** deployed (Basis-Image `Ubuntu 24.04`, Flavor
`gp1.small`). Die Zahl gleichzeitiger Team-Cluster ist über `max_teams` begrenzt
(Standard 15).

## Deployment-Dauer

Ein Deployment läuft in zwei Phasen:

1. `tofu apply` legt die VMs an.
2. Beim ersten Start richtet cloud-init die VM ein (Phase `VM_SETUP`): k3s und die
   Werkzeuge werden installiert, die Konten und Namespaces angelegt. Der Store meldet das
   Deployment erst als fertig, wenn diese Einrichtung abgeschlossen ist.

Die Dauer hängt von der Einrichtung ab. Messwerte folgen nach der Abnahme auf Staging.

## Konfigurierbare Variablen

| Variable | Beschreibung |
|---|---|
| `image_name` | Basis-Image (Ubuntu 24.04 empfohlen) |
| `flavor_name` | VM-Größe des Team-Clusters |
| `ip_mode` | Adressfamilie: `ipv4`, `ipv6` (Standard) oder `dual` |
| `network_uuid` | Netz mit öffentlicher IPv6, für `ipv6` und `dual` |
| `network_v4_uuid` | Netz mit öffentlich gerouteter IPv4, für `ipv4` und `dual` |
| `floating_ip_pool` | Name des External Networks für Floating IPs |
| `shared_secgroup_id` | ID der gemeinsamen Security Group |
| `max_teams` | Obergrenze gleichzeitiger Team-Cluster |
