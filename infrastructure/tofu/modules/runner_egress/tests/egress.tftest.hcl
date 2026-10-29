mock_provider "openstack" {}

run "no_default_egress" {
  command = plan
  variables { name = "isolated-test" }
  assert {
    condition     = openstack_networking_secgroup_v2.runner.delete_default_rules && length(openstack_networking_secgroup_rule_v2.egress) == 0
    error_message = "The execution VM must not get default allow-all egress."
  }
}

run "explicit_destination" {
  command = plan
  variables {
    name = "isolated-test"
    allowed_egress = {
      keystone = { ethertype = "IPv4", protocol = "tcp", port = 5000, cidr = "192.0.2.10/32" }
    }
  }
  assert {
    condition     = openstack_networking_secgroup_rule_v2.egress["keystone"].remote_ip_prefix == "192.0.2.10/32"
    error_message = "Only the configured destination should be allowed."
  }
}

run "reject_all_internet" {
  command = plan
  variables {
    name = "isolated-test"
    allowed_egress = {
      all = { ethertype = "IPv4", protocol = "tcp", port = 443, cidr = "0.0.0.0/0" }
    }
  }
  expect_failures = [var.allowed_egress]
}

run "reject_ipv6_all_internet" {
  command = plan
  variables {
    name = "isolated-test"
    allowed_egress = {
      all = { ethertype = "IPv6", protocol = "tcp", port = 443, cidr = "::/0" }
    }
  }
  expect_failures = [var.allowed_egress]
}

run "reject_mismatched_address_family" {
  command = plan
  variables {
    name = "isolated-test"
    allowed_egress = {
      wrong_family = { ethertype = "IPv4", protocol = "tcp", port = 5000, cidr = "2001:db8::1/128" }
    }
  }
  expect_failures = [var.allowed_egress]
}
