# Caddy with the RFC 2136 DNS provider compiled in, for the Forgejo host.
#
# Deliberately a copy of ../../caddy/Dockerfile rather than a shared build
# context. infrastructure/ansible/forgejo.yml synchronises only the forgejo/
# directory to the VM, so a context pointing outside it would not exist there.
# Four lines of duplication cost less than coupling the two stacks, and it lets
# each host move to a new Caddy version on its own schedule. Keep the two in
# sync when upgrading — the reasoning below applies to both.
#
# The stock image ships no DNS provider modules, and without one only the
# inbound challenge types are available. Those cannot work on this host: its
# security group restricts 80 and 443 to the campus range, so the CA can reach
# neither.
#
# dns-01 inverts the direction. Caddy writes a TXT record under
# _acme-challenge.<host> over RFC 2136, authenticated with the zone's TSIG key,
# and the CA reads it from DNS. Nothing has to reach us inbound.
#
# Versions are pinned rather than floating. caddy:2-* is any 2.x, and the
# plugin without a version resolves to whatever is newest at build time, so two
# builds weeks apart produce different images without a line changing here.
#
# That costs more than reproducibility. The deploy rebuilds on the VM, and a
# rebuild whose output differs moves the tag to a new image while the running
# container still points at the old one - which then gets collected. Compose
# can no longer resolve the container's image and aborts before it can replace
# it, so the container stays stranded and every later run fails the same way.
# It happened once on the staging host.
FROM caddy:2.11.4-builder AS builder

RUN xcaddy build v2.11.4 --with github.com/caddy-dns/rfc2136@v1.0.0

FROM caddy:2.11.4-alpine

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
