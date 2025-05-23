#!/usr/bin/env python3
"""
Download Sentinel-2 tiles from a JSON file generated by sentinel_city_explorer.

This is a simple wrapper script that uses the existing sentinel_tile_downloader.py functionality.
It downloads all tiles found in the JSON file with no limitations, using a hierarchical structure
with year and tile ID.
"""

import os
import sys
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Add the project root directory to the Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from src.sentinel_tile_downloader import SentinelDownloader
from src.token_manager import get_access_token, ensure_valid_token

def main():
    parser = argparse.ArgumentParser(description="Download Sentinel-2 tiles from a JSON file")
    parser.add_argument("--json-file", type=str, required=True,
                        help="Path to the JSON file containing tile information")
    parser.add_argument("--output-dir", type=str, default="downloads",
                        help="Directory to save downloaded files (default: downloads)")
    
    args = parser.parse_args()
    
    # Check if the JSON file exists
    if not os.path.exists(args.json_file):
        logging.error(f"Error: JSON file not found: {args.json_file}")
        sys.exit(1)
    
    # Always refresh the token before starting
    logging.info("Refreshing token before starting")
    refreshed = get_access_token()
    if refreshed:
        logging.info("Token refreshed successfully")
    else:
        logging.warning("Failed to refresh token, will try to generate a new one")
        # Try to generate a new token
        token_data = ensure_valid_token()
        if token_data:
            logging.info("New token generated successfully")
        else:
            logging.warning("Failed to generate a new token")
            sys.exit(1)
    
    # Create the downloader and download tiles
    try:
        downloader = SentinelDownloader()
        logging.info(f"Downloading all tiles from {args.json_file} without any limitations (using hierarchical structure)")
        downloader.download_tiles_from_json(
            args.json_file,
            output_dir=args.output_dir
        )
    except FileNotFoundError as e:
        logging.error(f"Error: {e}")
        sys.exit(1)
    except PermissionError as e:
        logging.error(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 