provider "openstack" {
  # Configuration is automatically loaded from environment variables:
  # OS_AUTH_URL, OS_APPLICATION_CREDENTIAL_ID, OS_APPLICATION_CREDENTIAL_SECRET, etc.
  #
  # Unlike envs/staging, this environment is applied from an operator's machine
  # rather than from CI — there is no runner yet when it first runs. Source the
  # same credentials you use for the openstack CLI before applying.
}
