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

# Global variable to store the land polygons once loaded
_LAND_POLYGONS = None

# Global constants for token handling
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
TOKEN_FILE = 'copernicus_dataspace_token.json'

# Create data directory for land polygons if it doesn't exist
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(data_dir, exist_ok=True)

def is_token_valid(access_token):
    """
    Check if the current access token is valid.
    
    Args:
        access_token (str): The access token to check
        
    Returns:
        bool: True if the token is valid, False otherwise
    """
    if not access_token:
        print("No access token available to check")
        return False
    
    try:
        # Try to get user info with the current token
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

def refresh_access_token(token_file=TOKEN_FILE):
    """
    Refresh the access token using the refresh token.
    
    Args:
        token_file (str): Path to the token file
        
    Returns:
        dict or None: New token data if refresh was successful, None otherwise
    """
    try:
        with open(token_file, 'r') as file:
            token_data = json.load(file)
            refresh_token = token_data.get('refresh_token')
            
            if not refresh_token:
                raise ValueError('No refresh token found')

            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': 'cdse-public'
            }

            response = requests.post(TOKEN_URL, headers=headers, data=data)
            response.raise_for_status()
            
            new_token_data = response.json()
            
            # Update the token file with new tokens
            with open(token_file, 'w') as f:
                json.dump(new_token_data, f)
            
            print("Access token refreshed successfully")
            
            return new_token_data

    except Exception as e:
        print(f'Error refreshing access token: {e}')
        print(f'Stacktrace:\n{traceback.format_exc()}')
        return None

def load_or_refresh_token(token_file=TOKEN_FILE):
    """
    Load the token from file and refresh it if necessary.
    
    Args:
        token_file (str): Path to the token file
        
    Returns:
        str or None: The valid access token if available, None otherwise
    """
    try:
        # Load the token
        with open(token_file, 'r') as f:
            token_data = json.load(f)
            access_token = token_data.get('access_token')
        
        # Check if token is valid
        if access_token and is_token_valid(access_token):
            return access_token
        
        # Token is invalid, try to refresh
        print("Token is invalid or expired, attempting to refresh...")
        new_token_data = refresh_access_token(token_file)
        
        if new_token_data:
            return new_token_data.get('access_token')
        else:
            print("Token refresh failed. Please generate a new token.")
            return None
    
    except Exception as e:
        print(f"Error loading or refreshing token: {e}")
        return None

