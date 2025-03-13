# Sentinel Tile Downloader

A Python script for downloading Sentinel-2 tiles by their ID from the Copernicus Data Space API.

## Prerequisites

- Python 3.6 or higher
- Required Python packages: `requests`

## Installation

1. Clone or download this repository
2. Install the required packages:
   ```
   pip install requests
   ```
3. Make the script executable:
   ```
   chmod +x sentinel_tile_downloader.py
   ```

## Authentication

To download tiles, you need a valid Copernicus Data Space API token. Follow these steps:

1. Register for an account at [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/)
2. Generate an API token from your account
3. Create a token file using the provided template:
   ```
   cp copernicus_dataspace_token_template.json ~/copernicus_dataspace_token.json
   ```
4. Edit the token file and replace the placeholder values with your actual tokens

## Usage

### Basic Usage

```bash
./sentinel_tile_downloader.py --tile-id "TILE_ID" --year-filter "YEAR"
```

### Finding Available Tiles

If you're not sure which tile IDs are available, use the `--list-available` flag:

```bash
./sentinel_tile_downloader.py --tile-id "any" --year-filter "2022" --list-available
```

This will show you examples of available tile IDs for the specified year.

### All Options

```bash
./sentinel_tile_downloader.py --tile-id "TILE_ID" 
                             [--year-filter "YEAR"] 
                             [--output-dir "DIRECTORY"] 
                             [--token-file "PATH_TO_TOKEN_FILE"]
                             [--debug]
                             [--list-available]
```

- `--tile-id`: The Sentinel-2 tile ID to download (required)
- `--year-filter`: Year to filter for (e.g., '2022') (optional)
- `--output-dir`: Directory to save downloaded files (default: "downloads")
- `--token-file`: Path to the Copernicus Data Space token file (optional)
- `--debug`: Enable debug logging
- `--list-available`: List available tiles when the specified tile ID is not found

## Examples

### Download a specific tile for 2022

```bash
./sentinel_tile_downloader.py --tile-id "11SMB" --year-filter "2022"
```

### List available tiles for 2023

```bash
./sentinel_tile_downloader.py --tile-id "any" --year-filter "2023" --list-available
```

### Download with a custom token file location

```bash
./sentinel_tile_downloader.py --tile-id "11SMB" --token-file "/path/to/token.json"
```

## Troubleshooting

If you're having issues with land detection:

1. Try downloading the land polygon data:

```bash
python download_land_polygons.py
```

2. If too many points are being skipped, you can:
   - Increase the number of attempts with `--max-land-attempts 30`
   - Disable land detection with `--ensure-on-land=False`

### Authentication Issues

If you're experiencing 401 or 403 errors:

1. Make sure your token is valid and not expired:
   ```bash
   ./get_token.sh
   ```

2. The tool now includes automatic token refresh, but if you're still having issues:
   - Check that your refresh token is valid in the token file
   - Ensure your Copernicus account has the proper access permissions
   - Try manually generating a new token if automatic refresh fails

3. For persistent authentication problems:
   - Look for error messages about token refresh failures in the console output
   - Verify network connectivity to Copernicus Data Space API endpoints
   - Check if your account has any limitations on API usage or rate limits

## License

This project is open source and available under the MIT License.

# Sentinel City Explorer

This tool queries Sentinel-2 Global Mosaics data for geographically dispersed cities and random points near those cities, then visualizes the results on an interactive map.

## Features

- Select geographically dispersed cities from a CSV file
- Query Sentinel-2 Global Mosaics data for each city
- Generate random points at a specified distance from each city
- Detect whether points are on land or in water
- Select the best (closest) tile for each location
- Create an interactive map showing cities, random points, and their associated tiles
- Multiple base maps including satellite view for better visualization

## Recent Updates

### Token Refresh Mechanism

- Automatic token refresh when 401/403 errors are encountered
- Improved error handling for API requests with retry mechanism
- Token validation before making requests
- Prevents session timeouts during long-running queries

### Point and Tile Selection Improvements

- Enhanced point selection to ensure points are inside the tile boundaries
- Improved random point generation to select points outside the city tile
- Better prioritization of tiles that contain the query point
- Fixed issue where random points were sometimes placed outside their associated tiles

### Query Consolidation

