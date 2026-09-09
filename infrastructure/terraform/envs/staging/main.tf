# Module is used to define things in one place
# and achieve DRY
module "vm" {
  source = "../../modules/openstack_vm"

  name       = "staging-dhbw-appstore"
  image      = "Ubuntu 24.04"
  flavor     = "gp1.large"
  public_key = var.ssh_public_key

  # IPv6 works here only because the certificate is obtained over dns-01.
  # The CA cannot reach this host inbound: its own endpoint has no AAAA record,
  # and both inbound challenge types failed against DHBWV6:
  #
  #   http-01      "Could not fetch URL: http://.../.well-known/acme-challenge/..."
  #   tls-alpn-01  "Unable to retrieve server certificate for ..."
  #
  # dns-01 needs no inbound connection at all: Caddy writes a TXT record over
  # RFC 2136 and the CA reads it from DNS. See caddy/Caddyfile.
  #
  # Reachability itself was never the issue - a host outside the DHBW network
  # reached this VM over IPv6 on both 80 and 443.
  network_name = "DHBWV6"
  connect_via  = "fixed_ipv6"

  # Second interface for IPv4 - not currently possible on newstack.dhbw.cloud.
  # Both routes to a public IPv4 address are closed to this project:
  #
  #   - A port on "DHBW" is refused by Neutron with 403 HTTPForbidden,
  #     "Tenant ... not allowed to create port on this network".
  #   - A floating IP can be allocated from "DHBW" (141.72.178.x) but not
  #     associated: "External network ... is not reachable from subnet ...".
  #     The same missing router the old stack had.
  #
  # The stack therefore runs IPv6-only: an AAAA record, no A record. That
  # costs nothing for the certificate - Caddy proves the domain over dns-01,
  # which needs no inbound connection of either family.
  #
  # Re-enable once the project is allowed to create ports on DHBW, or once a
  # router exists between the VM subnet and the external network.
  # secondary_network_name = "DHBW"
  # secondary_subnet_name  = "DHBW-178"

  # Referencing the resource rather than a bare name gives Terraform the
  # dependency, so the group and its rules exist before the instance is built.
  security_groups = ["default", openstack_networking_secgroup_v2.appstore_vm.name]

  # Belongs at 50, the way the Forgejo host has it: the named volumes under
  # /var/lib/docker hold both databases, and a volume also survives a
  # replacement of the instance.
  #
  # Raised back to 50: on newstack.dhbw.cloud Cinder hands out volumes
  # normally - a test volume went from "creating" to "available" in seconds,
  # so the ten-minute timeout that forced the 0 no longer applies. The root
  # disk of gp1.large is 10 GB, of which ~7 GB are free, and the documented
  # failure mode is "no space left on device" during the Caddy build.
  #
  # NOTE: this env sets no user_data, so the module's comment about cloud-init
  # formatting the volume does not apply here. The Ansible playbook does that
  # job instead, but only when docker_data_device is set - it defaults to ""
  # and must be kept in step with this value:
  #
  #     ansible-playbook ... -e docker_data_device=/dev/vdb
  #
  # The playbook creates the filesystem with force: no and mounts it by UUID,
  # so re-running a deploy never reformats the volume.
  docker_data_volume_size_gb = 50

  metadata = {
    env  = "staging"
    role = "docker"
  }
}

output "vm_ip" {
  value = module.vm.vm_ip
}

# The address the A record for APP_HOSTNAME points at.
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
