# The Forgejo host: the forge itself, its Postgres, and the Actions runner.
#
# This is bootstrap infrastructure — see backend.tf for why its state is local
# while every other environment's lives in the database this host runs.

module "vm" {
  source = "../../modules/openstack_vm"

  name       = "ci-dhbw-appstore"
  image      = "Ubuntu 22.04"
  public_key = var.ssh_public_key

  # Smaller than staging's gp1.large. This host runs Forgejo, one Postgres and
  # a single job container at a time (runner/config.yml pins capacity to 1
  # because the Terraform state has no locking across concurrent runs).
  flavor = "gp1.medium"

  # See the NETWORK note in variables.tf. Both are variables rather than
  # literals so the address family is a per-tenant choice.
  network_name     = var.network_name
  connect_via      = var.connect_via
  floating_ip_pool = var.floating_ip_pool

  # Second interface so the forge is reachable without IPv6.
  secondary_network_name = var.secondary_network_name
  secondary_subnet_name  = var.secondary_subnet_name

  # Referencing the resource rather than a bare name gives Terraform the
  # dependency, so the group and its rules exist before the instance is built.
  security_groups = ["default", openstack_networking_secgroup_v2.forgejo_vm.name]

  docker_data_volume_size_gb = var.docker_data_volume_size_gb

  metadata = {
    env  = "forgejo"
    role = "forge"
  }
}

# The Cinder volume is created and attached here, but formatting and mounting
# it at /var/lib/docker is left to Ansible rather than cloud-init.
#
# The module attaches the volume as a separate resource, after the instance
# reports ACTIVE — which is also when cloud-init is already running. Whether
# /dev/vdb exists by the time cloud-init's disk stage runs is a race, and when
# it loses, the setup fails silently: the volume is attached but unused, and
# the symptom only appears later as a full root disk. Ansible runs strictly
# after `terraform apply` returns, so the device is guaranteed to be there.
#
# modules/openstack_vm/variables.tf still describes user_data as the place for
# this. That is accurate for envs that pass their own cloud-init; it is not the
# approach taken here.

output "vm_ip" {
  description = "Address Ansible connects to, selected by connect_via."
  value       = module.vm.vm_ip
}

output "vm_name" {
  value = module.vm.vm_name
}

# The address the A record for the forge's hostname points at.
output "vm_ipv4" {
  value = module.vm.secondary_ipv4
}

# Consumed by the Ansible step that writes the netplan config.
output "vm_ipv4_gateway" {
  value = module.vm.secondary_gateway_ipv4
}

output "vm_ipv4_mac" {
  value = module.vm.secondary_mac
}

output "docker_data_volume_gb" {
  description = "0 when no separate volume was created."
  value       = var.docker_data_volume_size_gb
}