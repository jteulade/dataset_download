#!/bin/bash

# Replace these with your actual credentials
USERNAME="jules.teulade@gmail.com"
PASSWORD="w7B6XXM:K1'Zb4*G"

# Make the token request and save the complete response
curl -s -d "client_id=cdse-public" \
     -d "username=$USERNAME" \
     -d "password=$PASSWORD" \
     -d "grant_type=password" \
     "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token" > copernicus_dataspace_token.json

# Check if the token was retrieved successfully
if grep -q "access_token" copernicus_dataspace_token.json; then
    echo "Token retrieved successfully and saved to copernicus_dataspace_token.json"
    
    # Extract and display the access token for convenience
    ACCESS_TOKEN=$(cat copernicus_dataspace_token.json | python3 -m json.tool | grep "access_token" | awk -F\" '{print $4}')
    echo "Access token: ${ACCESS_TOKEN:0:20}... (truncated)"
    
    # Display token expiration information
    EXPIRES_IN=$(cat copernicus_dataspace_token.json | python3 -m json.tool | grep "expires_in" | awk '{print $2}' | tr -d ',')
    echo "Token expires in: $EXPIRES_IN seconds ($(echo "$EXPIRES_IN/60" | bc) minutes)"
else
    echo "Failed to retrieve token. Check your credentials and try again."
    cat copernicus_dataspace_token.json
fi 