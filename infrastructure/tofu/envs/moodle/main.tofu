# Moodle laeuft als feste Infrastruktur neben dem App Store - nicht als App
# im App Store.
#
# Der Unterschied ist wesentlich: Eine App wird je Kurs ausgerollt und wieder
# verworfen. Moodle dagegen ist die Gegenstelle der LTI-Anbindung. Seine
# Adresse steht als LTI_PLATFORM_ISSUER in der Konfiguration des App Stores
# und ist der Schluessel, unter dem jeder Launch nachgeschlagen wird. Aendert
# sie sich, bricht die Anbindung.
#
# Deshalb auch KEIN destroy bei jedem Merge, anders als bei envs/staging
# (ADR-0003). Diese VM bleibt stehen; der Deploy aktualisiert sie nur.
module "vm" {
  source = "../../modules/openstack_vm"

  name       = "moodle"
  image      = "Ubuntu 24.04"
  public_key = var.ssh_public_key

  # k8s.node aus demselben Grund wie in envs/staging seit ADR-0004: 4 vCPU,
  # 8 GB RAM und 50 GB Systemplatte, ohne ein Cinder-Volume zu brauchen.
  # Moodle mit Postgres und Moodledata braucht deutlich mehr als die 10 GB
  # der gp1-Familie.
  flavor = "k8s.node"

  network_name = "DHBWV6"
  connect_via  = "fixed_ipv6"

  security_groups = ["default", openstack_networking_secgroup_v2.moodle.name]

  # Kein Volume - dieselbe Ueberlegung wie ADR-0004. Anders als bei Staging
  # ist das hier allerdings ein echtes Risiko: Moodles Kursdaten liegen dann
  # auf der Instanzplatte. Solange die VM nicht abgerissen wird, ist das in
  # Ordnung; fuer den Dauerbetrieb gehoert eine Sicherung dazu.
  docker_data_volume_size_gb = 0

  metadata = {
    env  = "moodle"
    role = "lti-platform"
  }
}

output "vm_ip" {
  value       = module.vm.vm_ip
  description = "IPv6-Adresse der Moodle-VM. Gehoert als AAAA-Eintrag unter den Hostnamen."
}
