"""
Token Manager Utility

This module provides functions for managing authentication tokens for the
Copernicus Data Space API.
"""

import os
import json
import getpass
import subprocess
import requests
import sys
import time

# Global constants
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
DEFAULT_TOKEN_FILE = 'copernicus_dataspace_token.json'

def get_token_path(token_file=None):
    """
    Get the path to the token file.
    
    Args:
        token_file (str, optional): Path to the token file. If None, the default path is used.
        
    Returns:
        str: Path to the token file
    """
    if token_file is None:
        # Use the default token file in the project root
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), DEFAULT_TOKEN_FILE)
    return token_file

def load_token(token_file=None):
    """
    Load the token from the token file.
    
    Args:
        token_file (str, optional): Path to the token file. If None, the default path is used.
        
    Returns:
        dict: Token data, or None if the file doesn't exist or is invalid
    """
    token_path = get_token_path(token_file)
    
    try:
        if os.path.exists(token_path):
            with open(token_path, 'r') as f:
                return json.load(f)
        return None
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading token from {token_path}: {e}")
        return None

def save_token(token_data, token_file=None):
    """
    Save the token data to the token file.
    
    Args:
        token_data (dict): Token data to save
        token_file (str, optional): Path to the token file. If None, the default path is used.
        
    Returns:
        bool: True if the token was saved successfully, False otherwise
    """
    token_path = get_token_path(token_file)
    
    try:
        with open(token_path, 'w') as f:
            json.dump(token_data, f)
        return True
    except IOError as e:
        print(f"Error saving token to {token_path}: {e}")
        return False

def get_credentials():
    """
    Get credentials from environment variables or prompt the user.
    
    Returns:
        tuple: (username, password) or (None, None) if the user cancels
    """
    # First try environment variables
    username = os.environ.get('COPERNICUS_USERNAME')
    password = os.environ.get('COPERNICUS_PASSWORD')
    
    # If not in environment variables, prompt the user
    if not username:
        username = input("Enter your Copernicus username: ")
        if not username:
            return None, None
    
    if not password:
        password = getpass.getpass("Enter your Copernicus password: ")
        if not password:
            return None, None
    
    return username, password

def generate_token(token_file=None):
    """
    Generate a new token using credentials from environment variables or user prompt.
    
    Args:
        token_file (str, optional): Path to save the token. If None, the default path is used.
        
    Returns:
        dict: Token data, or None if token generation failed
    """
    username, password = get_credentials()
    
    if not username or not password:
        print("No credentials provided. Token generation canceled.")
        return None
    
    try:
        # Make the token request
        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": "cdse-public",
                "username": username,
                "password": password,
                "grant_type": "password"
            }
        )
        
        # Check if the request was successful
        if response.status_code == 200:
            token_data = response.json()
            token_path = get_token_path(token_file)
            
            # Save the token
            if save_token(token_data, token_file):
                # Display success message
                print(f"Token generated successfully and saved to {token_path}")
                print(f"Token will expire in {token_data.get('expires_in', 'unknown')} seconds")
                return token_data
            else:
                print(f"Failed to save token to {token_path}")
                return token_data  # Still return the token even if saving failed
        else:
            print(f"Failed to generate token: {response.status_code} {response.reason}")
            if response.text:
                print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"Error generating token: {e}")
        return None

def refresh_token(token_data=None, token_file=None):
    """
    Refresh an existing token using the refresh token.
    
    Args:
        token_data (dict, optional): Existing token data. If None, it will be loaded from the token file.
        token_file (str, optional): Path to the token file. If None, the default path is used.
        
    Returns:
        dict: New token data, or None if token refresh failed
    """
    # If no token data was provided, load it from the file
    if token_data is None:
        token_data = load_token(token_file)
        
    if token_data is None or 'refresh_token' not in token_data:
        print("No valid token data with refresh token found.")
        return generate_token(token_file)
    
    try:
        # Make the refresh token request
        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": "cdse-public",
                "refresh_token": token_data['refresh_token'],
                "grant_type": "refresh_token"
            }
        )
        
        # Check if the request was successful
        if response.status_code == 200:
            new_token_data = response.json()
            
            # Save the new token
            if save_token(new_token_data, token_file):
                print("Token refreshed successfully")
                print(f"New token will expire in {new_token_data.get('expires_in', 'unknown')} seconds")
                return new_token_data
            else:
                print("Failed to save refreshed token")
                return new_token_data  # Still return the token even if saving failed
        else:
            print(f"Failed to refresh token: {response.status_code} {response.reason}")
            if response.text:
                print(f"Response: {response.text}")
            
            # If refresh failed, try to generate a new token
            print("Trying to generate a new token...")
            return generate_token(token_file)
    except Exception as e:
        print(f"Error refreshing token: {e}")
        # If refresh failed with an exception, try to generate a new token
        print("Trying to generate a new token...")
        return generate_token(token_file)

def ensure_valid_token(token_file=None):
    """
    Ensure a valid token is available, generating or refreshing if needed.
    Always refreshes the token for each call.
    
    Args:
        token_file (str, optional): Path to the token file. If None, the default path is used.
        
    Returns:
        dict: Token data, or None if no valid token could be obtained
    """
    token_data = load_token(token_file)
    
    # Always refresh the token if it exists, otherwise generate a new one
    if token_data is None:
        print("No token found. Generating a new token...")
        return generate_token(token_file)
    else:
        print("Always refreshing token...")
        return refresh_token(token_data, token_file)

def get_access_token(token_file=None):
    """
    Get a valid access token, always refreshing it.
    
    Args:
        token_file (str, optional): Path to the token file. If None, the default path is used.
        
    Returns:
        str: Access token, or None if no valid token could be obtained
    """
    token_data = ensure_valid_token(token_file)
    
    if token_data and 'access_token' in token_data:
        return token_data['access_token']
    
    return None

def is_token_valid(access_token=None, token_file=None):
    """
    Check if the given access token is valid.
    
    Args:
        access_token (str, optional): The access token to check. If None, it will be loaded from the token file.
        token_file (str, optional): Path to the token file. If None, the default path is used.
        
    Returns:
        bool: True if the token is valid, False otherwise
    """
    if access_token is None:
        token_data = load_token(token_file)
        if token_data and 'access_token' in token_data:
            access_token = token_data['access_token']
        else:
            print("No access token available to check")
            return False
    
    try:
        # Try to get user info with the token
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(
            'https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/userinfo', 
            headers=headers
        )
        
        if response.status_code == 200:
            print("Access token is valid")
            return True
        else:
            print(f"Access token validation failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error checking token validity: {e}")
        return False

if __name__ == "__main__":
    # If run directly, generate or refresh a token
    token_data = ensure_valid_token()
        
    if token_data:
        # Show token details
        print(f"Access token: {token_data.get('access_token', 'unknown')[:20]}... (truncated)")
        print(f"Token expires in: {token_data.get('expires_in', 'unknown')} seconds")
    else:
        print("Failed to obtain a valid token.") 