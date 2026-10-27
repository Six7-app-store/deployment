variable "name" {
  type = string
}

variable "allowed_egress" {
  description = "Explicit destination CIDRs and TCP/UDP ports. No rules means no egress."
  type = map(object({
    ethertype = string
    protocol  = string
    port      = number
    cidr      = string
  }))
  default = {}

  validation {
    condition = alltrue([
      for rule in values(var.allowed_egress) :
      contains(["IPv4", "IPv6"], rule.ethertype) &&
      contains(["tcp", "udp"], rule.protocol) &&
      rule.port >= 1 && rule.port <= 65535 && rule.port == floor(rule.port) &&
      can(cidrhost(rule.cidr, 0)) &&
      !can(regex("/0+$", rule.cidr)) &&
      ((rule.ethertype == "IPv6") == can(regex(":", rule.cidr)))
    ])
    error_message = "Use a specific IPv4/IPv6 CIDR, TCP/UDP protocol, and a single port from 1 through 65535."
  }
}
