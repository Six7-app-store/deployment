"""Check both paths without touching a Keycloak realm."""
from unittest.mock import MagicMock

from ensure_api_audience import ensure_mapper


def test_creates_and_updates_the_same_client_mapper():
    admin = MagicMock()
    admin.get_client_id.return_value = "client-id"
    admin.get_mappers_from_client.return_value = []
    ensure_mapper(admin, "frontend", "appstore-backend")
    admin.add_mapper_to_client.assert_called_once()
    admin.get_mappers_from_client.return_value = [{
        "id": "mapper-id", "name": "appstore-backend-audience",
    }]
    ensure_mapper(admin, "frontend", "appstore-backend")
    admin.update_client_mapper.assert_called_once()
