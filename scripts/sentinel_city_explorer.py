#!/usr/bin/env python3
"""
Sentinel City Explorer

This script combines the functionality of the city_selector and sentinel_query
modules to select geographically dispersed cities and query Sentinel-2 data for each city.
"""

import argparse
import os
import json
from datetime import datetime
import sys
from pathlib import Path
import random
import numpy as np
import logging as log
from shapely.geometry import Polygon, Point # type: ignore

log.basicConfig(level=log.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add the project root directory to the Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from src.city_selector import load_city_data, select_dispersed_cities
from src.sentinel_query import query_sentinel2_by_coordinates, get_random_point_at_distance, is_point_on_land
from src.token_manager import get_access_token

def setup_random_seed(seed=None):
    """Set up random seed for reproducibility
    
    Args:
        seed (int): Random seed value. If None, a random seed will be generated.
   
    Returns:
        int: The random seed used.
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
        log.info(f"Set random seed to {seed}")
    else:
        # If no seed provided, generate one and use it
        random_seed = random.randint(0, 2**32 - 1)
        random.seed(random_seed)
        np.random.seed(random_seed)
        log.info(f"Using generated random seed: {random_seed}")
        return random_seed
    return seed

def parse_arguments():
    """Parse command line arguments
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Query Sentinel-2 Global Mosaics data for dispersed cities")
    parser.add_argument("--cities-csv", type=str, default="worldcities.csv",
                        help="Path to the CSV file containing city data (e.g., worldcities.csv)")
    parser.add_argument("--num-cities", type=int, default=20,
                        help="Number of geographically dispersed cities to select")
    parser.add_argument("--population-min", type=int, default=500000,
                        help="Minimum population threshold for cities")
    parser.add_argument("--output-dir", type=str, default="results",
                        help="Directory to save output files")
    parser.add_argument("--year-filter", type=str, default="2023",
                        help="Year to filter for (e.g., '2023')")
    parser.add_argument("--random-distance", type=int, default=300,
                        help="Distance in kilometers for random points from cities (default: 100)")
    parser.add_argument("--ensure-on-land", action="store_true", default=True,
                        help="Only generate random points on land. If no land point is found after max-land-attempts, the random point will be skipped (default: True)")
    parser.add_argument("--max-land-attempts", type=int, default=10,
                        help="Maximum attempts to find a random point on land (default: 10)")
    parser.add_argument("--min-city-distance", type=int, default=500,
                        help="Minimum distance between cities in kilometers (default: 500)")
    parser.add_argument("--random-seed", type=int, default=None,
                        help="Random seed for reproducible results")
    
    return parser.parse_args()

def get_city_tile_info(result):
    """Extract tile ID, coordinates and footprint information from query result
    
    Parameters:
        result (dict): The query result containing areas and products
    Returns:
        tuple: A tuple containing the city tile ID, coordinates of the city footprint, and a boolean indicating if the footprint was found
    """
    # Check if the result contains areas
    if not result or 'areas' not in result or not result['areas']:
        return None, None, None
    
    # Extract the first area from the result
    area = result['areas'][0]
    city_tile_id = None
    coords = []
    city_footprint_found = False
    
    # Get the tile ID if present
    for product in area.get('quarterlyProducts', []):
        if 'Name' in product:
            parts = product['Name'].split('_')
            if len(parts) >= 5:
                city_tile_id = parts[4]
                break
    
    # Get the footprint coordinates if available
    original_feature = next((p for p in area.get('quarterlyProducts', []) if 'restoGeometry' in p), None)
    
    if original_feature:
        # First try direct restoGeometry
        if 'restoGeometry' in original_feature:
            geom = original_feature['restoGeometry']
            if 'type' in geom and geom['type'] == 'Polygon' and 'coordinates' in geom:
                geometry_coords = geom['coordinates'][0]
                # Convert from [lon, lat] to [lat, lon] for compatibility
                coords = [(coord[1], coord[0]) for coord in geometry_coords]
                city_footprint_found = True
        # Then try standard geometry
        elif 'geometry' in original_feature and original_feature['geometry']['type'] == 'Polygon':
            geometry_coords = original_feature['geometry']['coordinates'][0]
            coords = [(coord[1], coord[0]) for coord in geometry_coords]
            city_footprint_found = True
    
    return city_tile_id, coords, city_footprint_found

def generate_random_point(lat, lon, args, city_polygon=None):
    """Generate a random point at the specified distance from the city
    
    Parameters:
        lat (float): Latitude of the city
        lon (float): Longitude of the city
        args (argparse.Namespace): Parsed command line arguments
        city_polygon (Polygon, optional): Polygon representing the city footprint
    Returns:
        tuple: A tuple containing the latitude, longitude, and a boolean indicating if the point is on land
    """
    # If we have a city polygon, try to find a point outside it
    if city_polygon:
        max_attempts = 20
        found_valid_point = False
        
        for attempt in range(max_attempts):
            random_point_result = get_random_point_at_distance(
                lat, lon, args.random_distance, 
                ensure_on_land=args.ensure_on_land,
                max_attempts=args.max_land_attempts
            )
            
            if random_point_result is None:
                continue
                
            random_lat, random_lon, is_on_land = random_point_result
            
            # Check if this point is outside the city tile footprint
            if not city_polygon.contains(Point(random_lon, random_lat)):
                found_valid_point = True
                log.info(f"Found valid random point outside the city tile after {attempt+1} attempts")
                return random_point_result
        
        if not found_valid_point:
            log.warning(f"Could not find a random point outside the city tile after {max_attempts} attempts.")
            log.warning(f"Falling back to standard random point generation.")
    
    # Standard random point generation
    return get_random_point_at_distance(
        lat, lon, args.random_distance, 
        ensure_on_land=args.ensure_on_land,
        max_attempts=args.max_land_attempts
    )

def process_city(city, args, unified_result):
    """Process a single city and its random point
    
    Parameters:
        city (dict): Dictionary containing city information
        args (argparse.Namespace): Parsed command line arguments
        unified_result (dict): Dictionary to store the unified result
    Returns:
        tuple: A tuple containing the number of random points on land, in water, and skipped
    """
    lat, lon = city['lat'], city['lng']
    city_name = city['city']

    # Initialize city_polygon to None
    city_polygon = None


    # Query for the city center
    log.info(f"\nCity: {city_name} ({lat}, {lon})")
    result = query_sentinel2_by_coordinates(
        lat=lat,
        lon=lon,
        year=args.year_filter,
        output_dir=args.output_dir,
        city_name=city_name,
        city_lat=lat,
        city_lon=lon,
        is_neighbor=False
    )
    
    # Process city result
    city_tile_id = None
    if result and 'areas' in result and result['areas']:
        unified_result['areas'].extend(result['areas'])
        unified_result['properties']['totalAreas'] += len(result['areas'])
        unified_result['properties']['totalProducts'] += result['properties']['totalProducts']
        
        # Extract tile ID and footprint information
        city_tile_id, coords, city_footprint_found = get_city_tile_info(result)
        
        # Create city polygon if footprint found
        if city_footprint_found and coords:
            city_polygon = Polygon(coords)
        
       
    
    # Generate random point
    log.info(f"\nGenerating random point {args.random_distance} km away from {city_name}...")
    random_point_result = generate_random_point(lat, lon, args, city_polygon if city_polygon else None)
    
    # Skip if no random point found
    if random_point_result is None:
        log.warning (f"Could not find a point on land after {args.max_land_attempts} attempts. Skipping random point for {city_name}.")
        return 0, 0, 1  # on_land, in_water, skipped
    
    random_lat, random_lon, is_on_land = random_point_result
    
    # Update land/water statistics
    if is_on_land:
        land_status = "on land"
        on_land = 1
        in_water = 0
    else:
        land_status = "in water"
        on_land = 0
        in_water = 1
        
    log.info(f"Random point {args.random_distance} km away: ({random_lat}, {random_lon}) - {land_status}")
    
    # Query Sentinel-2 data for the random point
    neighborhood_size = 0.05 if city_tile_id else None
    random_result = query_sentinel2_by_coordinates(
        lat=random_lat,
        lon=random_lon,
        year=args.year_filter,
        output_dir=args.output_dir,
        city_name=city_name,
        city_lat=lat,
        city_lon=lon,
        is_neighbor=True
    )
    
    # Process random point result
    if random_result and 'areas' in random_result and random_result['areas']:
        unified_result['areas'].extend(random_result['areas'])
        unified_result['properties']['totalAreas'] += len(random_result['areas'])
        unified_result['properties']['totalProducts'] += random_result['properties']['totalProducts']
    
    return on_land, in_water, 0  # on_land, in_water, skipped



def save_results(unified_result, output_dir, year_filter):
    """Save the unified result to a JSON file.
    
    Parameters:
        unified_result (dict): The unified result containing areas and properties
        output_dir (str): Directory to save the output file
        year_filter (str): Year filter used in the query
    Returns:
        str: Path to the saved JSON file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unified_file = os.path.join(output_dir, f"S2_GlobalMosaics_{year_filter}_unified_{timestamp}.json")
    with open(unified_file, 'w') as f:
        json.dump(unified_result, f, indent=2)
    return unified_file



def main():
    # Parse arguments
    args = parse_arguments()
    
    # Validate arguments
    if not os.path.isfile(args.cities_csv):
        log.error(f"Cities CSV file not found: {args.cities_csv}")
        sys.exit(1)

    if args.num_cities <= 0:
        log.error("Number of cities (--num-cities) must be greater than 0.")
        sys.exit(1)

    if args.population_min < 0:
        log.error("Minimum population (--population-min) cannot be negative.")
        sys.exit(1)

    if args.random_distance <= 0:
        log.error("Random distance (--random-distance) must be greater than 0.")
        sys.exit(1)

    if args.max_land_attempts <= 0:
        log.error("Maximum land attempts (--max-land-attempts) must be greater than 0.")
        sys.exit(1)

    if args.min_city_distance <= 0:
        log.error("Minimum city distance (--min-city-distance) must be greater than 0.")
        sys.exit(1)

    if not os.path.exists(args.output_dir):
        try:
            os.makedirs(args.output_dir)
            log.info(f"Created output directory: {args.output_dir}")
        except Exception as e:
            log.error(f"Failed to create output directory: {args.output_dir}. Error: {e}")
            sys.exit(1)

    if not args.year_filter.isdigit() or len(args.year_filter) != 4:
        log.error("Year filter (--year-filter) must be a valid 4-digit year (e.g., '2023').")
        sys.exit(1)

    if args.random_seed is not None and args.random_seed < 0:
        log.error("Random seed (--random-seed) must be a non-negative integer.")
        sys.exit(1)

    # Set up random seed
    random_seed = setup_random_seed(args.random_seed)
    
    # Refresh token
    log.info("Refreshing token before starting")
    refreshed = get_access_token()
    if refreshed:
        log.info("Token refreshed successfully")
    else:
        log.warning("Failed to refresh token. Will try to generate a new one when needed.")
    
    # Load and select cities
    log.info("\n=== Step 1: Loading and selecting cities ===")
    cities_df = load_city_data(args.cities_csv, args.population_min)
    if cities_df.empty:
        log.error("No cities found.")
        sys.exit(1)

    selected_cities = select_dispersed_cities(
        cities_df, 
        args.num_cities,
        min_distance_km=args.min_city_distance
    )
    if selected_cities.empty:
        log.error("No cities found that meet the criteria.")
        sys.exit(1)

    log.info(f"Selected {len(selected_cities)} dispersed cities")
    
    # Save selected cities to CSV
    os.makedirs(args.output_dir, exist_ok=True)
    selected_cities_file = os.path.join(args.output_dir, "selected_cities.csv")
    selected_cities.to_csv(selected_cities_file, index=False)
    log.info(f"Selected cities saved to {selected_cities_file}")
    
    # Initialize result structure
    unified_result = {
        "areas": [],
        "properties": {
            "totalProducts": 0,
            "totalAreas": 0,
            "description": "Combined Sentinel-2 Global Mosaics data for selected cities and random neighbor points",
            "command_line_args": {
                "cities_csv": args.cities_csv,
                "num_cities": args.num_cities,
                "population_min": args.population_min,
                "output_dir": args.output_dir,
                "year_filter": args.year_filter,
                "random_distance": args.random_distance,
                "ensure_on_land": args.ensure_on_land,
                "max_land_attempts": args.max_land_attempts,
                "min_city_distance": args.min_city_distance,
                "random_seed": random_seed
            }
        }
    }
    
    # Process each city
    log.info("\n=== Step 2: Querying Sentinel-2 Global Mosaics data for each city ===")
    random_points_on_land = 0
    random_points_in_water = 0
    skipped_random_points = 0
    
    for _, city in selected_cities.iterrows():
        on_land, in_water, skipped = process_city(city, args, unified_result)
        random_points_on_land += on_land
        random_points_in_water += in_water
        skipped_random_points += skipped
    
    # Save results
    unified_file = save_results(unified_result, args.output_dir, args.year_filter)
    
    # Print summary
    log.info(f"\nSaved unified JSON with {unified_result['properties']['totalAreas']} areas and {unified_result['properties']['totalProducts']} products to {unified_file}")
    
    total_random_points_attempted = random_points_on_land + random_points_in_water + skipped_random_points
    total_random_points_generated = random_points_on_land + random_points_in_water
    

    # Calculate percentages
    try:
        land_percent = (random_points_on_land / total_random_points_generated * 100) if total_random_points_generated > 0 else 0
        water_percent = (random_points_in_water / total_random_points_generated * 100) if total_random_points_generated > 0 else 0
        skipped_percent = (skipped_random_points / total_random_points_attempted * 100) if total_random_points_attempted > 0 else 0
    except ZeroDivisionError:
        log.error("Division by zero error while calculating percentages.")
        land_percent = 0
        water_percent = 0
        skipped_percent = 0
    
    log.info(f"\n=== Summary ===")
    log.info(f"- Selected {len(selected_cities)} dispersed cities")
    log.info(f"- Total Sentinel-2 Global Mosaic areas: {unified_result['properties']['totalAreas']}")
    log.info(f"- Total Sentinel-2 Global Mosaic products: {unified_result['properties']['totalProducts']}")
    log.info(f"- Random points on land: {random_points_on_land} ({land_percent:.1f}% of generated points)")
    log.info(f"- Random points in water: {random_points_in_water} ({water_percent:.1f}% of generated points)")
    log.info(f"- Random points skipped: {skipped_random_points} ({skipped_percent:.1f}% of attempted points)")
    log.info(f"- Unified JSON saved to {unified_file}")
    
    log.info("\n=== Process Complete ===")
    log.info(f"You can now use the download_from_json.py script to download the tiles:")
    log.info(f"python scripts/download_from_json.py --json-file {unified_file} --output-dir downloads")
    log.info(f"\nTo visualize the results, use visualize_quarterly_products.py:")
    log.info(f"python scripts/visualize_quarterly_products.py --input-json {unified_file}")
    
if __name__ == "__main__":
    main() 