terraform {
  required_version = ">= 1.5.0"

  # State lives in Postgres, not on a runner's disk. The previous local backend
  # wrote to an absolute path that only survived because the runner's workspace
  # persisted; a job container is destroyed after every run, so the state — and
  # with it the ability to manage the VM — was lost each time.
  #
  # The connection string comes from PG_CONN_STR in the environment rather than
  # -backend-config, which keeps the password out of git. Same approach as
  # worker/app/services/terraform_executor.py.
  #
  # The pg backend also takes a Postgres advisory lock per operation, so two
  # concurrent runs cannot corrupt the state.
  backend "pg" {
    schema_name = "staging"
  }

  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 3.4"
    }
  }
}