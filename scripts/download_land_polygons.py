#!/usr/bin/env python3
"""
Download Natural Earth land polygons for use in the Sentinel City Explorer.

This script downloads the Natural Earth land polygons at 1:110m scale and saves them
to the data directory for use by the sentinel_query module.
"""
import logging
import os
import sys
import requests
import zipfile
import io
import argparse
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add the project root directory to the Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

def download_natural_earth_land(output_dir):
    """
    Download Natural Earth land polygons at 1:110m scale.
    
    Parameters:
        output_dir (str): Directory to save the downloaded polygons
   
    Returns:
        bool: True if download was successful, False otherwise
    """
    os.makedirs(output_dir, exist_ok=True)
    
    logging.info(f"Will download land polygon data to: {output_dir}")
    
    # URL for Natural Earth land polygons at 1:110m scale
    # Fixed URL to use the correct format
    url = "https://naciscdn.org/naturalearth/110m/physical/ne_110m_land.zip"
    
    logging.info(f"Downloading Natural Earth land polygons from {url}")
    
    try:
        # Download the zip file with a proper user agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        # Check if the request was successful
        response.raise_for_status()
        
        # Extract the zip file
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            z.extractall(output_dir)
        
        # Check if the shapefile exists
        shapefile = os.path.join(output_dir, 'ne_110m_land.shp')
        if os.path.exists(shapefile):
            logging.info(f"Successfully downloaded and extracted land polygons to {shapefile}")
            return True
        else:
            logging.error(f"Error: Shapefile not found after extraction")
            return False
        
    except zipfile.BadZipFile:
        logging.error("Erreur : Le fichier téléchargé n'est pas une archive ZIP valide.")        
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Erreur pendant le téléchargement: {e}")
    except Exception as e:
        logging.error(f"Error downloading land polygons: {e}")
        return False


def parse_arguments():
    """
    Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Download Natural Earth land polygons.")
    parser.add_argument("--output-dir", type=str, default="data",
                        help="Directory to save the downloaded polygons")
    return parser.parse_args()   

if __name__ == "__main__":
    args = parse_arguments()
    logging.info("Downloading Natural Earth land polygons for Sentinel City Explorer")
    success = download_natural_earth_land(args.output_dir)
    if success:
        logging.info("Land polygon data is now available for the Sentinel City Explorer")
    else:
        logging.error("Failed to download land polygon data")
        sys.exit(1)