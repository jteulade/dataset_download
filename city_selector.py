"""
City Selector Module

This module provides functions for loading city data and selecting geographically
dispersed cities using a greedy algorithm.
"""

import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import haversine_distances

def load_city_data(csv_file, population_min=0):
    """
    Load city data from a CSV file and filter by minimum population.
    
    Args:
        csv_file (str): Path to the CSV file containing city data
        population_min (int): Minimum population threshold
        
    Returns:
        pandas.DataFrame: DataFrame containing filtered city data
    """
    print(f"Loading city data from {csv_file}")
    cities_df = pd.read_csv(csv_file)
    
    # Filter by population if specified
    if population_min > 0:
        print(f"Filtering cities with population >= {population_min}")
        cities_df = cities_df[cities_df['population'] >= population_min]
    
    print(f"Loaded {len(cities_df)} cities")
    return cities_df

def select_dispersed_cities(cities_df, n_cities=200):
    """
    Select geographically dispersed cities using a greedy algorithm.
    
    Args:
        cities_df (pandas.DataFrame): DataFrame containing city data
        n_cities (int): Number of cities to select
        
    Returns:
        pandas.DataFrame: DataFrame containing selected cities
    """
    print(f"Selecting {n_cities} geographically dispersed cities")
    
    # Ensure we have latitude and longitude columns
    if 'lat' not in cities_df.columns or 'lng' not in cities_df.columns:
        raise ValueError("City data must contain 'lat' and 'lng' columns")
    
    # Filter out cities with missing coordinates
    valid_cities = cities_df.dropna(subset=['lat', 'lng']).copy()
    print(f"Found {len(valid_cities)} cities with valid coordinates")
    
    if len(valid_cities) < n_cities:
        print(f"Warning: Only {len(valid_cities)} cities available, less than requested {n_cities}")
        n_cities = len(valid_cities)
    
    # Convert coordinates to radians for haversine distance calculation
    coords_rad = np.radians(valid_cities[['lat', 'lng']].values)
    
    # Start with the most populous city
    valid_cities = valid_cities.sort_values('population', ascending=False)
    selected_indices = [0]  # Start with the most populous city
    
    # Greedy algorithm to select dispersed cities
    for i in range(1, n_cities):
        selected_coords = coords_rad[selected_indices]
        min_distances = []
        
        # Calculate minimum distance from each unselected city to any selected city
        for j in range(len(valid_cities)):
            if j in selected_indices:
                min_distances.append(-1)  # Already selected
                continue
                
            # Calculate haversine distances to all selected cities
            city_coord = coords_rad[j].reshape(1, -1)
            distances = haversine_distances(city_coord, selected_coords).flatten()
            
            # Convert from radians to kilometers (Earth radius ≈ 6371 km)
            distances_km = 6371.0 * distances
            
            # Find minimum distance to any selected city
            min_distances.append(np.min(distances_km))
        
        # Select the city with the maximum minimum distance
        next_city_idx = np.argmax(min_distances)
        selected_indices.append(next_city_idx)
    
    # Return the selected cities
    return valid_cities.iloc[selected_indices].reset_index(drop=True)

if __name__ == "__main__":
    # Example usage
    import argparse
    
    parser = argparse.ArgumentParser(description="Select geographically dispersed cities from a CSV file")
    parser.add_argument("--cities-csv", type=str, required=True,
                        help="Path to the CSV file containing city data (e.g., worldcities.csv)")
    parser.add_argument("--num-cities", type=int, default=20,
                        help="Number of geographically dispersed cities to select")
    parser.add_argument("--population-min", type=int, default=500000,
                        help="Minimum population threshold for cities")
    parser.add_argument("--output-csv", type=str, default="results/selected_cities.csv",
                        help="Path to save the selected cities CSV file")
    
    args = parser.parse_args()
    
    # Load city data
    cities_df = load_city_data(args.cities_csv, args.population_min)
    
    # Select dispersed cities
    selected_cities = select_dispersed_cities(cities_df, args.num_cities)
    print(f"Selected {len(selected_cities)} dispersed cities")
    
    # Save selected cities to CSV
    import os
    os.makedirs(os.path.dirname(args.output_csv), exist_ok=True)
    selected_cities.to_csv(args.output_csv, index=False)
    print(f"Selected cities saved to {args.output_csv}") 