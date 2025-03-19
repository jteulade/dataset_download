#!/usr/bin/env python3
"""
Download Natural Earth land polygons for use in the Sentinel City Explorer.

This script downloads the Natural Earth land polygons at 1:110m scale and saves them
to the data directory for use by the sentinel_query module.
"""

import os
import sys
import requests
import zipfile
import io
import shutil

def download_natural_earth_land():
    """
    Download Natural Earth land polygons at 1:110m scale.
    
    Returns:
        bool: True if download was successful, False otherwise
    """
    # Get project root directory (parent of src)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    # Use a common data directory in the project root
    data_dir = os.path.join(project_root, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    print(f"Will download land polygon data to: {data_dir}")
    
    # URL for Natural Earth land polygons at 1:110m scale
    # Fixed URL to use the correct format
    url = "https://naciscdn.org/naturalearth/110m/physical/ne_110m_land.zip"
    
    print(f"Downloading Natural Earth land polygons from {url}")
    
    try:
        # Download the zip file with a proper user agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Extract the zip file
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            z.extractall(data_dir)
        
        # Check if the shapefile exists
        shapefile = os.path.join(data_dir, 'ne_110m_land.shp')
        if os.path.exists(shapefile):
            print(f"Successfully downloaded and extracted land polygons to {shapefile}")
            return True
        else:
            print(f"Error: Shapefile not found after extraction")
            # Try alternative URLs
            if download_from_alternative_url(data_dir):
                return True
            return False
            
    except Exception as e:
        print(f"Error downloading land polygons: {e}")
        # Try alternative URLs
        if download_from_alternative_url(data_dir):
            return True
        return False

def download_from_alternative_url(data_dir):
    """
    Try downloading from alternative URLs if the main one fails.
    
    Args:
        data_dir (str): Directory to save the data to
        
    Returns:
        bool: True if download was successful, False otherwise
    """
    # Alternative URLs
    urls = [
        "https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/110m/physical/ne_110m_land.zip",
        "https://github.com/nvkelso/natural-earth-vector/raw/master/110m_physical/ne_110m_land.zip",
    ]
    
    for url in urls:
        print(f"Trying alternative URL: {url}")
        try:
            # Download the zip file
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            # Extract the zip file
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                z.extractall(data_dir)
            
            # Check if the shapefile exists
            shapefile = os.path.join(data_dir, 'ne_110m_land.shp')
            if os.path.exists(shapefile):
                print(f"Successfully downloaded and extracted land polygons to {shapefile}")
                return True
        except Exception as e:
            print(f"Error with alternative URL {url}: {e}")
    
    return False

if __name__ == "__main__":
    print("Downloading Natural Earth land polygons for Sentinel City Explorer")
    success = download_natural_earth_land()
    if success:
        print("Land polygon data is now available for the Sentinel City Explorer")
    else:
        print("Failed to download land polygon data")
        sys.exit(1)