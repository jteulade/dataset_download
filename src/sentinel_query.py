"""
Sentinel Query Module

This module provides functions for querying Sentinel-2 Global Mosaics data from the Copernicus Data Space API.
"""

import os
import json
import logging 
import requests
import sys
from datetime import datetime, timedelta
import math
import random
import numpy as np
from shapely.geometry import Point # type: ignore
from shapely.geometry.polygon import Polygon # type: ignore
import geopandas as gpd # type: ignore
import warnings
from src.token_manager import ensure_valid_token, get_access_token

# Global variable to store the land polygons once loaded
_LAND_POLYGONS = None

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create data directory path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(project_root, 'data')
os.makedirs(data_dir, exist_ok=True)
import sys

def make_sentinel_request(url : str, headers : dict, params : dict, max_retries : int =2):
    """
    Make a request to the Sentinel API with token refresh handling.
    
    Args:
        url : The URL to request
        headers : The request headers
        params : The request parameters
        max_retries : Maximum number of retries
        
    Returns:
        The response from the API
    """
    for retry in range(max_retries + 1):
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code in [401, 403] and retry < max_retries:
            logging.info(f"Authentication error ({response.status_code}). Refreshing token...")
            new_access_token = get_access_token()
            if new_access_token:
                headers = {'Authorization': f'Bearer {new_access_token}'}
                continue
            break
        return response
    return response

def process_product(product : dict, quarter : str, query_point):
    """
    Process a single Sentinel product and check if it contains the query point.
    
    Args:
        product : The product data from the API
        quarter : The quarter (Q1, Q2, Q3, Q4)
        query_point : The query point coordinates (lon, lat)
        
    Returns:
        (product_entry, contains_point) where product_entry is the processed product
            and contains_point is a boolean indicating if the product contains the query point
    """
    try:
        product_entry = dict(product)
        product_entry["quarter"] = quarter
        
        if 'GeoFootprint' in product and 'coordinates' in product['GeoFootprint']:
            try:
                if product['GeoFootprint']['type'] == 'Polygon':
                    coords = product['GeoFootprint']['coordinates'][0]
                    tile_polygon = Polygon(coords)
                    # Point takes (x, y) which is (lon, lat)
                    query_point_obj = Point(query_point[0], query_point[1])
                    
                    if tile_polygon.contains(query_point_obj):
                        product_entry["contains_query_point"] = True
                        return product_entry, True
            except Exception as e:
                logging.error(f"Error checking if point is in tile: {e}")
        
        return product_entry, False
    except KeyError as e:
        logging.error(f"KeyError while processing product: {e}")
        return None, False
    except Exception as e:
        logging.error(f"Unexpected error while processing product: {e}")
        return None, False

def select_best_products(products_containing_point : list, quarterly_products : list):
    """
    Select the best products based on tile ID and query point containment.
    
    Args:
        products_containing_point : List of products that contain the query point
        quarterly_products : List of all quarterly products
        
    Returns:
        list: The selected products
    """
    if products_containing_point:
        logging.info(f"Found {len(products_containing_point)} products that contain the query point.")
        best_tile_id = None
        for product in products_containing_point:
            if 'Name' in product:
                parts = product['Name'].split('_')
                if len(parts) >= 5:
                    best_tile_id = parts[4]
                    break
        
        if best_tile_id:
            final_products = [p for p in products_containing_point 
                            if 'Name' in p and best_tile_id in p['Name']]
            logging.info(f"Selected {len(final_products)} products from the best tile {best_tile_id}")
        else:
            final_products = products_containing_point
    else:
        # If no products contain the query point, try to find the closest tile
        if quarterly_products:
            # Get the tile ID from the first product
            first_product = quarterly_products[0]
            if 'Name' in first_product:
                parts = first_product['Name'].split('_')
                if len(parts) >= 5:
                    best_tile_id = parts[4]  # Extract the tile ID part
                    # Filter to only keep products from this tile
                    final_products = [p for p in quarterly_products 
                                    if 'Name' in p and best_tile_id in p['Name']]
                    logging.info(f"Selected {len(final_products)} products from the closest tile {best_tile_id}")
                else:
                    final_products = quarterly_products
        else:
            final_products = []
    
    return final_products

