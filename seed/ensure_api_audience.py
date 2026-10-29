"""Idempotently configure the API audience on an existing Keycloak client.

Run before enabling backend issuer/audience validation on an existing realm.
Uses KEYCLOAK_ADMIN_USER / KEYCLOAK_ADMIN_PASSWORD from the environment.
"""
import os

from keycloak import KeycloakAdmin


def ensure_mapper(admin, client_name, audience):
    client_id = admin.get_client_id(client_name)
    if not client_id:
        raise RuntimeError(f"Keycloak client {client_name!r} not found")
    mapper = {
        "name": "appstore-backend-audience",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-audience-mapper",
        "consentRequired": False,
        "config": {
            "included.client.audience": audience,
            "access.token.claim": "true",
            "id.token.claim": "false",
        },
    }
    existing = next(
        (item for item in admin.get_mappers_from_client(client_id) if item.get("name") == mapper["name"]),
        None,
    )
    if existing:
        admin.update_client_mapper(client_id, existing["id"], {**mapper, "id": existing["id"]})
    else:
        admin.add_mapper_to_client(client_id, mapper)


def main():
    admin = KeycloakAdmin(
        server_url=os.environ.get("KEYCLOAK_SERVER_URL", "http://keycloak:8080"),
        username=os.environ["KEYCLOAK_ADMIN_USER"],
        password=os.environ["KEYCLOAK_ADMIN_PASSWORD"],
        realm_name=os.environ.get("KEYCLOAK_REALM", "dhbw"),
        user_realm_name="master",
        verify=True,
    )
    ensure_mapper(
        admin,
        os.environ.get("KEYCLOAK_FRONTEND_CLIENT_ID", "appstore-frontend"),
        os.environ.get("KEYCLOAK_TOKEN_AUDIENCE", "appstore-backend"),
    )
    print("API audience configured for the frontend client")


if __name__ == "__main__":
    main()
