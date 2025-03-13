#!/usr/bin/env python3
"""
Combine Sentinel Features

This script combines all Sentinel-2 features from multiple JSON files in the results directory
into a single comprehensive JSON file.
"""

import os
import json
import glob
import argparse
from datetime import datetime

def combine_sentinel_features(input_dir="results", output_file=None, pattern="S2_GlobalMosaics_*_raw.json"):
    """
    Combine all Sentinel-2 features from multiple JSON files into a single comprehensive JSON file.
    
    Args:
        input_dir (str): Directory containing the JSON files
        output_file (str): Path to save the combined JSON file
        pattern (str): Glob pattern to match JSON files
        
    Returns:
        dict: Combined JSON data with all features
    """
    # Create input directory if it doesn't exist
    if not os.path.exists(input_dir):
        os.makedirs(input_dir)
        print(f"Created directory: {input_dir}")
        return None
    
    # Find all JSON files matching the pattern
    json_files = glob.glob(os.path.join(input_dir, pattern))
    print(f"Found {len(json_files)} JSON files matching pattern '{pattern}'")
    
    if not json_files:
        print(f"No JSON files found in {input_dir} matching pattern '{pattern}'")
        return None
    
    # Initialize combined data structure
    combined_data = {
        "type": "FeatureCollection",
        "features": [],
        "properties": {
            "totalResults": 0,
            "exactCount": True,
            "source_files": [],
            "combined_timestamp": datetime.now().isoformat(),
            "description": "Combined Sentinel-2 features from multiple queries"
        }
    }
    
    # Process each JSON file
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                
            # Check if the file has features
            if 'features' in data and isinstance(data['features'], list):
                # Add source file information
                combined_data["properties"]["source_files"].append({
                    "file": os.path.basename(json_file),
                    "feature_count": len(data["features"])
                })
                
                # Add features to combined data
                combined_data["features"].extend(data["features"])
                
                # Update total results count
                combined_data["properties"]["totalResults"] += len(data["features"])
                
                print(f"Added {len(data['features'])} features from {os.path.basename(json_file)}")
            else:
                print(f"Warning: No features found in {os.path.basename(json_file)}")
                
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
    
    # Set default output file if not provided
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(input_dir, f"S2_GlobalMosaics_combined_{timestamp}.json")
    
    # Save combined data to file
    with open(output_file, 'w') as f:
        json.dump(combined_data, f, indent=2)
    
    print(f"\nCombined {combined_data['properties']['totalResults']} features from {len(combined_data['properties']['source_files'])} files")
    print(f"Combined JSON saved to {output_file}")
    
    return combined_data

def main():
    parser = argparse.ArgumentParser(description="Combine Sentinel-2 features from multiple JSON files into a single comprehensive JSON file")
    parser.add_argument("--input-dir", type=str, default="results",
                        help="Directory containing the JSON files (default: results)")
    parser.add_argument("--output-file", type=str,
                        help="Path to save the combined JSON file (default: results/S2_GlobalMosaics_combined_TIMESTAMP.json)")
    parser.add_argument("--pattern", type=str, default="S2_GlobalMosaics_*_raw.json",
                        help="Glob pattern to match JSON files (default: S2_GlobalMosaics_*_raw.json)")
    
    args = parser.parse_args()
    
    # Combine features
    combine_sentinel_features(
        input_dir=args.input_dir,
        output_file=args.output_file,
        pattern=args.pattern
    )

if __name__ == "__main__":
    main() 