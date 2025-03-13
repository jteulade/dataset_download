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
from city_selector import load_city_data, select_dispersed_cities
from sentinel_query import query_sentinel2_by_coordinates, get_random_point_at_distance, is_point_on_land
from map_visualizer import create_mosaic_map

def main():
    parser = argparse.ArgumentParser(description="Query Sentinel-2 Global Mosaics data for dispersed cities and visualize the results")
    parser.add_argument("--cities-csv", type=str, required=True,
                        help="Path to the CSV file containing city data (e.g., worldcities.csv)")
    parser.add_argument("--num-cities", type=int, default=20,
                        help="Number of geographically dispersed cities to select")
    parser.add_argument("--population-min", type=int, default=500000,
                        help="Minimum population threshold for cities")
    parser.add_argument("--start-date", type=str,
                        help="Start date in format YYYY-MM-DD (default: based on year-filter)")
    parser.add_argument("--end-date", type=str,
                        help="End date in format YYYY-MM-DD (default: based on year-filter)")
    parser.add_argument("--max-records", type=int, default=10,
                        help="Maximum number of tiles to return per city (default: 10)")
    parser.add_argument("--output-dir", type=str, default="results",
                        help="Directory to save output files")
    parser.add_argument("--output-map", type=str, default="maps/city_mosaics_map.html",
                        help="Path to save the HTML map file")
    parser.add_argument("--year-filter", type=str, default="2022",
                        help="Year to filter for (e.g., '2022')")
    parser.add_argument("--random-distance", type=int, default=300,
                        help="Distance in kilometers for random points from cities (default: 100)")
    parser.add_argument("--ensure-on-land", action="store_true", default=True,
                        help="Only generate random points on land. If no land point is found after max-land-attempts, the random point will be skipped (default: True)")
    parser.add_argument("--max-land-attempts", type=int, default=10,
                        help="Maximum attempts to find a random point on land (default: 10)")
    parser.add_argument("--download-land-data", action="store_true", default=False,
                        help="Download land polygon data before starting")
    
    args = parser.parse_args()
    
    # Download land polygon data if requested
    if args.download_land_data:
        try:
            from download_land_polygons import download_natural_earth_land
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
    selected_cities = select_dispersed_cities(cities_df, args.num_cities)
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
    
    # Create a structure to collect the best features for the combined JSON
    best_features = []
    query_metadata = []
    
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
            start_date=args.start_date,
            end_date=args.end_date,
            max_records=args.max_records,  # Still query multiple tiles to find the best one
            output_dir=args.output_dir,
            year_filter=args.year_filter,
            city_name=city_name,
            city_lat=lat,
            city_lon=lon,
            is_neighbor=False
        )
        
        if result:
            # Select only the best tile (closest to the city center)
            if result['count'] > 0 and 'json_data' in result and 'features' in result['json_data']:
                # The features are already sorted by distance in query_sentinel2_by_coordinates
                # So we just take the first one (closest)
                best_feature = result['features'][0]
                
                # Find the corresponding original feature in the json_data
                best_original_feature = None
                for feature in result['json_data']['features']:
                    # Try to match the feature based on title or other unique identifier
                    if 'properties' in feature and 'title' in feature['properties'] and \
                       'title' in best_feature and feature['properties']['title'] == best_feature['title']:
                        best_original_feature = feature
                        break
                
                if best_original_feature:
                    # Add metadata to the best feature
                    if 'properties' not in best_original_feature:
                        best_original_feature['properties'] = {}
                    
                    # Add city metadata to the feature properties
                    best_original_feature['properties']['city_name'] = city_name
                    best_original_feature['properties']['city_lat'] = lat
                    best_original_feature['properties']['city_lon'] = lon
                    best_original_feature['properties']['is_neighbor'] = False
                    best_original_feature['properties']['query_point_lat'] = lat
                    best_original_feature['properties']['query_point_lon'] = lon
                    best_original_feature['properties']['distance_km'] = best_feature['distance_km']
                    best_original_feature['properties']['is_best_tile'] = True
                    
                    # Add the best feature to the collection
                    best_features.append(best_original_feature)
                    
                    # Add query metadata
                    query_metadata.append({
                        'city_name': city_name,
                        'query_point': {'lat': lat, 'lon': lon},
                        'is_neighbor': False,
                        'best_feature_title': best_feature['title'],
                        'best_feature_distance_km': best_feature['distance_km'],
                        'timestamp': datetime.now().isoformat()
                    })
                
                result['features'] = [best_feature]  # Keep only the best feature
                result['count'] = 1  # Update the count
                print(f"Selected the best tile for {city_name}: {best_feature['title']}")
                print(f"Distance from city center: {best_feature['distance_km']:.2f} km")
            
            # Don't overwrite the city_name if it's already set in the result
            if not result.get('city_name'):
                result['city_name'] = city_name
                
            cities_results.append(result)
        
        # Generate a random point at the specified distance and query for it
        print(f"\nGenerating random point {args.random_distance} km away from {city_name}...")
        
        random_point_result = get_random_point_at_distance(
            lat, lon, args.random_distance, 
            ensure_on_land=args.ensure_on_land,
            max_attempts=args.max_land_attempts
        )
        
        # Skip this random point if we couldn't find a point on land and ensure_on_land is True
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
        
        # Query Sentinel-2 data for the random point
        random_result = query_sentinel2_by_coordinates(
            lat=random_lat,
            lon=random_lon,
            start_date=args.start_date,
            end_date=args.end_date,
            max_records=args.max_records,  # Query multiple tiles to find the best one
            output_dir=args.output_dir,
            year_filter=args.year_filter,
            city_name=city_name,
            city_lat=lat,
            city_lon=lon,
            is_neighbor=True
        )
        
        # Create a result object for the random point even if no data is found
        if random_result:
            # Select only the best tile (closest to the random point)
            if random_result['count'] > 0 and 'json_data' in random_result and 'features' in random_result['json_data']:
                # The features are already sorted by distance in query_sentinel2_by_coordinates
                # So we just take the first one (closest)
                best_feature = random_result['features'][0]
                
                # Find the corresponding original feature in the json_data
                best_original_feature = None
                for feature in random_result['json_data']['features']:
                    # Try to match the feature based on title or other unique identifier
                    if 'properties' in feature and 'title' in feature['properties'] and \
                       'title' in best_feature and feature['properties']['title'] == best_feature['title']:
                        best_original_feature = feature
                        break
                
                if best_original_feature:
                    # Add metadata to the best feature
                    if 'properties' not in best_original_feature:
                        best_original_feature['properties'] = {}
                    
                    # Add city and random point metadata to the feature properties
                    best_original_feature['properties']['city_name'] = city_name
                    best_original_feature['properties']['city_lat'] = lat
                    best_original_feature['properties']['city_lon'] = lon
                    best_original_feature['properties']['is_neighbor'] = True
                    best_original_feature['properties']['query_point_lat'] = random_lat
                    best_original_feature['properties']['query_point_lon'] = random_lon
                    best_original_feature['properties']['is_on_land'] = is_on_land
                    best_original_feature['properties']['land_status'] = land_status
                    best_original_feature['properties']['distance_from_city'] = args.random_distance
                    best_original_feature['properties']['distance_km'] = best_feature['distance_km']
                    best_original_feature['properties']['is_best_tile'] = True
                    
                    # Add the best feature to the collection
                    best_features.append(best_original_feature)
                    
                    # Add query metadata
                    query_metadata.append({
                        'city_name': city_name,
                        'query_point': {'lat': random_lat, 'lon': random_lon},
                        'is_neighbor': True,
                        'is_on_land': is_on_land,
                        'land_status': land_status,
                        'distance_from_city': args.random_distance,
                        'best_feature_title': best_feature['title'],
                        'best_feature_distance_km': best_feature['distance_km'],
                        'timestamp': datetime.now().isoformat()
                    })
            
            # Add land/water status to the result
            random_result['is_on_land'] = is_on_land
            random_result['land_status'] = land_status
            
            # Set the city name with land/water indicator, but preserve the original city metadata
            land_indicator = "Land" if is_on_land else "Water"
            random_result['display_name'] = f"{city_name} (Random Point - {land_indicator})"
            
            # Don't overwrite the city metadata if it's already set
            if not random_result.get('city_name'):
                random_result['city_name'] = city_name
            if not random_result.get('city_lat'):
                random_result['city_lat'] = lat
            if not random_result.get('city_lon'):
                random_result['city_lon'] = lon
            if not 'is_neighbor' in random_result:
                random_result['is_neighbor'] = True
                
            random_result['original_city_lat'] = lat
            random_result['original_city_lon'] = lon
            random_result['distance_from_city'] = args.random_distance
            
            # Print details of the random point's tile
            print(f"Found {random_result['count']} Sentinel-2 tiles for the random point")
            
            if random_result['count'] > 0:
                # Select only the best tile (closest to the random point)
                best_feature = random_result['features'][0]
                random_result['features'] = [best_feature]  # Keep only the best feature
                random_result['count'] = 1  # Update the count
                
                print("\nRandom Point Best Tile Details:")
                print(f"  Title: {best_feature['title']}")
                print(f"  Start Date: {best_feature['start_date']}")
                print(f"  Product Type: {best_feature['product_type']}")
                if best_feature.get('tile_id'):
                    print(f"  Tile ID: {best_feature['tile_id']}")
                print(f"  Distance from random point: {best_feature['distance_km']:.2f} km")
                if best_feature.get('download_url'):
                    print(f"  Download URL: {best_feature['download_url']}")
                
                # Only add to results if we found tiles
                random_points_results.append(random_result)
            else:
                print(f"No Sentinel-2 tiles found for the random point near {city_name}")
                
                # Add the random point to the map even if no tiles were found
                land_indicator = "Land" if is_on_land else "Water"
                empty_random_result = {
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
                random_points_results.append(empty_random_result)
        else:
            print(f"Query failed for the random point near {city_name}")
            
            # Add the random point to the map even if the query failed
            land_indicator = "Land" if is_on_land else "Water"
            failed_random_result = {
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
            random_points_results.append(failed_random_result)
    
    # Save the combined JSON file with only the best features
    if best_features:
        # Create a combined data structure
        combined_data = {
            "type": "FeatureCollection",
            "features": best_features,
            "properties": {
                "totalResults": len(best_features),
                "exactCount": True,
                "queries": query_metadata,
                "combined_timestamp": datetime.now().isoformat(),
                "description": "Combined Sentinel-2 best features from all queries"
            }
        }
        
        # Create a filename with timestamp to avoid overwriting
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        combined_file = os.path.join(args.output_dir, f"S2_GlobalMosaics_{args.year_filter}_best_tiles_{timestamp}.json")
        
        # Save the combined data
        with open(combined_file, 'w') as f:
            json.dump(combined_data, f, indent=2)
        
        print(f"\nSaved combined JSON with {len(best_features)} best features to {combined_file}")
    
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
    print(f"- Selected the best (closest) tile for each location with data")
    print(f"- Total Sentinel-2 Global Mosaic tiles for cities: {sum(r['count'] for r in cities_results)}")
    print(f"- Total Sentinel-2 Global Mosaic tiles for random points: {sum(r['count'] for r in random_points_results)}")
    
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
    if best_features:
        print(f"- Combined JSON with {len(best_features)} best features saved to {combined_file}")

if __name__ == "__main__":
    main() 