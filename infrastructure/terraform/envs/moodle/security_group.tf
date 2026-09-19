# Moodle muss aus zwei Richtungen erreichbar sein, und das unterscheidet diese
# Gruppe von der des App Stores:
#
#   - Studierende und Lehrende rufen es im Browser auf
#   - Der App Store holt sich Moodles JWKS und Token bei jedem LTI-Launch
#
# Beides laeuft ueber 443. Eine Einschraenkung auf das Campusnetz wuerde LTI
# brechen, sobald jemand von aussen auf Moodle zugreift.
resource "openstack_networking_secgroup_v2" "moodle" {
  name        = "moodle-vm"
  description = "Moodle: HTTP/HTTPS offen, SSH nur aus dem Campusnetz"
}

resource "openstack_networking_secgroup_rule_v2" "http_v6" {
  direction         = "ingress"
  ethertype         = "IPv6"
  protocol          = "tcp"
  port_range_min    = 80
  port_range_max    = 80
  remote_ip_prefix  = "::/0"
  security_group_id = openstack_networking_secgroup_v2.moodle.id
}

resource "openstack_networking_secgroup_rule_v2" "https_v6" {
  direction         = "ingress"
  ethertype         = "IPv6"
  protocol          = "tcp"
  port_range_min    = 443
  port_range_max    = 443
  remote_ip_prefix  = "::/0"
  security_group_id = openstack_networking_secgroup_v2.moodle.id
}

# SSH bleibt auf dem Campus. Der Deploy laeuft vom Runner aus, und der steht
# im Projektnetz innerhalb dieses Bereichs.
resource "openstack_networking_secgroup_rule_v2" "ssh_v6" {
  direction         = "ingress"
  ethertype         = "IPv6"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = var.ssh_source_cidr_ipv6
  security_group_id = openstack_networking_secgroup_v2.moodle.id
}

resource "openstack_networking_secgroup_rule_v2" "icmpv6" {
  direction         = "ingress"
  ethertype         = "IPv6"
  protocol          = "ipv6-icmp"
  remote_ip_prefix  = var.ssh_source_cidr_ipv6
  security_group_id = openstack_networking_secgroup_v2.moodle.id
}