- Created a unified JSON output file that consolidates all queries
- Added descriptive metadata to the unified output
- Combined all areas into a single structure for easier processing
- Improved structure with `totalProducts` and `totalAreas` counters

## Installation

1. Clone this repository
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Download the land polygon data (optional but recommended):

```bash
python download_land_polygons.py
```

## Usage

Basic usage:

```bash
python sentinel_city_explorer.py --cities-csv path/to/worldcities.csv
```

Advanced usage:

```bash
python sentinel_city_explorer.py \
  --cities-csv path/to/worldcities.csv \
  --population-min 100000 \
  --num-cities 200 \
  --random-distance 100 \
  --ensure-on-land \
  --max-land-attempts 20 \
  --download-land-data
```

## Command-line Arguments

- `--cities-csv`: Path to the CSV file containing city data (required)
- `--num-cities`: Number of geographically dispersed cities to select (default: 20)
- `--population-min`: Minimum population threshold for cities (default: 500000)
- `--start-date`: Start date in format YYYY-MM-DD (default: based on year-filter)
- `--end-date`: End date in format YYYY-MM-DD (default: based on year-filter)
- `--max-records`: Maximum number of tiles to return per city (default: 10)
- `--output-dir`: Directory to save output files (default: "results")
- `--output-map`: Path to save the HTML map file (default: "maps/city_mosaics_map.html")
- `--year-filter`: Year to filter for (default: "2022")
- `--random-distance`: Distance in kilometers for random points from cities (default: 100)
- `--ensure-on-land`: Only generate random points on land (default: True)
- `--max-land-attempts`: Maximum attempts to find a random point on land (default: 10)
- `--download-land-data`: Download land polygon data before starting

## Land Detection

The tool can detect whether random points are on land or in water. This is useful for ensuring that random points are only generated on land, which is more likely to have Sentinel-2 data.

To use this feature:

1. Download the land polygon data:

```bash
python download_land_polygons.py
```

2. Run the script with the `--ensure-on-land` flag:

```bash
python sentinel_city_explorer.py --cities-csv path/to/worldcities.csv --ensure-on-land
```

If a random point cannot be found on land after the specified number of attempts (`--max-land-attempts`), the random point will be skipped.

## Output

The script produces:

1. A CSV file with the selected cities
2. JSON files with the raw query results
3. An interactive HTML map showing all the data

### Map Visualization

The map shows:
- Cities as red markers
- Random points on land as green markers
- Random points in water as blue markers
- Sentinel-2 tiles as colored polygons
- Lines connecting cities to their random points
- Multiple base maps including satellite view that can be toggled using the layer control

### Technical Implementation

#### Point Selection Algorithm

The tool uses the following approach to ensure points are properly selected:

1. For city centers:
   - Queries tile information for the exact coordinates
   - Prioritizes products that contain the query point (using geometry boundaries)
   - Selects the 4 quarterly products that are closest to the city center

2. For random points:
   - Generates a random point at the specified distance from the city
   - Ensures the random point is outside the city's tile footprint
   - Checks if the point is on land (if enabled)
   - Prioritizes tiles that contain the random point
   - Connects the random point to the city with a line on the map

#### Token Refresh Mechanism

The tool implements a robust token handling system:

1. Token validation before making requests:
   - Checks if the current token is valid by making a test API call
   - Automatically refreshes expired tokens using the refresh token
   - Falls back to manual token generation if refresh fails

2. Request retry logic:
   - Detects 401/403 authentication errors during API calls
   - Automatically refreshes the token when these errors occur
   - Retries the request with the new token
   - Maximum of 2 retry attempts per request

This approach ensures uninterrupted execution even during long-running queries that might exceed the token's lifetime.

### Tile Metadata

Each Sentinel-2 tile includes the following metadata:

- **Basic Information**:
  - Title
  - Start Date
  - Completion Date
  - Product Type
  - Tile ID

- **Spatial Information**:
  - Footprint (polygon coordinates)
  - Distance from query point

- **City Association**:
  - City Name - Name of the associated city
  - City Coordinates - Latitude and longitude of the associated city
  - Point Type - Whether the tile is associated with a city center or a random point

- **Access Information**:
  - Download URL

This metadata is stored in the JSON files and displayed in the interactive map popups.

## License

This project is open source and available under the MIT License. 