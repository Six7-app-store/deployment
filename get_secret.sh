#!/bin/bash

echo "Regenerating appstore-backend client secret..."

# Get admin token
TOKEN=$(curl -s -X POST http://keycloak:8080/realms/master/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=admin-cli&username=admin&password=admin&grant_type=password" | jq -r '.access_token')

echo "✓ Token erhalten"

# Get client ID
CLIENT_ID=$(curl -s -X GET "http://keycloak:8080/admin/realms/dhbw/clients?clientId=appstore-backend" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" | jq -r '.[0].id')

echo "✓ Client-ID: $CLIENT_ID"

# Regenerate secret
NEW_SECRET=$(curl -s -X POST "http://keycloak:8080/admin/realms/dhbw/clients/$CLIENT_ID/client-secret" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" | jq -r '.value')

echo "✓ Neues Secret: $NEW_SECRET"
echo ""
echo "KEYCLOAK_CLIENT_SECRET=$NEW_SECRET"