def query_sentinel2_by_coordinates(lat : float, lon : float, year : str ="2023", output_dir : str ="results",
                                  city_name : str =None, city_lat : float =None, city_lon : float =None, is_neighbor : bool =False, save_results : bool =False):
    """
    Query Sentinel-2 data for the specified coordinates and year.
    
    Args:
        lat : Latitude
        lon : Longitude
        year : Year to filter for
        output_dir : Directory to save output files
        city_name : Name of the associated city
        city_lat : Latitude of the associated city
        city_lon : Longitude of the associated city
        is_neighbor : Whether this is a neighbor (random) point
        save_results : Whether to save individual results to files
        
    Returns:
        The query result, or None if the query failed
    """
    access_token = get_access_token()
    if not access_token:
        logging.warning("Failed to obtain a valid access token")
        return None
        
    headers = {'Authorization': f'Bearer {access_token}'}
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    box_size = 0.1
    os.makedirs(output_dir, exist_ok=True)
    
    products_containing_point = []
    quarterly_products = []
    
    # Calculate distance from query point to city center if provided
    distance_km = 0
    if all(x is not None for x in [city_lat, city_lon, lat, lon]):
        lon1, lat1, lon2, lat2 = map(math.radians, [city_lon, city_lat, lon, lat])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        distance_km = c * 6371  # Radius of Earth in kilometers
    
    # Query each quarter
    for quarter in quarters:
        url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
        spatial_filter = f"OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(({lon-box_size} {lat-box_size}, {lon-box_size} {lat+box_size}, {lon+box_size} {lat+box_size}, {lon+box_size} {lat-box_size}, {lon-box_size} {lat-box_size}))')"
        params = {
            "$filter": f"({spatial_filter}) and Collection/Name eq 'GLOBAL-MOSAICS' and contains(Name,'{year}_{quarter}')"
        }

        response = make_sentinel_request(url, headers, params)
        print(f"\n")
        logging.info(f"{year} {quarter}:")
        logging.info(f"Status code: {response.status_code}")
        
        result = handle_api_error(response, year, quarter)
        for product in result.get('value', []):
            product_entry, contains_point = process_product(product, quarter, (lon, lat))
            if contains_point:
                products_containing_point.append(product_entry)
       
    
    # Select the best products, passing both city coordinates and query point
    city_coords = (city_lat, city_lon) if all(x is not None for x in [city_lat, city_lon]) else None
    query_point = (lat, lon)
    final_products = select_best_products(products_containing_point, quarterly_products)
    
    # Ensure we have exactly one product per quarter
    if len(final_products) != 4:
        found_quarters = set(p.get('quarter') for p in final_products)
        missing_quarters = set(quarters) - found_quarters
        logging.warning(f"Warning: Found {len(final_products)} products instead of expected 4.")
        logging.warning(f"Missing quarters: {missing_quarters}")
        logging.warning(f"Found quarters: {found_quarters}")
        return None
    
    # Sort products by quarter
    final_products.sort(key=lambda x: x.get('quarter'))
    logging.info(f"\nSelected {len(final_products)} out of {len(quarterly_products)} quarterly products")
    
    # Create the result structure
    area = {
        "year": year,
        "productCount": len(final_products),
        "cityName": city_name,
        "cityLat": city_lat,
        "cityLon": city_lon,
        "isNeighbor": is_neighbor,
        "queryPointLat": lat,
        "queryPointLon": lon,
        "quarterlyProducts": final_products
    }
    
    result = {
        "areas": [area],
        "properties": {
            "totalProducts": len(final_products),
            "totalAreas": 1,
            "year": year,
            "queryCoordinates": {
                "lat": lat,
                "lon": lon
            }
        }
    }
    
    return result

