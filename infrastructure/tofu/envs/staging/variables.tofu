variable "ssh_public_key" {
  description = "SSH public key for the staging deploy keypair. Supplied by CI via TF_VAR_ssh_public_key (derived from the SSH_PRIVATE_KEY secret)."
  type        = string
}

# DHBW campus ranges allowed to reach SSH.
#
# The defaults are committed on purpose. These are a security control, and a
# reviewer reading security_group.tf needs to be able to tell whether port 22 is
# campus-only or open to the world — a bare var reference hides exactly the fact
# that matters most. Committing them also gives the range a git history, so
# widening it is an auditable change rather than an invisible one.
#
# Both remain overridable per environment via TF_VAR_ssh_source_cidr_ipv4 /
# TF_VAR_ssh_source_cidr_ipv6 without touching this file.
variable "ssh_source_cidr_ipv4" {
  description = "IPv4 range allowed to reach port 22 (DHBW campus)."
  type        = string
  default     = "141.72.0.0/16"

  validation {
    condition     = can(cidrhost(var.ssh_source_cidr_ipv4, 0))
    error_message = "ssh_source_cidr_ipv4 must be a valid IPv4 CIDR, e.g. 141.72.0.0/16."
  }
}

# 2001:7c0:1b20::/48 is the campus allocation (registered to DHBW Mannheim in
# RIPE). The previous value, 2001:7c0:1b20:c913::/64, is the allocation pool of
# the DHBWV6 network itself — the range VMs draw their own addresses from, not
# the range an operator connects in from. With the runner on a laptop, that
# value blocks the Ansible step.
#
# Narrow it back to that /64 in Phase 2, once the runner is a VM in this tenant:
# then only the runner may reach port 22, which is tighter than campus-wide.
variable "ssh_source_cidr_ipv6" {
  description = "IPv6 range allowed to reach port 22 (DHBW campus)."
  type        = string
  default     = "2001:7c0:1b20::/48"

  validation {
    condition     = can(cidrhost(var.ssh_source_cidr_ipv6, 0))
    error_message = "ssh_source_cidr_ipv6 must be a valid IPv6 CIDR, e.g. 2001:7c0:1b20::/48."
  }
}
