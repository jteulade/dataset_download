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
    """
    # Create data directory if it doesn't exist
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
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
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Error downloading land polygons: {e}")
        # Try alternative URL if the first one fails
        return download_from_alternative_url(data_dir)
    except zipfile.BadZipFile as e:
        print(f"Error extracting land polygons: {e}")
        return download_from_alternative_url(data_dir)
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

def download_from_alternative_url(data_dir):
    """
    Try downloading from an alternative URL if the primary one fails.
    """
    alt_url = "https://github.com/nvkelso/natural-earth-vector/raw/master/110m_physical/ne_110m_land.zip"
    print(f"Trying alternative URL: {alt_url}")
    
    try:
        # Download the zip file with a proper user agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(alt_url, headers=headers)
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
            return create_simplified_land_file(data_dir)
            
    except Exception as e:
        print(f"Error downloading from alternative URL: {e}")
        print("Using simplified land polygons instead.")
        return create_simplified_land_file(data_dir)

def create_simplified_land_file(data_dir):
    """
    Create a simplified land polygon file as a fallback.
    """
    try:
        print("Creating simplified land polygon file as fallback...")
        
        # Import required modules
        import geopandas as gpd
        from shapely.geometry import Polygon
        
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
        
        # Save as shapefile
        shapefile = os.path.join(data_dir, 'ne_110m_land.shp')
        gdf.to_file(shapefile)
        
        print(f"Successfully created simplified land polygon file at {shapefile}")
        return True
        
    except Exception as e:
        print(f"Error creating simplified land polygon file: {e}")
        return False

if __name__ == "__main__":
    success = download_natural_earth_land()
    sys.exit(0 if success else 1) 