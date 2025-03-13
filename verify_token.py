#!/usr/bin/env python3
"""
Verify that a Copernicus Data Space token file is valid and properly formatted.
"""

import json
import sys
import os
from datetime import datetime, timedelta

def verify_token_file(token_file):
    """Verify that a token file is valid and properly formatted."""
    print(f"Verifying token file: {token_file}")
    
    # Check if the file exists
    if not os.path.exists(token_file):
        print(f"Error: Token file does not exist: {token_file}")
        return False
    
    # Check if the file is empty
    if os.path.getsize(token_file) == 0:
        print(f"Error: Token file is empty: {token_file}")
        return False
    
    # Try to parse the JSON
    try:
        with open(token_file, 'r') as f:
            token_data = json.load(f)
        
        # Check for required fields
        required_fields = ['access_token', 'refresh_token', 'expires_in']
        missing_fields = [field for field in required_fields if field not in token_data]
        
        if missing_fields:
            print(f"Error: Token file is missing required fields: {', '.join(missing_fields)}")
            return False
        
        # Check token expiration
        if 'expires_in' in token_data:
            expires_in = token_data['expires_in']
            expiration_time = datetime.now() + timedelta(seconds=expires_in)
            print(f"Access token expires at: {expiration_time}")
        
        # Print token information
        print("Token file is valid and contains the following information:")
        print(f"- Access token: {token_data['access_token'][:20]}... (truncated)")
        print(f"- Refresh token: {token_data['refresh_token'][:20]}... (truncated)")
        print(f"- Token type: {token_data.get('token_type', 'unknown')}")
        print(f"- Expires in: {token_data.get('expires_in', 'unknown')} seconds")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"Error: Token file contains invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"Error: Failed to verify token file: {e}")
        return False

if __name__ == "__main__":
    # Use the provided token file or default to copernicus_dataspace_token.json
    token_file = sys.argv[1] if len(sys.argv) > 1 else "copernicus_dataspace_token.json"
    verify_token_file(token_file) 