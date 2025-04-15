#!/usr/bin/env python3
"""
Quarterly Products Visualizer

This script creates an interactive map to visualize Sentinel-2 Global Mosaics
quarterly products and their footprints.
"""

import argparse
import json
import logging as log
import os
from datetime import datetime
from pathlib import Path
import sys

log.basicConfig(level=log.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add the project root directory to the Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from src.map_visualizer import create_mosaic_map

def process_quarterly_products(json_file):
    """
    Process the JSON file containing quarterly products and convert it to the format
    expected by the map visualization module.
    
    Args:
        json_file (str): Path to the JSON file containing quarterly products
        
    Returns:
        list: List of results in the format expected by create_mosaic_map
    """
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    results = []
    
    for area in data.get('areas', []):
        # Create a result entry for this area
        result = {
            'count': len(area.get('quarterlyProducts', [])),
            'lat': area.get('queryPointLat', area.get('cityLat')),
            'lon': area.get('queryPointLon', area.get('cityLon')),
            'city_name': area.get('cityName', 'Unknown'),
            'is_neighbor': area.get('isNeighbor', False),
            'features': []
        }
        
        # Process each quarterly product
        for product in area.get('quarterlyProducts', []):
            feature = {
                'title': product.get('Name', 'Unknown'),
                'product_type': 'S2 Global Mosaic',
                'quarter': product.get('quarter', 'Unknown'),
                'start_date': product.get('ContentDate', {}).get('Start', ''),
                'end_date': product.get('ContentDate', {}).get('End', ''),
                'original_feature': product  # Store the original product data
            }
            
            # Add the feature to the result
            result['features'].append(feature)
        
        # Add the result to the listlog.info(f"Processing quarterly products from {args.input_json}")
        results.append(result)
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Create an interactive map to visualize Sentinel-2 Global Mosaics quarterly products")
    parser.add_argument("--input-json", type=str, required=True,
                        help="Path to the JSON file containing quarterly products")
    parser.add_argument("--output-map", type=str, default="maps/quarterly_products_map.html",
                        help="Path to save the HTML map file")
    
    args = parser.parse_args()
    
    # Process the quarterly products
    log.info(f"Processing quarterly products from {args.input_json}")
    results = process_quarterly_products(args.input_json)
    
    # Create the interactive map
    log.info(f"Creating interactive map with {len(results)} areas")
    create_mosaic_map(results, args.output_map)
    
    log.info(f"\nMap saved to {args.output_map}")

if __name__ == "__main__":
    main() 