terraform {
  required_version = ">= 1.5.0"

  # Der State liegt als Datei auf dem Runner, unter einem absoluten Pfad
  # ausserhalb des Workspace.
  #
  # Vorher lag er in Postgres. Das war richtig, solange der Deploy in einem
  # Job-Container lief, der nach jedem Lauf verschwand — eine Datei im Workspace
  # haette den Lauf nicht ueberlebt. Mit dem self-hosted Runner auf einer
  # dauerhaften VM gilt das nicht mehr, und Postgres wird zum Problem statt zur
  # Loesung: die State-Datenbank lief als Container `postgres-tfstate` im
  # Staging-Stack selbst. Seit dieser Workflow den Stack bei jedem Merge
  # abreisst, wuerde `terraform destroy` die Datenbank mitloeschen, in der steht,
  # was gerade geloescht wird. Der naechste Lauf startete mit leerem State,
  # saehe die verwaisten OpenStack-Ressourcen nicht und scheiterte beim Anlegen
  # am schon vergebenen Namen.
  #
  # /var/lib/tf-state/ liegt auf der Runner-VM (`github-runner`). Die ist eine
  # andere Maschine als die AppStore-VM und wird von diesem Terraform nicht
  # verwaltet — sie ueberlebt jedes destroy. actions/checkout raeumt nur den
  # Workspace, dieser Pfad bleibt unberuehrt.
  #
  # Der local-Backend kennt kein verteiltes Locking. Das ersetzt die
  # concurrency-Gruppe `staging-deploy` im Workflow: GitHub laesst immer nur
  # einen Deploy-Job gleichzeitig laufen, und es gibt genau einen Runner.
  backend "local" {
    path = "/var/lib/tf-state/staging/terraform.tfstate"
  }

  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 3.4"
    }
  }
}
