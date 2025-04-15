"""
Token Manager Utility

This module provides functions for managing authentication tokens for the
Copernicus Data Space API.
"""

import os
import json
import getpass
import logging as log
import requests

# Global constants
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
DEFAULT_TOKEN_FILE = 'copernicus_dataspace_token.json'

def get_token_patprinth(token_file=None):
    """Get the path to the token file."""
    if token_file is None:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), DEFAULT_TOKEN_FILE)
    return token_file

def load_token(token_file=None):
    """Load the token from the token file."""
    token_path = get_token_path(token_file)
    try:
        if os.path.exists(token_path):
            with open(token_path, 'r') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        log.error(f"Error loading token from {token_path}: {e}")
    return None

def save_token(token_data, token_file=None):
    """Save the token data to the token file."""
    token_path = get_token_path(token_file)
    try:
        with open(token_path, 'w') as f:
            json.dump(token_data, f)
        return True
    except IOError as e:
        log.error(f"Error saving token to {token_path}: {e}")
        return False

def get_credentials():
    """Get credentials from environment variables or prompt the user."""
    username = os.environ.get('COPERNICUS_USERNAME')
    password = os.environ.get('COPERNICUS_PASSWORD')
    
    if not username:
        username = input("Enter your Copernicus username: ")
    if not password:
        password = getpass.getpass("Enter your Copernicus password: ")
    
    return username, password

def generate_token(token_file=None):
    """Generate a new token using credentials."""
    username, password = get_credentials()
    if not username or not password:
        log.warning("No credentials provided. Token generation canceled.")
        return None
    
    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": "cdse-public",
                "username": username,
                "password": password,
                "grant_type": "password"
            }
        )
        
        if response.status_code == 200:
            token_data = response.json()
            if save_token(token_data, token_file):
                log.info(f"Token generated successfully and saved to {get_token_path(token_file)}")
                log.warning(f"Token will expire in {token_data.get('expires_in', 'unknown')} seconds")
            return token_data
        else:
            log.error(f"Failed to generate token: {response.status_code} {response.reason}")
            if response.text:
                log.error(f"Response: {response.text}")
    except Exception as e:
        log.error(f"Error generating token: {e}")
    return None

def refresh_token(token_data=None, token_file=None):
    """Refresh an existing token using the refresh token."""
    if token_data is None:
        token_data = load_token(token_file)
        
    if not token_data or 'refresh_token' not in token_data:
        return generate_token(token_file)
    
    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": "cdse-public",
                "refresh_token": token_data['refresh_token'],
                "grant_type": "refresh_token"
            }
        )
        
        if response.status_code == 200:
            new_token_data = response.json()
            if save_token(new_token_data, token_file):
                log.info("Token refreshed successfully")
                log.warning(f"New token will expire in {new_token_data.get('expires_in', 'unknown')} seconds")
            return new_token_data
        else:
            log.warning(f"Failed to refresh token: {response.status_code} {response.reason}")
            return generate_token(token_file)
    except Exception as e:
        log.error(f"Error refreshing token: {e}")
        return generate_token(token_file)

def ensure_valid_token(token_file=None):
    """Ensure a valid token is available, generating or refreshing if needed."""
    token_data = load_token(token_file)
    if token_data is None:
        log.warning("No token found. Generating a new token...")
        return generate_token(token_file)
    else:
        log.warning("Refreshing token...")
        return refresh_token(token_data, token_file)

def get_access_token(token_file=None):
    """Get a valid access token."""
    token_data = ensure_valid_token(token_file)
    return token_data.get('access_token') if token_data else None 