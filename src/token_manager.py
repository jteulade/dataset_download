"""
Token Manager Utility

This module provides functions for managing authentication tokens for the
Copernicus Data Space API.
"""

import os
import json
import getpass
import logging
import requests

# Global constants
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
DEFAULT_TOKEN_FILE = 'copernicus_dataspace_token.json'

def get_token_path(token_file=None):
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
    except FileNotFoundError:
        logging.error(f"Token file not found: {token_path}")
    except PermissionError:
        logging.error(f"Permission denied to read token file: {token_path}")
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error loading token from {token_path}: {e}")
    return None

def save_token(token_data, token_file=None):
    """Save the token data to the token file."""
    token_path = get_token_path(token_file)
    try:
        with open(token_path, 'w') as f:
            json.dump(token_data, f)
        return True
    except IOError as e:
        logging.error(f"Error saving token to {token_path}: {e}")
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
        logging.warning("No credentials provided. Token generation canceled.")
        return None
    
    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": "cdse-public",
                "username": username,
                "password": password,
                "grant_type": "password"
            },
            timeout=10  # Setting a timeout of 10 seconds to avoid the request hanging indefinitely
        )
        response.raise_for_status()

        if response.headers.get('Content-Type') != 'application/json':
            logging.error(f"Unexpected content type: {response.headers.get('Content-Type')}")
            return None  
        token_data = response.json()

        # Save the token data to the specified file
        if save_token(token_data, token_file):
            logging.info(f"Token generated successfully and saved to {get_token_path(token_file)}")
            logging.warning(f"Token will expire in {token_data.get('expires_in', 'unknown')} seconds")
        return token_data
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error: {e}")
    except Exception as e:
        logging.error(f"Error generating token: {e}")
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
        response.raise_for_status()
        if response.headers.get('Content-Type') != 'application/json':
            logging.error(f"Unexpected content type: {response.headers.get('Content-Type')}")
            return None
        new_token_data = response.json()
        if save_token(new_token_data, token_file):
            logging.info("Token refreshed successfully")
            logging.warning(f"New token will expire in {new_token_data.get('expires_in', 'unknown')} seconds")
        return new_token_data
    
    # Handle specific exceptions
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error: {e}")
        return generate_token(token_file)
    except requests.exceptions.Timeout as e:
        logging.error(f"Request timed out: {e}")
        return generate_token(token_file)
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error: {e}")
        return generate_token(token_file)
    except Exception as e:
        logging.error(f"Error refreshing token: {e}")
        return generate_token(token_file)

def ensure_valid_token(token_file=None):
    """Ensure a valid token is available, generating or refreshing if needed."""
    token_data = load_token(token_file)
    if token_data is None:
        logging.warning("No token found. Generating a new token...")
        return generate_token(token_file)
    else:
        logging.warning("Refreshing token...")
        return refresh_token(token_data, token_file)

def get_access_token(token_file=None):
    """Get a valid access token."""
    token_data = ensure_valid_token(token_file)
    return token_data.get('access_token') if token_data else None 