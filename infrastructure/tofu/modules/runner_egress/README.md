# Egress-Sicherheitsgruppe für einen isolierten Runner

Das Modul erstellt eine OpenStack-Sicherheitsgruppe ohne die automatisch
angelegten Egress-Regeln und erlaubt ausschließlich die in `allowed_egress`
explizit angegebenen CIDRs und TCP-/UDP-Ports. Eine leere Liste sperrt den
ausgehenden Verkehr. Der Test verwendet den gemockten Provider und baut keine
Cloud-Ressourcen.

Das Modul ist **noch an keine VM angeschlossen**. Es schützt den vorhandenen
Worker nicht. Beim späteren Anschluss muss es die einzige Sicherheitsgruppe
jedes Runner-Ports sein: OpenStack addiert die Regeln mehrerer Gruppen; eine
zusätzliche `default`-Gruppe kann die Einschränkung aushebeln. IPv4 und IPv6,
DNS, Keystone und Service-Katalog, Git/Provider-Mirror, State und einen engen
Runner-Kontrollkanal müssen passend zur echten Zielumgebung geplant und mit
realen Verbindungstests überprüft werden. Auch Zugriff auf den Metadatenserver
muss bewusst entschieden werden. CIDR-Regeln allein kontrollieren keine
DNS-Namen oder Weiterleitungen innerhalb erlaubter Dienste.

Das Modul erstellt weder die Runner-VM noch die sichere Übergabe der Credentials
und isoliert keine Tasks voneinander. Dafür sind ein Runner-Konzept und ein
verbindlicher Lebenszyklus notwendig, bevor es ausgerollt werden darf.
Lehrkräfte dürfen eigene Templates einreichen; diese sind deshalb als
nicht vertrauenswürdiger Code zu behandeln. Die Zugriffe auf State und Secrets
müssen zusätzlich je Deployment beschränkt werden. Eine gemeinsame
Postgres-Rolle mit Zugriff auf alle Schemas würde die Isolation unterlaufen.
