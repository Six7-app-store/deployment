# Caddy with the RFC 2136 DNS provider compiled in.
#
# The stock image ships no DNS provider modules, and without one only the
# inbound challenge types are available - which cannot work here. The CA's
# endpoint has no AAAA record, so it cannot reach an IPv6-only host: both
# http-01 and tls-alpn-01 failed against this VM with "Connection error" and
# "Unable to retrieve server certificate".
#
# dns-01 inverts the direction. Caddy writes a TXT record under
# _acme-challenge.<host> over RFC 2136, authenticated with the zone's TSIG key,
# and the CA reads it from DNS. Nothing has to reach us inbound.
#
# Building here rather than pulling a prebuilt image keeps this to one file.
# xcaddy fetches Go modules on the first build and caches afterwards.
#
# On a Caddy upgrade this has to be rebuilt, and the module has to support the
# new version - the one real cost of compiling a plugin in.
# Versions are pinned rather than floating. caddy:2-* is any 2.x, and the
# plugin without a version resolves to whatever is newest at build time, so two
# builds weeks apart produce different images without a line changing here.
#
# That costs more than reproducibility. The deploy rebuilds on the VM, and a
# rebuild whose output differs moves the tag to a new image while the running
# container still points at the old one - which then gets collected. Compose
# can no longer resolve the container's image and aborts before it can replace
# it, so the container stays stranded and every later run fails the same way.
# It happened once here.
FROM caddy:2.11.4-builder AS builder

RUN xcaddy build v2.11.4 --with github.com/caddy-dns/rfc2136@v1.0.0

FROM caddy:2.11.4-alpine

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
