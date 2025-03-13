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

# Global variable to store the land polygons once loaded
_LAND_POLYGONS = None

# Create data directory for land polygons if it doesn't exist
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(data_dir, exist_ok=True)

def query_sentinel2_by_coordinates(lat, lon, start_date=None, end_date=None, 
                                  max_records=10, output_dir="results", year_filter="2022",
                                  city_name=None, city_lat=None, city_lon=None, is_neighbor=False):
    """
    Query the Copernicus Data Space API for Sentinel-2 Global Mosaics data based on coordinates.
    
    Args:
        lat (float): Latitude of the point of interest
        lon (float): Longitude of the point of interest
        start_date (str): Start date in format "YYYY-MM-DD" (defaults to beginning of year_filter)
        end_date (str): End date in format "YYYY-MM-DD" (defaults to end of year_filter)
        max_records (int): Maximum number of records to return (default: 10)
        output_dir (str): Directory to save output files
        year_filter (str): Year to filter for (e.g., "2022")
        city_name (str): Name of the associated city
        city_lat (float): Latitude of the associated city
        city_lon (float): Longitude of the associated city
        is_neighbor (bool): Whether this point is a neighbor/random point of a city
        
    Returns:
        dict: Dictionary containing query results and file paths
    """
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Set default dates if not provided
    if start_date is None:
        if year_filter:
            start_date = f"{year_filter}-01-01"  # Start from beginning of specified year
        else:
            start_date = "2020-01-01"  # Default to 2020 for mosaics
    
    if end_date is None:
        if year_filter:
            end_date = f"{year_filter}-12-31"  # End at end of specified year
        else:
            end_date = datetime.now().strftime("%Y-%m-%d")
    
    # Format dates for API
    start_date_formatted = f"{start_date}T00:00:00Z"
    end_date_formatted = f"{end_date}T23:59:59Z"
    
    # Create a bounding box around the point (approximately 10km)
    # 0.1 degrees is roughly 11km at the equator
    box_size = 0.1
    bbox = f"{lon-box_size},{lat-box_size},{lon+box_size},{lat+box_size}"
    
    # Base URL and parameters for Global Mosaics
    url = "https://catalogue.dataspace.copernicus.eu/resto/api/collections/GLOBAL-MOSAICS/search.json"
    params = {
        "startDate": start_date_formatted,
        "completionDate": end_date_formatted,
        "maxRecords": str(max_records),  # Request the specified number of records
        "box": bbox,  # This is the key parameter for spatial filtering
        "platform": "SENTINEL-2"  # Explicitly filter for SENTINEL-2 platform
    }
    print(f"Querying Sentinel-2 Global Mosaic data for coordinates ({lat}, {lon})")
    
    # Make the request
    response = requests.get(url, params=params)
    print(f"Request URL: {response.url}")
    
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return None
    
    # Parse the JSON response
    json_data = response.json()
    
    # Check if we have features
    if 'features' not in json_data or len(json_data['features']) == 0:
        print(f"No results found for coordinates ({lat}, {lon})")
        return {
            'lat': lat,
            'lon': lon,
            'features': [],
            'count': 0,
            'json_data': json_data
        }
    
    # Helper function to check if a point is inside a polygon
    def point_in_polygon(point, polygon):
        """
        Check if a point is inside a polygon using the ray casting algorithm.
        
        Args:
            point (tuple): Point coordinates (x, y)
            polygon (list): List of polygon vertices [(x1, y1), (x2, y2), ...]
            
        Returns:
            bool: True if the point is inside the polygon, False otherwise
        """
        x, y = point
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    # Process the features
    features = json_data['features']
    print(f"Found {len(features)} features")
    
    # Extract key information from properties
    processed_features = []
    for feature in features:
        props = feature['properties']
        
        # Extract footprint if available
        footprint = None
        if 'footprint' in props:
            footprint = props['footprint']
        
        # Extract tile ID from title
        tile_id = None
        if 'title' in props:
            title = props['title']
            # Example title format: "Sentinel-2_mosaic_2022_Q4_19GFH_0_0"
            parts = title.split('_')
            if len(parts) >= 5:
                tile_id = parts[4]  # Extract the tile ID part
        
        # Calculate distance from the query point to the center of the tile
        # This is used for ranking tiles
        distance_km = 0
        if 'centroid' in props:
            centroid = props['centroid']
            # Handle different centroid formats
            try:
                # Check if centroid is a list/array with at least 2 elements
                if isinstance(centroid, (list, tuple)) and len(centroid) >= 2:
                    lon2, lat2 = centroid[0], centroid[1]
                # Check if centroid is a dictionary with lon/lat keys
                elif isinstance(centroid, dict) and 'lon' in centroid and 'lat' in centroid:
                    lon2, lat2 = centroid['lon'], centroid['lat']
                # Check if centroid is a dictionary with coordinates array
                elif isinstance(centroid, dict) and 'coordinates' in centroid and len(centroid['coordinates']) >= 2:
                    lon2, lat2 = centroid['coordinates'][0], centroid['coordinates'][1]
                else:
                    # If we can't parse the centroid, use the query coordinates
                    print(f"Warning: Could not parse centroid format: {centroid}")
                    lon2, lat2 = lon, lat
                
                # Convert to radians
                lon1, lat1, lon2, lat2 = map(math.radians, [lon, lat, lon2, lat2])
                
                # Haversine formula
                dlon = lon2 - lon1
                dlat = lat2 - lat1
                a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
                c = 2 * math.asin(math.sqrt(a))
                r = 6371  # Radius of Earth in kilometers
                distance_km = c * r
            except (TypeError, IndexError, KeyError) as e:
                print(f"Warning: Error calculating distance: {e}")
                # If there's an error, set distance to 0
                distance_km = 0
        
        # Create a processed feature
        processed_feature = {
            'title': props.get('title', 'Unknown'),
            'platform': props.get('platform', 'Unknown'),
            'start_date': props.get('startDate', 'Unknown'),
            'completion_date': props.get('completionDate', 'Unknown'),
            'product_type': props.get('productType', 'Unknown'),
            'tile_id': tile_id,
            'footprint': footprint,
            'distance_km': distance_km,
            'download_url': props.get('services', {}).get('download', {}).get('url'),
            'original_feature': feature,
            # Add the new metadata fields
            'city_name': city_name,
            'city_lat': city_lat,
            'city_lon': city_lon,
            'is_neighbor': is_neighbor
        }
        
        processed_features.append(processed_feature)
    
    # Sort features by distance (closest first)
    processed_features.sort(key=lambda x: x['distance_km'])
    
    # Return all features up to max_records
    selected_features = processed_features[:max_records]
    print(f"Selected {len(selected_features)} tiles")
    
    # Create a result object
    result = {
        'lat': lat,
        'lon': lon,
        'features': selected_features,
        'count': len(selected_features),
        'json_data': json_data,  # Include the full JSON data in the result
        'is_mosaic': True,
        # Add the city metadata to the result object as well
        'city_name': city_name,
        'city_lat': city_lat,
        'city_lon': city_lon,
        'is_neighbor': is_neighbor
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
    parser.add_argument("--start-date", type=str,
                        help="Start date in format YYYY-MM-DD (default: based on year-filter)")
    parser.add_argument("--end-date", type=str,
                        help="End date in format YYYY-MM-DD (default: based on year-filter)")
    parser.add_argument("--max-records", type=int, default=10,
                        help="Maximum number of records to return (default: 10)")
    parser.add_argument("--output-dir", type=str, default="results",
                        help="Directory to save output files")
    parser.add_argument("--year-filter", type=str, default="2022",
                        help="Year to filter for (e.g., '2022')")
    
    args = parser.parse_args()
    
    # Query Sentinel-2 data
    result = query_sentinel2_by_coordinates(
        lat=args.lat,
        lon=args.lon,
        start_date=args.start_date,
        end_date=args.end_date,
        max_records=args.max_records,
        output_dir=args.output_dir,
        year_filter=args.year_filter
    )
    
    # Print summary
    if result:
        print(f"\nSummary:")
        print(f"- Coordinates: ({args.lat}, {args.lon})")
        print(f"- Found {result['count']} Sentinel-2 Global Mosaic tiles")
        
        # Print details of each feature
        for i, feature in enumerate(result['features']):
            print(f"\nFeature {i+1}:")
            print(f"- Title: {feature['title']}")
            print(f"- Start Date: {feature['start_date']}")
            print(f"- Product Type: {feature['product_type']}")
            if feature['tile_id']:
                print(f"- Tile ID: {feature['tile_id']}")
            print(f"- Distance: {feature['distance_km']:.2f} km") 