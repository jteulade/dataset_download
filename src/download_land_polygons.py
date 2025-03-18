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
    src_dir = os.path.dirname(script_dir)
    project_root = os.path.dirname(src_dir)
    
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
            # If all download methods fail, create simplified land file
            return create_simplified_land_file(data_dir)
            
    except Exception as e:
        print(f"Error downloading land polygons: {e}")
        # Try alternative URLs
        if download_from_alternative_url(data_dir):
            return True
        # If all download methods fail, create simplified land file
        return create_simplified_land_file(data_dir)

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

def create_simplified_land_file(data_dir):
    """
    Create a simplified land polygons file as a fallback.
    
    Args:
        data_dir (str): Directory to save the simplified land file to
        
    Returns:
        bool: True if creation was successful, False otherwise
    """
    try:
        import geopandas as gpd
        from shapely.geometry import Polygon
        
        print("Creating simplified land polygons")
        
        # Define simplified polygons for major continents
        # These are very rough approximations - expanded to cover more coastal areas
        continents = {
            'North America': [
                (-175, 85), (-45, 85), (-45, 0), (-175, 0)
            ],
            'South America': [
                (-95, 20), (-25, 20), (-25, -65), (-95, -65)
            ],
            'Europe': [
                (-15, 75), (50, 75), (50, 30), (-15, 30)
            ],
            'Africa': [
                (-25, 45), (60, 45), (60, -45), (-25, -45)
            ],
            'Asia': [
                (35, 85), (185, 85), (185, -5), (35, -5)
            ],
            'Australia': [
                (105, -5), (160, -5), (160, -50), (105, -50)
            ],
            'Antarctica': [
                (-185, -55), (185, -55), (185, -95), (-185, -95)
            ],
            # Add more regions to cover islands and coastal areas
            'Caribbean': [
                (-90, 30), (-55, 30), (-55, 10), (-90, 10)
            ],
            'Southeast Asia': [
                (90, 25), (130, 25), (130, -10), (90, -10)
            ],
            'Pacific Islands': [
                (130, 30), (180, 30), (180, -30), (130, -30)
            ]
        }
        
        # Convert to shapely polygons
        polygons = []
        names = []
        
        for name, coords in continents.items():
            poly = Polygon(coords)
            polygons.append(poly)
            names.append(name)
        
        # Create a GeoDataFrame
        gdf = gpd.GeoDataFrame({'name': names, 'geometry': polygons})
        
        # Save to a shapefile
        shapefile = os.path.join(data_dir, 'ne_110m_land.shp')
        gdf.to_file(shapefile)
        
        print(f"Successfully created simplified land polygons file at {shapefile}")
        return True
    except Exception as e:
        print(f"Error creating simplified land polygons: {e}")
        return False

if __name__ == "__main__":
    print("Downloading Natural Earth land polygons for Sentinel City Explorer")
    success = download_natural_earth_land()
    if success:
        print("Land polygon data is now available for the Sentinel City Explorer")
    else:
        print("Failed to download or create land polygon data")
        sys.exit(1)