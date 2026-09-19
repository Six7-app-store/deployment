# Module is used to define things in one place
# and achieve DRY
module "vm" {
  source = "../../modules/openstack_vm"

  name  = "staging-dhbw-appstore"
  image = "Ubuntu 24.04"

  # k8s.node statt gp1.large. Rechenleistung identisch - 4 vCPU, 8 GB RAM -,
  # aber 50 GB Systemplatte statt 10. Die ganze gp1-Familie (ebenso cb1 und
  # mb1) hat nur 10 GB, und genau deshalb hing hier bisher ein Cinder-Volume
  # dran.
  #
  # Der Name kommt daher, dass der Flavor fuer Kubernetes-Knoten gedacht ist.
  # Er steht im Flavor-Katalog dieses Projekts und ist nicht anderweitig
  # gebunden; ob die DHBW eine bevorzugte Verwendung erwartet, ist nicht
  # dokumentiert.
  #
  # Am Kontingent aendert der Wechsel nichts: 4 vCPU und 8 GB bleiben 4 vCPU
  # und 8 GB. Siehe ADR-0004.
  flavor = "k8s.node"

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

  # Kein Cinder-Volume mehr. Die 50 GB kommen jetzt aus dem Flavor, siehe oben.
  #
  # Der Grund ist nicht Geschmack: am 18.09.2026 hat Cinder auf
  # newstack.dhbw.cloud aufgehoert, Volumes fertigzustellen. Zwei blieben ueber
  # Stunden in "creating" haengen, das Kontingent lag dabei bei 4 von 30
  # Volumes und 80 von 256 GB. Der erste automatische Deploy scheiterte daran
  # mit "Error waiting for openstack_blockstorage_volume_v3 ... to become
  # ready: context deadline exceeded" - und zwar erst, nachdem destroy die alte
  # VM bereits abgeraeumt hatte.
  #
  # Ein Volume war hier ohnehin nur noch Gewohnheit. Sein Zweck war, Daten ueber
  # ein Ersetzen der Instanz zu retten; seit ADR-0003 wird der Stack bei jedem
  # Merge komplett neu gebaut. Es rettete also nichts mehr, kostete aber eine
  # Abhaengigkeit von einem Dienst, der ausfallen kann - und genau das tat er.
  #
  # Bleibt 0, solange docker_data_device im Playbook auf "" steht. Die beiden
  # Werte gehoeren zusammen: wer hier wieder ein Volume anlegt, muss dort das
  # Geraet eintragen, sonst liegen die Docker-Daten weiter auf der Systemplatte
  # und das Volume bleibt leer. Siehe ADR-0004.
  docker_data_volume_size_gb = 0

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
