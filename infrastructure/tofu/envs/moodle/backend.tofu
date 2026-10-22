terraform {
  required_version = ">= 1.13.0"

  # Wie bei envs/staging: der State liegt als Datei auf der Runner-VM, also auf
  # einer Maschine, die dieses OpenTofu nicht verwaltet. Die Begruendung steht
  # in ADR-0003 und gilt hier unveraendert.
  #
  # Anders als Staging wird diese VM allerdings NICHT bei jedem Merge
  # abgerissen - siehe main.tofu. Der State ist trotzdem ausgelagert, damit ein
  # Neuaufbau der Staging-VM ihn nicht mitnimmt.
  backend "local" {
    # Eigenes Verzeichnis statt /var/lib/tf-state/: der alte Terraform-State
    # (ADR 0010) bleibt als Sicherung liegen und wird nie von OpenTofu
    # ueberschrieben. Die Uebernahme steht in docs/moodle-infrastruktur.md.
    path = "/var/lib/tofu-state/moodle/terraform.tfstate"
  }

  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 3.4"
    }
  }
}
