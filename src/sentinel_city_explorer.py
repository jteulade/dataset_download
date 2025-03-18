#!/usr/bin/env python3
"""
Sentinel City Explorer

This script combines the functionality of the city_selector, sentinel_query, and map_visualizer
modules to select geographically dispersed cities, query Sentinel-2 data for each city,
and visualize the results on an interactive map.
"""

import argparse
import os
import json
from datetime import datetime
from src.city_selector import load_city_data, select_dispersed_cities
from src.sentinel_query import query_sentinel2_by_coordinates, get_random_point_at_distance, is_point_on_land
from src.map_visualizer import create_mosaic_map

def main():
    parser = argparse.ArgumentParser(description="Query Sentinel-2 Global Mosaics data for dispersed cities and visualize the results")
    parser.add_argument("--cities-csv", type=str, default="worldcities.csv",
                        help="Path to the CSV file containing city data (e.g., worldcities.csv)")
    parser.add_argument("--num-cities", type=int, default=20,
                        help="Number of geographically dispersed cities to select")
    parser.add_argument("--population-min", type=int, default=500000,
                        help="Minimum population threshold for cities")
    parser.add_argument("--output-dir", type=str, default="results",
                        help="Directory to save output files")
    parser.add_argument("--output-map", type=str, default="maps/city_mosaics_map.html",
                        help="Path to save the HTML map file")
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
    
    args = parser.parse_args()
    
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
    cities_results = []
    random_points_results = []
    
    # Create a unified structure for all areas and products
    unified_result = {
        "areas": [],
        "properties": {
            "totalProducts": 0,
            "totalAreas": 0,
            "description": "Combined Sentinel-2 Global Mosaics data for selected cities and random neighbor points"
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
                # Create a structure compatible with the original explorer
                compat_result = {
                    'lat': lat,
                    'lon': lon,
                    'city_name': city_name,
                    'city_lat': lat,
                    'city_lon': lon,
                    'is_neighbor': False,
                    'count': 1,  # We're treating the area as a single feature now
                    'features': []
                }
                
                # Instead of creating individual features for each quarterly product,
                # create a single "area" feature that represents the tile
                # Use the first product to get basic information, but include all quarters
                first_product = area['quarterlyProducts'][0] if area['quarterlyProducts'] else None
                
                if first_product:
                    area_feature = {
                        'title': f"Sentinel-2 Tile for {city_name} - {len(area['quarterlyProducts'])} quarters",
                        'id': first_product.get('Id', ''),
                        'product_type': 'S2 Global Mosaic Area',
                        'quarterly_count': len(area['quarterlyProducts']),
                        'quarters': [p.get('Name', '').split('_')[-2] for p in area['quarterlyProducts']],
                        'year': args.year_filter,
                        # Get geometry from first product that has restoGeometry
                        'original_feature': next((p for p in area['quarterlyProducts'] if 'restoGeometry' in p), first_product)
                    }
                    
                    # Extract dates 
                    if 'ContentDate' in first_product:
                        area_feature['start_date'] = first_product['ContentDate'].get('Start', '')
                        area_feature['end_date'] = first_product['ContentDate'].get('End', '')
                    
                    # Add download URL from first product
                    if 'downloadUrl' in first_product:
                        area_feature['download_url'] = first_product['downloadUrl']
                    elif 'restoProperties' in first_product and 'services' in first_product['restoProperties'] and 'download' in first_product['restoProperties']['services']:
                        area_feature['download_url'] = first_product['restoProperties']['services']['download'].get('url', '')
                    
                    # Add the tile ID if present
                    tile_id = None
                    for product in area['quarterlyProducts']:
                        if 'Name' in product:
                            # Try to extract tile ID from the name
                            # Format is typically: Sentinel-2_mosaic_YEAR_QUARTER_TILEID_RESOLUTION_VERSION
                            parts = product['Name'].split('_')
                            if len(parts) >= 5:
                                tile_id = parts[4]
                                break
                    
                    if tile_id:
                        area_feature['tile_id'] = tile_id
                    
                    compat_result['features'].append(area_feature)
                
                # Store raw data for JSON output
                compat_result['json_data'] = {'area': area}
                
                if 'tile_id' in area_feature:
                    print(f"Selected the tile for {city_name}")
                    print(f"Tile ID: {area_feature['tile_id']}")
                    print(f"Distance from city center: 0.00 km")
                    print(f"Contains {area_feature.get('quarterly_count', 0)} quarterly products for {args.year_filter}")
                
                cities_results.append(compat_result)
            else:
                # No products found, create an empty result
                empty_result = {
                    'lat': lat,
                    'lon': lon,
                    'city_name': city_name,
                    'city_lat': lat,
                    'city_lon': lon,
                    'is_neighbor': False,
                    'count': 0,
                    'features': [],
                    'json_data': {'features': []}
                }
                cities_results.append(empty_result)
                print(f"No Sentinel-2 data found for {city_name}")
        
        # Generate a random point at the specified distance and query for it
        print(f"\nGenerating random point {args.random_distance} km away from {city_name}...")
        
        # Initialize random_point_result as None in case all the following code paths fail
        random_point_result = None
        
        # Before generating a random point, let's check if we have a valid city tile footprint
        if cities_results and cities_results[-1].get('count', 0) > 0 and cities_results[-1].get('features', []):
            city_feature = cities_results[-1]['features'][0]
            city_footprint_found = False
            city_tile_id = city_feature.get('tile_id')
            
            # Get the footprint coordinates if available in the original feature
            original_feature = city_feature.get('original_feature')
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
                # Create a structure compatible with the original explorer
                compat_result = {
                    'lat': random_lat,
                    'lon': random_lon,
                    'city_name': city_name,
                    'city_lat': lat,
                    'city_lon': lon,
                    'is_neighbor': True,
                    'is_on_land': is_on_land,
                    'land_status': land_status,
                    'distance_from_city': args.random_distance,
                    'original_city_lat': lat,
                    'original_city_lon': lon,
                    'count': 1,  # Treating area as one feature
                    'features': []
                }
                
                # Similar to city processing, create a single area feature
                first_product = area['quarterlyProducts'][0] if area['quarterlyProducts'] else None
                
                if first_product:
                    area_feature = {
                        'title': f"Sentinel-2 Tile for {city_name} (Random Point) - {len(area['quarterlyProducts'])} quarters",
                        'id': first_product.get('Id', ''),
                        'product_type': 'S2 Global Mosaic Area',
                        'quarterly_count': len(area['quarterlyProducts']),
                        'quarters': [p.get('Name', '').split('_')[-2] for p in area['quarterlyProducts']],
                        'year': args.year_filter,
                        # Get geometry from first product that has restoGeometry
                        'original_feature': next((p for p in area['quarterlyProducts'] if 'restoGeometry' in p), first_product)
                    }
                    
                    # Extract dates
                    if 'ContentDate' in first_product:
                        area_feature['start_date'] = first_product['ContentDate'].get('Start', '')
                        area_feature['end_date'] = first_product['ContentDate'].get('End', '')
                    
                    # Add download URL
                    if 'downloadUrl' in first_product:
                        area_feature['download_url'] = first_product['downloadUrl']
                    elif 'restoProperties' in first_product and 'services' in first_product['restoProperties'] and 'download' in first_product['restoProperties']['services']:
                        area_feature['download_url'] = first_product['restoProperties']['services']['download'].get('url', '')
                    
                    # Add the tile ID if present
                    tile_id = None
                    for product in area['quarterlyProducts']:
                        if 'Name' in product:
                            parts = product['Name'].split('_')
                            if len(parts) >= 5:
                                tile_id = parts[4]
                                break
                    
                    if tile_id:
                        area_feature['tile_id'] = tile_id
                    
                    compat_result['features'].append(area_feature)
                
                # Store raw data for JSON output
                compat_result['json_data'] = {'area': area}
                
                # Set the display name with land/water indicator
                land_indicator = "Land" if is_on_land else "Water"
                compat_result['display_name'] = f"{city_name} (Random Point - {land_indicator})"
                
                # Print summary and add to results
                if compat_result['features']:
                    best_feature = compat_result['features'][0]
                    print(f"\nRandom Point Tile Details:")
                    if 'tile_id' in best_feature:
                        print(f"  Tile ID: {best_feature['tile_id']}")
                    print(f"  Contains {best_feature.get('quarterly_count', 0)} quarterly products for {args.year_filter}")
                    print(f"  Distance from city center: {args.random_distance:.2f} km")
                    
                    # Add coordinates to the tile feature for better visualization
                    best_feature['query_point_lat'] = random_lat
                    best_feature['query_point_lon'] = random_lon
                    
                    if 'download_url' in best_feature:
                        print(f"  Download URL available")
                
                print(f"Found tile with Sentinel-2 data for the random point")
                random_points_results.append(compat_result)
            else:
                # No products found, create an empty result
                land_indicator = "Land" if is_on_land else "Water"
                empty_result = {
                    'lat': random_lat,
                    'lon': random_lon,
                    'display_name': f"{city_name} (Random Point - {land_indicator} - No Data)",
                    'city_name': city_name,
                    'city_lat': lat,
                    'city_lon': lon,
                    'is_neighbor': True,
                    'original_city_lat': lat,
                    'original_city_lon': lon,
                    'distance_from_city': args.random_distance,
                    'count': 0,
                    'features': [],
                    'is_on_land': is_on_land,
                    'land_status': land_status
                }
                random_points_results.append(empty_result)
                print(f"No Sentinel-2 data found for the random point near {city_name}")
        else:
            # Query failed, create an empty result
            land_indicator = "Land" if is_on_land else "Water"
            failed_result = {
                'lat': random_lat,
                'lon': random_lon,
                'display_name': f"{city_name} (Random Point - {land_indicator} - Query Failed)",
                'city_name': city_name,
                'city_lat': lat,
                'city_lon': lon,
                'is_neighbor': True,
                'original_city_lat': lat,
                'original_city_lon': lon,
                'distance_from_city': args.random_distance,
                'count': 0,
                'features': [],
                'is_on_land': is_on_land,
                'land_status': land_status
            }
            random_points_results.append(failed_result)
            print(f"Query failed for the random point near {city_name}")
    
    # Save only the unified JSON file with all areas
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unified_file = os.path.join(args.output_dir, f"S2_GlobalMosaics_{args.year_filter}_unified_{timestamp}.json")
    with open(unified_file, 'w') as f:
        json.dump(unified_result, f, indent=2)
    
    print(f"\nSaved unified JSON with {unified_result['properties']['totalAreas']} areas and {unified_result['properties']['totalProducts']} products to {unified_file}")
    
    # Combine city results and random point results for the map
    all_results = cities_results + random_points_results
    
    # Step 4: Create an interactive map
    print("\n=== Step 3: Creating interactive map ===")
    create_mosaic_map(all_results, args.output_map)
    
    # Print summary
    cities_with_data = sum(1 for r in cities_results if r['count'] > 0)
    random_points_with_data = sum(1 for r in random_points_results if r['count'] > 0)
    total_random_points_attempted = random_points_on_land + random_points_in_water + skipped_random_points
    
    print(f"\n=== Summary ===")
    print(f"- Selected {len(selected_cities)} dispersed cities")
    print(f"- Found Sentinel-2 Global Mosaic data for {cities_with_data} cities")
    print(f"- Found Sentinel-2 Global Mosaic data for {random_points_with_data} random points")
    print(f"- Selected tiles for each location with data")
    print(f"- Total Sentinel-2 Global Mosaic tiles for cities: {cities_with_data}")
    print(f"- Total Sentinel-2 Global Mosaic tiles for random points: {random_points_with_data}")
    
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
    print(f"- Interactive map saved to {args.output_map}")
    print(f"- Unified JSON with {unified_result['properties']['totalAreas']} areas and {unified_result['properties']['totalProducts']} products saved to {unified_file}")
    
    print("\n=== Process Complete ===")
    print(f"You can now use the download_from_json.py script to download the tiles:")
    print(f"python download_from_json.py --json-file {unified_file} --output-dir downloads")

if __name__ == "__main__":
    main() 