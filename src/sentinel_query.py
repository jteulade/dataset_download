"""
Sentinel Query Module

This module provides functions for querying Sentinel-2 Global Mosaics data from the Copernicus Data Space API.
"""

import os
import json
import requests
from datetime import datetime, timedelta
import math
import random
import numpy as np
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon
import geopandas as gpd
import warnings
import traceback
from src.token_manager import ensure_valid_token, get_access_token, is_token_valid

# Global variable to store the land polygons once loaded
_LAND_POLYGONS = None

# Create data directory path
# First, get the project root directory (parent of src)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Use a common data directory in the project root
data_dir = os.path.join(project_root, 'data')
os.makedirs(data_dir, exist_ok=True)

def load_or_refresh_token(token_file=None):
    """
    Load or refresh the authentication token.
    
    Args:
        token_file (str, optional): Path to the token file. If None, the default path is used.
        
    Returns:
        str: The access token, or None if no valid token could be obtained
    """
    # This function now uses the token_manager.get_access_token() function
    return get_access_token(token_file)

def query_sentinel2_by_coordinates(lat, lon, year="2023", output_dir="results",
                                  city_name=None, city_lat=None, city_lon=None, is_neighbor=False, save_results=False):
    """
    Query Sentinel-2 data for the specified coordinates and year.
    
    Args:
        lat (float): Latitude
        lon (float): Longitude
        year (str): Year to filter for
        output_dir (str): Directory to save output files
        city_name (str, optional): Name of the associated city
        city_lat (float, optional): Latitude of the associated city
        city_lon (float, optional): Longitude of the associated city
        is_neighbor (bool): Whether this is a neighbor (random) point
        save_results (bool): Whether to save individual results to files
        
    Returns:
        dict or None: The query result, or None if the query failed
    """
    # Ensure we have a valid token before making API requests
    access_token = get_access_token()
    if not access_token:
        print("Failed to obtain a valid access token")
        return None
        
    # Set up the request headers with the token
    headers = {'Authorization': f'Bearer {access_token}'}
    
    # Define the quarters to query
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    
    # Define the bounding box size (in degrees)
    box_size = 0.1
    
    # Create results directories
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize the result structure
    result_structure = {
        'areas': [],
        'properties': {
            'totalAreas': 0,
            'totalProducts': 0
        }
    }
    
    # Dictionary to organize products by tile
    tiles = {}
    
    # Track products that contain the query point
    products_containing_point = []
    
    # List to store all quarterly products
    quarterly_products = []
    
    # Calculate distance from query point to city center if city coordinates are provided
    distance_km = 0
    if city_lat is not None and city_lon is not None and lat is not None and lon is not None:
        # Convert to radians
        lon1, lat1, lon2, lat2 = map(math.radians, [city_lon, city_lat, lon, lat])
        
        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371  # Radius of Earth in kilometers
        distance_km = c * r
    
    # Query each quarter
    for quarter in quarters:
        # Make the OData request with coordinates
        url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
        
        # Create a spatial filter using the bounding box
        spatial_filter = f"OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(({lon-box_size} {lat-box_size}, {lon-box_size} {lat+box_size}, {lon+box_size} {lat+box_size}, {lon+box_size} {lat-box_size}, {lon-box_size} {lat-box_size}))')"
        
        params = {
            "$filter": f"({spatial_filter}) and Collection/Name eq 'GLOBAL-MOSAICS' and contains(Name,'{year}_{quarter}')"
        }

        # Try the request, with token refresh if needed
        max_retries = 2
        for retry in range(max_retries + 1):
            response = requests.get(url, headers=headers, params=params)
            
            print(f"\n{year} {quarter}:")
            print(f"Status code: {response.status_code}")
            
            # If we get a 401 or 403, the token might be expired
            if response.status_code in [401, 403] and retry < max_retries:
                print(f"Authentication error ({response.status_code}). Refreshing token and retrying...")
                # Get a fresh token using our token manager
                new_access_token = get_access_token()
                if new_access_token:
                    # Update the headers with the new token
                    headers = {'Authorization': f'Bearer {new_access_token}'}
                    print(f"Token refreshed. Retrying request {retry+1}/{max_retries}...")
                else:
                    print("Failed to refresh token. Aborting query.")
                    break
            else:
                # Either success or a different error that we won't retry
                break
        
        # Process the response
        if response.status_code == 200:
            result = response.json()
            
            # Process each product
            for product in result.get('value', []):
                # Add the product entry
                product_entry = dict(product)
                product_entry["quarter"] = quarter
                
                # Check if this product contains the query point
                if 'GeoFootprint' in product and 'coordinates' in product['GeoFootprint']:
                    try:
                        if product['GeoFootprint']['type'] == 'Polygon':
                            # Extract coordinates - they are in [lon, lat] format in the API response
                            coords = product['GeoFootprint']['coordinates'][0]
                            
                            # Create a polygon from the coordinates - keep as [lon, lat] for Shapely
                            tile_polygon = Polygon(coords)
                            
                            # Check if the query point is inside this polygon
                            query_point = Point(lon, lat)  # Point takes (x, y) which is (lon, lat)
                            
                            if tile_polygon.contains(query_point):
                                print(f"Found product that contains the query point: {product.get('Name')}")
                                product_entry["contains_query_point"] = True
                                
                                # Add to the products_containing_point list
                                products_containing_point.append(product_entry)
                    except Exception as e:
                        print(f"Error checking if point is in tile: {e}")
                
                # Add to the quarterly_products list
                quarterly_products.append(product_entry)
    
    # Select the most relevant products (prioritize those containing the query point)
    if products_containing_point:
        print(f"Found {len(products_containing_point)} products that contain the query point.")
        # Only use products that contain the query point if there are any
        final_products = products_containing_point
    else:
        final_products = quarterly_products
    
    print(f"\nSelected {len(final_products)} out of {len(quarterly_products)} quarterly products")
    
    # Get the tile count
    tile_count = len(final_products)
    
    # Create the area entry
    area = {
        "year": year,
        "productCount": tile_count,
        "cityName": city_name,
        "cityLat": city_lat,
        "cityLon": city_lon,
        "isNeighbor": is_neighbor,
        "queryPointLat": lat,
        "queryPointLon": lon,
        "quarterlyProducts": final_products
    }
    
    # Create the final result structure
    result = {
        "areas": [area],
        "properties": {
            "totalProducts": tile_count,
            "totalAreas": 1,
            "year": year,
            "queryCoordinates": {
                "lat": lat,
                "lon": lon
            }
        }
    }
    
    return result

