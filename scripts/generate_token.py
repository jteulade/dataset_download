#!/usr/bin/env python3
"""
Script to generate a new token for the Copernicus Data Space API.
"""

import sys
from pathlib import Path

# Add the project root directory to the Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from src.token_manager import generate_token

def main():
    print("Generating new token...")
    token_data = generate_token()
    if token_data:
        print("Token generated successfully!")
    else:
        print("Failed to generate token.")
        sys.exit(1)

if __name__ == "__main__":
    main() 