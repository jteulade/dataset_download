#!/usr/bin/env python3
import json
import requests

# Load the token
with open('copernicus_dataspace_token.json', 'r') as f:
    token_data = json.load(f)
    access_token = token_data['access_token']

# Set up the headers
headers = {
    'Authorization': f'Bearer {access_token}'
}

# Define search parameters
year = "2023"
quarters = ["Q1", "Q2", "Q3", "Q4"]
# Example coordinates for Paris, France
lat = 48.8566
lon = 2.3522

# Create a bounding box around the point (approximately 10km)
# 0.1 degrees is roughly 11km at the equator
box_size = 0.1
bbox = f"{lon-box_size},{lat-box_size},{lon+box_size},{lat+box_size}"

print(f"Checking for Sentinel-2 mosaic products around coordinates ({lat}, {lon}) for {year}:")
print("-" * 70)

# Check each quarter
for quarter in quarters:
    # Make the OData request with coordinates
    url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
    
    # Create a spatial filter using the bounding box
    spatial_filter = f"OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(({lon-box_size} {lat-box_size}, {lon-box_size} {lat+box_size}, {lon+box_size} {lat+box_size}, {lon+box_size} {lat-box_size}, {lon-box_size} {lat-box_size}))')"
    
    params = {
        "$filter": f"({spatial_filter}) and Collection/Name eq 'GLOBAL-MOSAICS' and contains(Name,'{year}_{quarter}')"
    }

    response = requests.get(url, headers=headers, params=params)
    
    print(f"\n{year} {quarter}:")
    print(f"Status code: {response.status_code}")
    
    # Print the complete response
    if response.status_code == 200:
        result = response.json()
        print("\nComplete JSON response:")
        print(json.dumps(result, indent=2))
        
        product_count = len(result.get('value', []))
        print(f"\nSummary: Found {product_count} product(s)")
    else:
        print(f"❌ Error: {response.text}")

print("\nSummary of curl commands to check each quarter:")
print("-" * 70)

for quarter in quarters:
    spatial_filter = f"OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(({lon-box_size} {lat-box_size}, {lon-box_size} {lat+box_size}, {lon+box_size} {lat+box_size}, {lon+box_size} {lat-box_size}, {lon-box_size} {lat-box_size}))')"
    print(f"\n# Check {year} {quarter} around coordinates ({lat}, {lon})")
    print(f'''curl -X GET "https://catalogue.dataspace.copernicus.eu/odata/v1/Products?%24filter=({spatial_filter}) and Collection/Name eq 'GLOBAL-MOSAICS' and contains(Name,'{year}_{quarter}')" \\
-H "Authorization: Bearer $ACCESS_TOKEN" | python -m json.tool''') 