def handle_api_error(response, year : str, quarter : str):
    """
    Handle API errors and stop execution if necessary.
    
    Args:
        response : The API response object.
        year : The year of the query.
        quarter : The quarter of the query.
    """
    try:
        response.raise_for_status()
    except Exception as e:
        logging.error(f"HTTP error: {e}")
        sys.exit(1)

    result = response.json()
    if not result.get('value', []):
        logging.error(f"Error: No products found for {year} {quarter}. Stopping execution.\033[0m")
        sys.exit(1)
    return result

def is_point_on_land(lat : float, lon : float, debug : bool=False):
    """
    Check if a geographic point is on land or in water.
    
    Args:
        lat : Latitude of the point
        lon : Longitude of the point
        debug : Whether to print debug information
        
    Returns:
        True if the point is on land, False if it's in water
    """
    global _LAND_POLYGONS
    
    point = Point(lon, lat)
    
    if _LAND_POLYGONS is None:
        try:
            ne_file = os.path.join(data_dir, 'ne_110m_land.shp')
            if os.path.exists(ne_file):
                logging.info(f"Loading land polygons from {ne_file}")
                _LAND_POLYGONS = gpd.read_file(ne_file)
            else:
                warnings.warn("Land polygon file not found. Cannot determine if point is on land.")
                return False
        except ImportError:
            warnings.warn("Geopandas not installed. Cannot determine if point is on land.")
            return False
        except FileNotFoundError:
            warnings.warn("Land polygon file not found. Cannot determine if point is on land.")
            return False
        except ValueError:
            warnings.warn("Error parsing land polygon file. Cannot determine if point is on land.")
            return False
        except Exception as e:
            warnings.warn(f"Error loading land polygons: {e}. Cannot determine if point is on land.")
            return False
    
    return any(point.within(row.geometry) for _, row in _LAND_POLYGONS.iterrows())

def get_random_point_at_distance(lat : float, lon : float, distance_km : float, ensure_on_land : bool =True, max_attempts : int =10, debug : bool =False):
    """
    Generate a random point at a specified distance from a given location.
    Optionally ensure the point is on land.
    
    Args:
        lat : Latitude of the center point
        lon : Longitude of the center point
        distance_km : Distance in kilometers
        ensure_on_land : If True, ensure the generated point is on land
        max_attempts : Maximum number of attempts to find a point on land
        debug : Whether to print debug information
        
    Returns:
        (latitude, longitude, is_on_land) of the random point, or None if ensure_on_land is True
                and no land point could be found after max_attempts
    """
    if not ensure_on_land:
        new_lat, new_lon = _generate_random_point_at_distance(lat, lon, distance_km)
        return new_lat, new_lon, is_point_on_land(new_lat, new_lon, debug)
    
    for _ in range(max_attempts):
        new_lat, new_lon = _generate_random_point_at_distance(lat, lon, distance_km)
        if is_point_on_land(new_lat, new_lon, debug):
            return new_lat, new_lon, True
    
    return None

def _generate_random_point_at_distance(lat : float, lon : float, distance_km : float):
    """
    Generate a random point at a specified distance from a given location.
    
    Args:
        lat : Latitude of the center point
        lon : Longitude of the center point
        distance_km : Distance in kilometers
        
    Returns:
        (latitude, longitude) of the random point
    """
    R = 6371.0  # Earth's radius in kilometers
    distance_rad = distance_km / R
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    bearing_rad = math.radians(random.uniform(0, 360))
    
    new_lat_rad = math.asin(
        math.sin(lat_rad) * math.cos(distance_rad) +
        math.cos(lat_rad) * math.sin(distance_rad) * math.cos(bearing_rad)
    )
    
    new_lon_rad = lon_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(distance_rad) * math.cos(lat_rad),
        math.cos(distance_rad) - math.sin(lat_rad) * math.sin(new_lat_rad)
    )
    
    return math.degrees(new_lat_rad), math.degrees(new_lon_rad)