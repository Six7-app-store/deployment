variable "ssh_public_key" {
  description = "SSH public key fuer den Deploy-Zugang. Aus SSH_PRIVATE_KEY abgeleitet."
  type        = string
}

# Dieselben Campus-Bereiche wie in envs/staging. SSH gehoert nicht ins offene
# Netz; 80 und 443 dagegen schon - siehe security_group.tf.
variable "ssh_source_cidr_ipv4" {
  description = "IPv4-Bereich, der Port 22 erreichen darf."
  type        = string
  default     = "141.72.0.0/16"
}

variable "ssh_source_cidr_ipv6" {
  description = "IPv6-Bereich, der Port 22 erreichen darf."
  type        = string
  default     = "2001:7c0:1b20::/48"
}
