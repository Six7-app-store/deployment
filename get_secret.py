#!/usr/bin/env python3
import urllib.request
import json
import sys

print("Regenerating appstore-backend client secret...")

try:
    # Get admin token
    token_url = "http://keycloak:8080/realms/master/protocol/openid-connect/token"
    token_data = "client_id=admin-cli&username=admin&password=admin&grant_type=password"
    
    req = urllib.request.Request(token_url, data=token_data.encode(), method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    
    with urllib.request.urlopen(req) as response:
        token_json = json.loads(response.read().decode())
        token = token_json['access_token']
    
    print("✓ Token erhalten")
    
    # Get client ID
    client_url = "http://keycloak:8080/admin/realms/dhbw/clients?clientId=appstore-backend"
    req = urllib.request.Request(client_url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    
    with urllib.request.urlopen(req) as response:
        clients = json.loads(response.read().decode())
    
    if not clients:
        print("❌ Client 'appstore-backend' nicht gefunden!")
        sys.exit(1)
    
    client_id = clients[0]['id']
    print(f"✓ Client-ID: {client_id}")
    
    # Regenerate secret
    secret_url = f"http://keycloak:8080/admin/realms/dhbw/clients/{client_id}/client-secret"
    req = urllib.request.Request(secret_url, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    
    with urllib.request.urlopen(req) as response:
        secret_json = json.loads(response.read().decode())
    
    new_secret = secret_json['value']
    
    print(f"✓ Neues Secret: {new_secret}")
    print()
    print(f"KEYCLOAK_CLIENT_SECRET={new_secret}")
    
except Exception as e:
    print(f"❌ Error: {e}", file=sys.stderr)
    sys.exit(1)
