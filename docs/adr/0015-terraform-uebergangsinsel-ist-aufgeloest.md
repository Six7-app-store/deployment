# 0015 — Die Terraform-Übergangsinsel ist aufgelöst

**Status:** Angenommen
**Datum:** 22.10.2026
**Beteiligt:** Projektteam

## Kontext

[ADR 0010](0010-opentofu-statt-terraform-und-packer.md) hat die Plattform auf
OpenTofu umgestellt und zwei Umgebungen ausgenommen, weil sie laufende VMs
verwalten, die nicht neu gebaut werden dürfen: `envs/moodle` und
`envs/forgejo`. Sie lagen als „Übergangsinsel" unter `infrastructure/terraform/`,
samt einer zweiten Kopie des Moduls `openstack_vm`. Dafür hielt die CI
`hashicorp/setup-terraform` vor, die Runner-VM ein Terraform-Binary, und der
Harness formatierte `.tf`-Dateien mit `terraform fmt`.

Forgejo ist mit [ADR 0014](0014-forgejo-wird-nicht-weiterbetrieben.md)
entfallen. Übrig blieb Moodle.

## Entscheidung

`envs/moodle` zieht nach `infrastructure/tofu/envs/moodle` um und nutzt das
dortige Modul. Der Ordner `infrastructure/terraform/` entfällt, einschließlich
der Modul-Kopie. Die CI installiert kein Terraform mehr.

Ressourcen- und Moduladressen bleiben unverändert, damit der bestehende State
passt. Der State wird einmalig von `/var/lib/tf-state/moodle/` nach
`/var/lib/tofu-state/moodle/` übernommen (Anleitung in
`docs/moodle-infrastruktur.md`). Der Plan danach muss „No changes" sagen; die
Moodle-VM wird nicht neu gebaut, ihre Kursdaten liegen auf der Instanzplatte.

## Konsequenzen

- Es gibt ein Werkzeug, ein Modul und einen Format-Befehl (`tofu fmt`).
- Das Terraform-Binary kann von der Runner-VM entfernt werden, und
  `/var/lib/tf-state/` nach einer vereinbarten Frist ebenfalls.
- Die Übernahme des States ist ein Schritt auf echter Infrastruktur und gehört
  einer Person mit Zugang. Der Code darf erst nach ihr auf `develop`, sonst
  zeigt der Branch Code, der zu keinem State passt.
- Schlägt die Übernahme fehl (der Plan zeigt mehr als „No changes"), bleibt der
  Rückfall über `import {}`-Blöcke. Der alte State wird nie gelöscht, nur
  umbenannt.

## Verworfene Alternativen

**Die Insel behalten.** Hielte zwei Werkzeuge, zwei Modul-Kopien und ein
Terraform auf dem Runner für eine einzige VM am Leben.

**Moodle neu bauen.** Hätte die Übernahme des States erspart, aber die
Kursdaten auf der Instanzplatte mitgenommen.
