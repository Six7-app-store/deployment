terraform {
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 3.4"
    }
  }
}

# Attach this group alone to each isolated execution VM's port. Security
# groups are additive, so an additional allow-all group defeats the policy.
resource "openstack_networking_secgroup_v2" "runner" {
  name                 = var.name
  description          = "Explicit egress for isolated deployment execution"
  delete_default_rules = true
}

resource "openstack_networking_secgroup_rule_v2" "egress" {
  for_each          = var.allowed_egress
  security_group_id = openstack_networking_secgroup_v2.runner.id
  direction         = "egress"
  ethertype         = each.value.ethertype
  protocol          = each.value.protocol
  port_range_min    = each.value.port
  port_range_max    = each.value.port
  remote_ip_prefix  = each.value.cidr
}