def is_point_on_land(lat, lon, debug=False):
    """
    Check if a geographic point is on land or in water.
    
    Args:
        lat (float): Latitude of the point
        lon (float): Longitude of the point
        debug (bool): Whether to print debug information
        
    Returns:
        bool: True if the point is on land, False if it's in water
    """
    global _LAND_POLYGONS
    
    # Create a Point object
    point = Point(lon, lat)
    
    # Load land polygons if not already loaded
    if _LAND_POLYGONS is None:
        try:
            # Try to load Natural Earth land polygons
            # First, check if we have the file locally in the project data directory
            ne_file = os.path.join(data_dir, 'ne_110m_land.shp')
            
            if os.path.exists(ne_file):
                print(f"Loading land polygons from {ne_file}")
                _LAND_POLYGONS = gpd.read_file(ne_file)
            else:
                # If file doesn't exist locally, return False as we can't determine if point is on land
                warnings.warn("Land polygon file not found. Cannot determine if point is on land.")
                return False
                
        except Exception as e:
            warnings.warn(f"Error loading land polygons: {e}. Cannot determine if point is on land.")
            return False
    
    # Check if the point is within any land polygon
    for idx, row in _LAND_POLYGONS.iterrows():
        try:
            if point.within(row.geometry):
                return True
        except Exception as e:
            pass
    
    return False

