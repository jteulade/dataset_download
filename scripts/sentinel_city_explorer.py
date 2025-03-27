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

# Add the project root directory to the Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from src.city_selector import load_city_data, select_dispersed_cities
from src.sentinel_query import query_sentinel2_by_coordinates, get_random_point_at_distance, is_point_on_land

def main():
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
    parser.add_argument("--download-land-data", action="store_true", default=False,
                        help="Download land polygon data before starting")
    parser.add_argument("--min-city-distance", type=int, default=500,
                        help="Minimum distance between cities in kilometers (default: 500)")
    parser.add_argument("--skip-post-processing", action="store_true", default=False,
                        help="Skip post-processing step to ensure minimum city distance")
    parser.add_argument("--random-seed", type=int, default=None,
                        help="Random seed for reproducible results")
    
    args = parser.parse_args()
    
    # Set random seed if provided
    if args.random_seed is not None:
        import random
        import numpy as np
        random.seed(args.random_seed)
        np.random.seed(args.random_seed)
        print(f"Set random seed to {args.random_seed}")
    else:
        # If no seed provided, generate one and use it
        import random
        import numpy as np
        random_seed = random.randint(0, 2**32 - 1)
        random.seed(random_seed)
        np.random.seed(random_seed)
        print(f"Using generated random seed: {random_seed}")
    
    # Always refresh the token before starting
    from src.token_manager import get_access_token
    print("Refreshing token before starting")
    refreshed = get_access_token()
    if refreshed:
        print("Token refreshed successfully")
    else:
        print("Failed to refresh token. Will try to generate a new one when needed.")
    
    # Download land polygon data if requested
    if args.download_land_data:
        try:
            from src.download_land_polygons import download_natural_earth_land
            print("Downloading land polygon data...")
            success = download_natural_earth_land()
            if success:
                print("Land polygon data downloaded successfully.")
            else:
                print("Failed to download land polygon data. Using simplified land polygons.")
        except ImportError:
            print("Warning: download_land_polygons.py not found. Skipping download.")
    
    # Step 1: Load city data
    print("\n=== Step 1: Loading and selecting cities ===")
    cities_df = load_city_data(args.cities_csv, args.population_min)
    
    # Step 2: Select dispersed cities
    selected_cities = select_dispersed_cities(
        cities_df, 
        args.num_cities,
        min_distance_km=args.min_city_distance,
        apply_post_processing=not args.skip_post_processing
    )
    print(f"Selected {len(selected_cities)} dispersed cities")
    
    # Save selected cities to CSV
    selected_cities_file = os.path.join(args.output_dir, "selected_cities.csv")
    os.makedirs(args.output_dir, exist_ok=True)
    selected_cities.to_csv(selected_cities_file, index=False)
    print(f"Selected cities saved to {selected_cities_file}")
    
    # Step 3: Query Sentinel-2 data for each city
    print("\n=== Step 2: Querying Sentinel-2 Global Mosaics data for each city ===")
    
    # Create a unified structure for all areas and products
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
                "download_land_data": args.download_land_data,
                "min_city_distance": args.min_city_distance,
                "skip_post_processing": args.skip_post_processing,
                "random_seed": args.random_seed if args.random_seed is not None else random_seed
            }
        }
    }
    
    # Track land/water statistics
    random_points_on_land = 0
    random_points_in_water = 0
    skipped_random_points = 0
    
    for _, city in selected_cities.iterrows():
        lat, lon = city['lat'], city['lng']
        city_name = city['city']
        
        # Query for the city center
        print(f"\nCity: {city_name} ({lat}, {lon})")
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
        
        if result:
            # Add area to the unified result
            if 'areas' in result and result['areas']:
                unified_result['areas'].extend(result['areas'])
                unified_result['properties']['totalAreas'] += len(result['areas'])
                unified_result['properties']['totalProducts'] += result['properties']['totalProducts']
            
            # Extract data from the result structure
            area = result['areas'][0] if 'areas' in result and result['areas'] else None
            
            if area and area.get('quarterlyProducts', []):
                # Get the tile ID if present
                tile_id = None
                for product in area['quarterlyProducts']:
                    if 'Name' in product:
                        parts = product['Name'].split('_')
                        if len(parts) >= 5:
                            tile_id = parts[4]
                            break
                
                if tile_id:
                    print(f"Selected the tile for {city_name}")
                    print(f"Tile ID: {tile_id}")
                    print(f"Distance from city center: 0.00 km")
                    print(f"Contains {len(area['quarterlyProducts'])} quarterly products for {args.year_filter}")
            else:
                print(f"No Sentinel-2 data found for {city_name}")
        
        # Generate a random point at the specified distance and query for it
        print(f"\nGenerating random point {args.random_distance} km away from {city_name}...")
        
        # Initialize random_point_result as None in case all the following code paths fail
        random_point_result = None
        
        # Before generating a random point, let's check if we have a valid city tile footprint
        if result and 'areas' in result and result['areas']:
            area = result['areas'][0]
            city_footprint_found = False
            city_tile_id = None
            
            # Get the tile ID if present
            for product in area.get('quarterlyProducts', []):
                if 'Name' in product:
                    parts = product['Name'].split('_')
                    if len(parts) >= 5:
                        city_tile_id = parts[4]
                        break
            
            # Get the footprint coordinates if available in the original feature
            original_feature = next((p for p in area.get('quarterlyProducts', []) if 'restoGeometry' in p), None)
            coords = []
            
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
            
            # If we found the city tile footprint, generate points within a sensible distance
            # but also in a different tile
            if city_footprint_found and city_tile_id:
                # Log city footprint info without printing
                city_footprint_info = f"Found city tile footprint for {city_name} with ID {city_tile_id}"
                
                # Create a polygon from the coordinates
                from shapely.geometry import Polygon, Point
                city_polygon = Polygon(coords)
                
                # Attempt to find a point within a different tile at the specified distance
                max_attempts = 20  # Increase attempts since we're more selective now
                found_valid_point = False
                
                for attempt in range(max_attempts):
                    # Generate a random point at the specified distance
                    random_point_result = get_random_point_at_distance(
                        lat, lon, args.random_distance, 
                        ensure_on_land=args.ensure_on_land,
                        max_attempts=args.max_land_attempts
                    )
                    
                    if random_point_result is None:
                        continue
                        
                    random_lat, random_lon, is_on_land = random_point_result
                    
                    # Check if this point is outside the city tile footprint
                    # We want to find a point in a different tile
                    if not city_polygon.contains(Point(random_lon, random_lat)):
                        found_valid_point = True
                        print(f"Found valid random point outside the city tile after {attempt+1} attempts")
                        break
                
                if not found_valid_point:
                    print(f"Could not find a random point outside the city tile after {max_attempts} attempts.")
                    print(f"Falling back to standard random point generation.")
                    random_point_result = get_random_point_at_distance(
                        lat, lon, args.random_distance, 
                        ensure_on_land=args.ensure_on_land,
                        max_attempts=args.max_land_attempts
                    )
            else:
                # Fallback to standard random point generation
                random_point_result = get_random_point_at_distance(
                    lat, lon, args.random_distance, 
                    ensure_on_land=args.ensure_on_land,
                    max_attempts=args.max_land_attempts
                )
        
        # Skip this random point if we couldn't find a point
        if random_point_result is None:
            print(f"Could not find a point on land after {args.max_land_attempts} attempts. Skipping random point for {city_name}.")
            skipped_random_points += 1
            continue
            
        random_lat, random_lon, is_on_land = random_point_result
        
        # Update land/water statistics
        if is_on_land:
            random_points_on_land += 1
            land_status = "on land"
        else:
            random_points_in_water += 1
            land_status = "in water"
            
        print(f"Random point {args.random_distance} km away: ({random_lat}, {random_lon}) - {land_status}")
        
        # After generating the random point, add extra check to ensure it will be in a different tile
        # than the city's tile by using a smaller bounding box for the query
        if city_tile_id:
            neighborhood_size = 0.05  # Smaller neighborhood to increase chance of single tile match
        else:
            neighborhood_size = None  # Use default size
        
        # Query Sentinel-2 data for the random point
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
        
        # Handle the random point result
        if random_result:
            # Add area to the unified result
            if 'areas' in random_result and random_result['areas']:
                unified_result['areas'].extend(random_result['areas'])
                unified_result['properties']['totalAreas'] += len(random_result['areas'])
                unified_result['properties']['totalProducts'] += random_result['properties']['totalProducts']
            
            # Extract data from the new result structure
            area = random_result['areas'][0] if 'areas' in random_result and random_result['areas'] else None
            
            if area and area.get('quarterlyProducts', []):
                # Get the tile ID if present
                tile_id = None
                for product in area['quarterlyProducts']:
                    if 'Name' in product:
                        parts = product['Name'].split('_')
                        if len(parts) >= 5:
                            tile_id = parts[4]
                            break
                
                if tile_id:
                    print(f"\nRandom Point Tile Details:")
                    print(f"  Tile ID: {tile_id}")
                    print(f"  Contains {len(area['quarterlyProducts'])} quarterly products for {args.year_filter}")
                    print(f"  Distance from city center: {args.random_distance:.2f} km")
                    
                    if any('downloadUrl' in p or ('restoProperties' in p and 'services' in p['restoProperties'] and 'download' in p['restoProperties']['services']) for p in area['quarterlyProducts']):
                        print(f"  Download URL available")
            else:
                print(f"No Sentinel-2 data found for the random point near {city_name}")
        else:
            print(f"Query failed for the random point near {city_name}")
    
    # Save the unified JSON file with all areas
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unified_file = os.path.join(args.output_dir, f"S2_GlobalMosaics_{args.year_filter}_unified_{timestamp}.json")
    with open(unified_file, 'w') as f:
        json.dump(unified_result, f, indent=2)
    
    print(f"\nSaved unified JSON with {unified_result['properties']['totalAreas']} areas and {unified_result['properties']['totalProducts']} products to {unified_file}")
    
    # Print summary
    total_random_points_attempted = random_points_on_land + random_points_in_water + skipped_random_points
    
    print(f"\n=== Summary ===")
    print(f"- Selected {len(selected_cities)} dispersed cities")
    print(f"- Total Sentinel-2 Global Mosaic areas: {unified_result['properties']['totalAreas']}")
    print(f"- Total Sentinel-2 Global Mosaic products: {unified_result['properties']['totalProducts']}")
    
    # Calculate percentages based on non-skipped points
    total_random_points_generated = random_points_on_land + random_points_in_water
    if total_random_points_generated > 0:
        land_percent = random_points_on_land / total_random_points_generated * 100
        water_percent = random_points_in_water / total_random_points_generated * 100
    else:
        land_percent = water_percent = 0
        
    # Calculate percentage of skipped points based on total attempts
    if total_random_points_attempted > 0:
        skipped_percent = skipped_random_points / total_random_points_attempted * 100
    else:
        skipped_percent = 0
    
    print(f"- Random points on land: {random_points_on_land} ({land_percent:.1f}% of generated points)")
    print(f"- Random points in water: {random_points_in_water} ({water_percent:.1f}% of generated points)")
    print(f"- Random points skipped: {skipped_random_points} ({skipped_percent:.1f}% of attempted points)")
    print(f"- Unified JSON saved to {unified_file}")
    
    print("\n=== Process Complete ===")
    print(f"You can now use the download_from_json.py script to download the tiles:")
    print(f"python scripts/download_from_json.py --json-file {unified_file} --output-dir downloads")
    print(f"\nTo visualize the results, use visualize_quarterly_products.py:")
    print(f"python scripts/visualize_quarterly_products.py --input-json {unified_file}")

if __name__ == "__main__":
    main() 