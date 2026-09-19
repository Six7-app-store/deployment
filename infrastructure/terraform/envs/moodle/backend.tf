terraform {
  required_version = ">= 1.5.0"

  # Wie bei envs/staging: der State liegt auf der Runner-VM, also auf einer
  # Maschine, die dieses Terraform nicht verwaltet. Die Begruendung steht in
  # ADR-0003 und gilt hier unveraendert.
  #
  # Anders als Staging wird diese VM allerdings NICHT bei jedem Merge
  # abgerissen - siehe main.tf. Der State ist trotzdem ausgelagert, damit ein
  # Neuaufbau der Staging-VM ihn nicht mitnimmt.
  backend "local" {
    path = "/var/lib/tf-state/moodle/terraform.tfstate"
  }

  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 3.4"
    }
  }
}
