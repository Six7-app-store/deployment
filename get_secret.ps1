# Get the appstore-backend client secret from Keycloak
Write-Host "Getting admin token from Keycloak..."

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8080/realms/master/protocol/openid-connect/token" `
        -Method POST `
        -Headers @{"Content-Type"="application/x-www-form-urlencoded"} `
        -Body "client_id=admin-cli&username=admin&password=admin&grant_type=password" `
        -ErrorAction Stop

    $json = $response.Content | ConvertFrom-Json
    $token = $json.access_token
    
    Write-Host "✓ Token erhalten"
    
    # Get the client ID for appstore-backend in dhbw realm
    Write-Host "Looking up appstore-backend client..."
    
    $clientResponse = Invoke-WebRequest -Uri "http://localhost:8080/admin/realms/dhbw/clients?clientId=appstore-backend" `
        -Method GET `
        -Headers @{"Authorization"="Bearer $token"; "Content-Type"="application/json"} `
        -ErrorAction Stop
    
    $clients = $clientResponse.Content | ConvertFrom-Json
    
    if ($clients.Count -eq 0) {
        Write-Host "❌ Client 'appstore-backend' nicht gefunden!"
        exit 1
    }
    
    $clientId = $clients[0].id
    Write-Host "✓ Client-ID: $clientId"
    
    # Regenerate the secret
    Write-Host "Regeneriere Client-Secret..."
    
    $secretResponse = Invoke-WebRequest -Uri "http://localhost:8080/admin/realms/dhbw/clients/$clientId/client-secret" `
        -Method POST `
        -Headers @{"Authorization"="Bearer $token"; "Content-Type"="application/json"} `
        -ErrorAction Stop
    
    $secretJson = $secretResponse.Content | ConvertFrom-Json
    $newSecret = $secretJson.value
    
    Write-Host "✓ Neues Secret: $newSecret"
    Write-Host ""
    Write-Host "Bitte in .env eintragen:"
    Write-Host "KEYCLOAK_CLIENT_SECRET=$newSecret"
    
} catch {
    Write-Host "❌ Error: $_"
    exit 1
}