def get_random_point_at_distance(lat, lon, distance_km, ensure_on_land=True, max_attempts=10, debug=False):
    """
    Generate a random point at a specified distance from a given location.
    Optionally ensure the point is on land.
    
    Args:
        lat (float): Latitude of the center point
        lon (float): Longitude of the center point
        distance_km (float): Distance in kilometers
        ensure_on_land (bool): If True, ensure the generated point is on land
        max_attempts (int): Maximum number of attempts to find a point on land
        debug (bool): Whether to print debug information
        
    Returns:
        tuple or None: (latitude, longitude, is_on_land) of the random point, or None if ensure_on_land is True
                      and no land point could be found after max_attempts
    """
    # If we don't need to ensure the point is on land, just generate one point
    if not ensure_on_land:
        new_lat, new_lon = _generate_random_point_at_distance(lat, lon, distance_km)
        is_on_land = is_point_on_land(new_lat, new_lon, debug)
        return new_lat, new_lon, is_on_land
    
    # Try to find a point on land
    for attempt in range(max_attempts):
        new_lat, new_lon = _generate_random_point_at_distance(lat, lon, distance_km)
        is_on_land = is_point_on_land(new_lat, new_lon, debug)
        if is_on_land:
            return new_lat, new_lon, True
    
    # If we couldn't find a point on land after max_attempts, return None
    return None

def _generate_random_point_at_distance(lat, lon, distance_km):
    """
    Generate a random point at a specified distance from a given location.
    
    Args:
        lat (float): Latitude of the center point
        lon (float): Longitude of the center point
        distance_km (float): Distance in kilometers
        
    Returns:
        tuple: (latitude, longitude) of the random point
    """
    # Earth's radius in kilometers
    R = 6371.0
    
    # Convert distance to radians
    distance_rad = distance_km / R
    
    # Convert lat/lon to radians
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    
    # Generate a random bearing (0-360 degrees)
    bearing_rad = math.radians(random.uniform(0, 360))
    
    # Calculate new latitude
    new_lat_rad = math.asin(
        math.sin(lat_rad) * math.cos(distance_rad) +
        math.cos(lat_rad) * math.sin(distance_rad) * math.cos(bearing_rad)
    )
    
    # Calculate new longitude
    new_lon_rad = lon_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(distance_rad) * math.cos(lat_rad),
        math.cos(distance_rad) - math.sin(lat_rad) * math.sin(new_lat_rad)
    )
    
    # Convert back to degrees
    new_lat = math.degrees(new_lat_rad)
    new_lon = math.degrees(new_lon_rad)
    
    return new_lat, new_lon

if __name__ == "__main__":
    # Example usage
    import argparse
    
    parser = argparse.ArgumentParser(description="Query Sentinel-2 Global Mosaics data for specific coordinates")
    parser.add_argument("--lat", type=float, required=True,
                        help="Latitude of the point of interest")
    parser.add_argument("--lon", type=float, required=True,
                        help="Longitude of the point of interest")
    parser.add_argument("--year", type=str, default="2023",
                        help="Year to filter for (default: '2023')")
    parser.add_argument("--output-dir", type=str, default="results",
                        help="Directory to save output files")
    parser.add_argument("--city-name", type=str,
                        help="Name of the associated city")
    parser.add_argument("--city-lat", type=float,
                        help="Latitude of the associated city")
    parser.add_argument("--city-lon", type=float,
                        help="Longitude of the associated city")
    parser.add_argument("--is-neighbor", type=bool, default=False,
                        help="Whether this point is a neighbor/random point of a city")
    
    args = parser.parse_args()
    
    # Query Sentinel-2 data
    result = query_sentinel2_by_coordinates(
        lat=args.lat,
        lon=args.lon,
        year=args.year,
        output_dir=args.output_dir,
        city_name=args.city_name,
        city_lat=args.city_lat,
        city_lon=args.city_lon,
        is_neighbor=args.is_neighbor
    )
    
    # Print summary
    if result:
        print(f"\nSummary:")
        print(f"- Coordinates: ({args.lat}, {args.lon})")
        print(f"- Found {result['properties']['totalProducts']} Sentinel-2 Global Mosaic products")
        
        # Print details of each feature
        for i, product in enumerate(result['areas'][0]['quarterlyProducts']):
            print(f"\nFeature {i+1}:")
            print(f"- Name: {product.get('Name', 'Unknown')}")
            print(f"- ID: {product.get('Id', 'Unknown')}")
            print(f"- Size: {product.get('ContentLength', 'Unknown')} bytes")
            print(f"- Content Type: {product.get('ContentType', 'Unknown')}")
            print(f"- Distance: {result['areas'][0]['distanceKm']:.2f} km") 