def query_sentinel2_by_coordinates(lat, lon, year="2023", output_dir="results",
                                  city_name=None, city_lat=None, city_lon=None, is_neighbor=False, save_results=False):
    """
    Query the Copernicus Data Space API for Sentinel-2 Global Mosaics data based on coordinates.
    
    Args:
        lat (float): Latitude of the point of interest
        lon (float): Longitude of the point of interest
        year (str): Year to filter for (default: "2023")
        output_dir (str): Directory to save output files
        city_name (str): Name of the associated city
        city_lat (float): Latitude of the associated city
        city_lon (float): Longitude of the associated city
        is_neighbor (bool): Whether this point is a neighbor/random point of a city
        save_results (bool): Whether to save individual query results
        
    Returns:
        dict: Structured JSON with areas and quarterly products
    """
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Create a bounding box around the point
    # Use a larger bounding box for random points to ensure better coverage
    box_size = 0.2 if is_neighbor else 0.1  # 0.2 degrees is roughly 22km at the equator
    
    # Define quarters to check
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    
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
    
    # Load and refresh token if needed
    access_token = load_or_refresh_token()
    if not access_token:
        print("Failed to obtain a valid access token")
        return None
    
    # Set up headers
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    
    # Create a structure to store quarterly products
    all_quarterly_products = []
    
    # Check each quarter
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
                # Refresh the token
                new_token_data = refresh_access_token()
                if new_token_data:
                    # Update the headers with the new token
                    access_token = new_token_data.get('access_token')
                    headers = {'Authorization': f'Bearer {access_token}'}
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
                # Create product entry by using the original product data
                product_entry = dict(product)  # Copy all original fields
                
                # Set the quarter for reference
                product_entry["quarter"] = quarter
                
                # Default: point is not inside this product's footprint
                product_entry["contains_query_point"] = False
                
                # Try to get additional metadata from the RESTO API endpoint
                product_id = product.get('Id')
                if product_id:
                    resto_url = f"https://catalogue.dataspace.copernicus.eu/resto/collections/GLOBAL-MOSAICS/{product_id}.json"
                    # Try the RESTO API request with token refresh if needed
                    max_resto_retries = 2
                    for resto_retry in range(max_resto_retries + 1):
                        try:
                            resto_response = requests.get(resto_url, headers=headers)
                            
                            # If we get a 401 or 403, the token might be expired
                            if resto_response.status_code in [401, 403] and resto_retry < max_resto_retries:
                                print(f"Authentication error ({resto_response.status_code}) in RESTO API. Refreshing token...")
                                # Refresh the token
                                new_token_data = refresh_access_token()
                                if new_token_data:
                                    # Update the headers with the new token
                                    access_token = new_token_data.get('access_token')
                                    headers = {'Authorization': f'Bearer {access_token}'}
                                    print(f"Token refreshed. Retrying RESTO API request {resto_retry+1}/{max_resto_retries}...")
                                else:
                                    print("Failed to refresh token for RESTO API. Skipping metadata.")
                                    break
                            else:
                                # Process the response
                                if resto_response.status_code == 200:
                                    resto_data = resto_response.json()
                                    
                                    # Add the RESTO API geometry
                                    if 'geometry' in resto_data:
                                        product_entry["restoGeometry"] = resto_data['geometry']
                                        
                                        # Check if query point is inside this product's geometry
                                        geom = resto_data['geometry']
                                        if geom.get('type') == 'Polygon' and 'coordinates' in geom:
                                            # Extract the coordinates of the polygon
                                            coords = geom['coordinates'][0]  # First ring of coordinates
                                            
                                            # Convert coordinates to a shapely polygon
                                            poly_coords = [(coord[0], coord[1]) for coord in coords]
                                            try:
                                                from shapely.geometry import Point, Polygon
                                                polygon = Polygon(poly_coords)
                                                point = Point(lon, lat)
                                                
                                                # Check if point is inside polygon
                                                product_entry["contains_query_point"] = polygon.contains(point)
                                                
                                                if product_entry["contains_query_point"]:
                                                    print(f"Found product that contains the query point: {product.get('Name')}")
                                            except Exception as e:
                                                print(f"Error checking if point is in polygon: {e}")
                                            
                                            # Calculate the centroid (simple average of coordinates)
                                            centroid_lon = sum(coord[0] for coord in coords) / len(coords)
                                            centroid_lat = sum(coord[1] for coord in coords) / len(coords)
                                            
                                            # Store the centroid
                                            product_entry["centroid"] = {
                                                "lat": centroid_lat,
                                                "lon": centroid_lon
                                            }
                                            
                                            # Calculate distance from query point to centroid using Haversine formula
                                            # Convert to radians
                                            q_lon, q_lat = math.radians(lon), math.radians(lat)
                                            c_lon, c_lat = math.radians(centroid_lon), math.radians(centroid_lat)
                                            
                                            # Haversine formula
                                            dlon = c_lon - q_lon
                                            dlat = c_lat - q_lat
                                            a = math.sin(dlat/2)**2 + math.cos(q_lat) * math.cos(c_lat) * math.sin(dlon/2)**2
                                            c = 2 * math.asin(math.sqrt(a))
                                            r = 6371  # Radius of Earth in kilometers
                                            
                                            # Store the distance to query point
                                            product_entry["distance_to_query"] = c * r
                                        
                                    # Add the RESTO API properties
                                    if 'properties' in resto_data:
                                        product_entry["restoProperties"] = resto_data['properties']
                                else:
                                    print(f"Failed to get RESTO metadata for product {product_id}: {resto_response.status_code}")
                                
                                # We've either succeeded or failed with a non-auth error, so break the retry loop
                                break
                                
                        except Exception as e:
                            print(f"Error fetching RESTO metadata: {e}")
                            # If RESTO API fails, add our own download URL as fallback
                            if not product.get('downloadUrl') and not product.get('services', {}).get('download', {}).get('url'):
                                product_entry["downloadUrl"] = f"https://catalogue.dataspace.copernicus.eu/odata/v1/Products({product.get('Id')})/$value"
                            break
                
                # If no centroid was calculated (no geometry or error), create a fallback
                if "centroid" not in product_entry:
                    # Use the query coordinates as a fallback and set a high distance
                    product_entry["centroid"] = {
                        "lat": lat,
                        "lon": lon
                    }
                    # Set a high distance value to rank these products lower
                    product_entry["distance_to_query"] = 1000.0
                
                all_quarterly_products.append(product_entry)
    
    # First, check if we found any products that contain the query point
    products_containing_point = [p for p in all_quarterly_products if p.get("contains_query_point", False)]
    
    if products_containing_point:
        print(f"Found {len(products_containing_point)} products that contain the query point.")
        # Sort by distance to query point for products that contain the point
        products_containing_point.sort(key=lambda x: x.get("distance_to_query", 1000.0))
        quarterly_products = products_containing_point[:min(4, len(products_containing_point))]
        
        # If we need more products, get the closest ones regardless of containing the point
        if len(quarterly_products) < 4:
            print(f"Need {4 - len(quarterly_products)} more products. Adding closest ones.")
            remaining_products = [p for p in all_quarterly_products if p not in quarterly_products]
            remaining_products.sort(key=lambda x: x.get("distance_to_query", 1000.0))
            quarterly_products.extend(remaining_products[:min(4 - len(quarterly_products), len(remaining_products))])
    else:
        print(f"No products found that contain the query point. Using closest products by distance.")
        # Sort products by distance to query point (closest first)
        all_quarterly_products.sort(key=lambda x: x.get("distance_to_query", 1000.0))
        
        # Take the first 4 products (or all if less than 4)
        quarterly_products = all_quarterly_products[:min(4, len(all_quarterly_products))]
    
    print(f"\nSelected {len(quarterly_products)} out of {len(all_quarterly_products)} quarterly products")
    
    # Get the tile count
    tile_count = len(quarterly_products)
    
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
        "quarterlyProducts": quarterly_products
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
            # First, check if we have the file locally
            ne_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                  'data', 'ne_110m_land.shp')
            
            if os.path.exists(ne_file):
                print(f"Loading land polygons from {ne_file}")
                _LAND_POLYGONS = gpd.read_file(ne_file)
            else:
                # If file doesn't exist locally, use a simplified approach
                print("Land polygon file not found. Using simplified continent polygons.")
                _LAND_POLYGONS = _create_simplified_land_polygons()
                
        except Exception as e:
            warnings.warn(f"Error loading land polygons: {e}. Using simplified continent polygons.")
            _LAND_POLYGONS = _create_simplified_land_polygons()
    
    # Check if the point is within any land polygon
    for idx, row in _LAND_POLYGONS.iterrows():
        try:
            if point.within(row.geometry):
                return True
        except Exception as e:
            pass
    
    return False

def _create_simplified_land_polygons():
    """
    Create a simplified set of land polygons for the major continents.
    This is a fallback when the Natural Earth dataset is not available.
    
    Returns:
        geopandas.GeoDataFrame: A GeoDataFrame with simplified continent polygons
    """
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
    return gdf

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