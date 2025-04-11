#!/usr/bin/env python3
"""
Sentinel Tile Downloader

This script downloads Sentinel-2 tiles based on metadata from a JSON file.
It handles token refresh for the Copernicus Data Space API.
"""

import os
import json
import argparse
import requests
import logging
import traceback
from datetime import datetime
from pathlib import Path
import re
from tqdm import tqdm
from src.token_manager import ensure_valid_token, get_access_token

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SentinelDownloader:
    """Class to handle Sentinel-2 tile downloads with token management."""
    
    CATALOGUE_URL = "https://catalogue.dataspace.copernicus.eu/resto/api/collections/GLOBAL-MOSAICS/search.json"
    ODATA_URL = "https://zipper.dataspace.copernicus.eu/odata/v1"
    
    def __init__(self, disable_progress_bars=False, chunk_size_mb=1):
        """Initialize the downloader with token management."""
        self.disable_progress_bars = disable_progress_bars
        self.chunk_size = chunk_size_mb * 1024 * 1024  # Convert MB to bytes
        
        # Initial token check
        self.access_token = get_access_token()
        if self.access_token:
            logger.info("Access token loaded successfully")
        else:
            logger.warning("No valid access token available")
            logger.info("You can still search for tiles, but downloading will require authentication")
    
    def is_token_valid(self):
        """Check if the current access token is valid."""
        # Refresh token if needed using token_manager
        self.access_token = get_access_token()
        return self.access_token is not None
    
    def refresh_access_token(self):
        """Refresh the access token using the refresh token."""
        logger.info("Refreshing access token...")
        # Always refresh the token using token_manager
        self.access_token = get_access_token()
        if self.access_token:
            logger.info("Access token refreshed successfully")
            return True
        else:
            logger.warning("Failed to refresh access token")
            return False
    
    def extract_tile_info_from_feature(self, feature):
        """
        Extract tile information from a feature in the JSON file.
        
        Args:
            feature (dict): The feature containing the tile information
            
        Returns:
            dict: The processed feature with tile information
        """
        # Check if this is the old JSON format (with properties key)
        if 'properties' in feature:
            props = feature['properties']
            title = props.get('title', 'Unknown')
            
            # Extract tile ID from title
            tile_id = None
            parts = title.split('_')
            if len(parts) >= 5:
                tile_id = parts[4]  # Extract the tile ID part
            
            # Extract product ID for OData API
            product_id = None
            download_url = props.get('services', {}).get('download', {}).get('url')
            if download_url:
                match = re.search(r'/download/([a-f0-9-]+)', download_url)
                if match:
                    product_id = match.group(1)
            
            # Create a processed feature
            processed_feature = {
                'title': title,
                'platform': props.get('platform', 'Unknown'),
                'start_date': props.get('startDate', 'Unknown'),
                'completion_date': props.get('completionDate', 'Unknown'),
                'product_type': props.get('productType', 'Unknown'),
                'tile_id': tile_id,
                'download_url': download_url,
                'product_id': product_id,
                'city_name': props.get('city_name', 'Unknown'),
                'distance_km': props.get('distance_km', 0),
                'is_best_tile': props.get('is_best_tile', False),
                'original_feature': feature
            }
            
            return processed_feature
        
        # New JSON format (quarterlyProducts)
        else:
            # Extract properties from the new format
            title = feature.get('Name', 'Unknown')
            
            # Extract tile ID from title
            tile_id = None
            parts = title.split('_')
            if len(parts) >= 5:
                tile_id = parts[4]  # Extract the tile ID part
            
            # Extract product ID directly from the ID field
            product_id = feature.get('Id')
            
            # Get download URL from restoProperties.services if available
            download_url = None
            resto_props = feature.get('restoProperties', {})
            if 'services' in resto_props and 'download' in resto_props['services']:
                download_url = resto_props['services']['download'].get('url')
            
            # Create a processed feature
            processed_feature = {
                'title': title,
                'platform': resto_props.get('platform', 'Unknown'),
                'start_date': resto_props.get('startDate', 'Unknown'),
                'completion_date': resto_props.get('completionDate', 'Unknown'),
                'product_type': resto_props.get('productType', 'Unknown'),
                'tile_id': tile_id,
                'download_url': download_url,
                'product_id': product_id,
                'city_name': None,  # Will be filled from parent area
                'distance_km': 0,   # Will be filled from parent area if available
                'is_best_tile': True,  # Assuming all tiles in the new format are "best" tiles
                'original_feature': feature
            }
            
            return processed_feature
    
    def search_tile_by_id(self, tile_id, year_filter=None):
        """
        Search for a Sentinel-2 tile by its ID.
        
        Args:
            tile_id (str): The tile ID to search for
            year_filter (str, optional): Year to filter for (e.g., '2022')
            
        Returns:
            dict: The feature containing the tile information, or None if not found
        """
        # Set default dates based on year filter
        if year_filter:
            start_date = f"{year_filter}-01-01T00:00:00Z"
            end_date = f"{year_filter}-12-31T23:59:59Z"
        else:
            # Default to the current year
            current_year = datetime.now().year
            start_date = f"{current_year}-01-01T00:00:00Z"
            end_date = datetime.now().strftime("%Y-%m-%dT23:59:59Z")
        
        # Set up parameters for the search
        # Instead of using 'q' parameter which might cause issues, 
        # we'll search for all tiles and filter them in code
        params = {
            "startDate": start_date,
            "completionDate": end_date,
            "maxRecords": "100",  # Request a large number to increase chances of finding the tile
            "platform": "SENTINEL-2"
            # Removed the 'q' parameter that was causing the 400 error
        }
        
        logger.info(f"Searching for Sentinel-2 tile with ID: {tile_id}")
        
        # Make the request
        try:
            logger.info(f"Sending request to: {self.CATALOGUE_URL}")
            logger.info(f"With parameters: {params}")
            
            response = requests.get(self.CATALOGUE_URL, params=params)
            
            # Log the full URL for debugging
            logger.info(f"Full request URL: {response.url}")
            
            # Check response status
            if response.status_code != 200:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return None
            
            # Parse the JSON response
            json_data = response.json()
            
            # Check if we have features
            if 'features' not in json_data or len(json_data['features']) == 0:
                logger.warning(f"No results found in the search response")
                return None
            
            logger.info(f"Found {len(json_data['features'])} features in the search response")
            
            # Look for the exact tile ID in the features
            matching_features = []
            for feature in json_data['features']:
                props = feature['properties']
                title = props.get('title', '')
                
                # Check if the tile ID is in the title
                if tile_id in title:
                    logger.info(f"Found matching tile: {title}")
                    
                    # Extract download URL
                    download_url = props.get('services', {}).get('download', {}).get('url')
                    
                    if not download_url:
                        logger.warning(f"No download URL found for tile: {title}")
                        continue
                    
                    # Extract product ID for OData API
                    product_id = None
                    if download_url:
                        import re
                        match = re.search(r'/download/([a-f0-9-]+)', download_url)
                        if match:
                            product_id = match.group(1)
                    
                    # Create a processed feature
                    processed_feature = {
                        'title': title,
                        'platform': props.get('platform', 'Unknown'),
                        'start_date': props.get('startDate', 'Unknown'),
                        'completion_date': props.get('completionDate', 'Unknown'),
                        'product_type': props.get('productType', 'Unknown'),
                        'tile_id': tile_id,
                        'download_url': download_url,
                        'product_id': product_id,
                        'original_feature': feature
                    }
                    
                    matching_features.append(processed_feature)
            
            if matching_features:
                # Return the first matching feature
                logger.info(f"Found {len(matching_features)} tiles matching ID: {tile_id}")
                return matching_features[0]
            else:
                logger.warning(f"Tile ID {tile_id} not found in search results")
                return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error searching for tile: {e}")
            return None
    
    def download_tile(self, feature, output_dir="downloads"):
        """
        Download a Sentinel-2 tile.
        
        Args:
            feature (dict): The feature containing the tile information
            output_dir (str): Directory to save downloaded file
            
        Returns:
            str: Path to the downloaded file, or None if download failed
        """
        if not feature:
            logger.error("Invalid feature")
            return None
        
        # Get the title - it could be directly in the feature or in properties
        title = feature.get('title')
        if not title and 'properties' in feature:
            title = feature['properties'].get('title')
        
        if not title:
            logger.error("No title found in feature")
            return None
            
        logger.info(f"Processing tile: {title}")
        
        # Get year and tile ID for directory structure - they could be in feature or properties
        year = feature.get('year')
        tile_id = feature.get('tile_id')
        
        # If we didn't find them directly, check in properties
        if 'properties' in feature:
            properties = feature['properties']
            if not year:
                year = properties.get('year')
            if not tile_id:
                tile_id = properties.get('tile_id')
        
        # Extract year from start_date as fallback
        start_date = None
        if 'properties' in feature:
            start_date = feature['properties'].get('startDate')
        elif 'start_date' in feature:
            start_date = feature.get('start_date')
            
        if not year and start_date and isinstance(start_date, str):
            year_match = re.match(r'^(\d{4})', start_date)
            if year_match:
                year = year_match.group(1)
                
        # If we still don't have a year, try to extract it from the title
        if not year and title:
            # Try to find year in title, like "Sentinel-2_mosaic_2023_Q1_54SUE_0_0"
            parts = title.split('_')
            if len(parts) >= 4:
                potential_year = parts[2]
                if potential_year.isdigit() and len(potential_year) == 4:
                    year = potential_year
        
        # Extract tile ID from title if not available
        if not tile_id and title:
            parts = title.split('_')
            if len(parts) >= 5:
                tile_id = parts[4]  # Extract the tile ID part (e.g., "54SUE")
        
        # Create hierarchical directory structure if year and tile_id are available
        if year and tile_id:
            nested_dir = os.path.join(output_dir, year, tile_id)
            logger.info(f"Using hierarchical directory structure: {nested_dir}")
        else:
            # Fallback to output_dir if we can't determine year or tile_id
            nested_dir = output_dir
            logger.warning("Could not determine hierarchical structure, using base output directory")
            if not year:
                logger.warning(f"Could not extract year from title or start_date: {title}, {start_date}")
            if not tile_id:
                logger.warning(f"No tile ID available for: {title}")
        
        # Create output directory if it doesn't exist
        os.makedirs(nested_dir, exist_ok=True)
        
        # Define output file path
        output_file = os.path.join(nested_dir, f"{title}.zip")
        
        logger.info(f"Downloading tile: {title}")
        logger.info(f"Output file: {output_file}")
        
        # Check if the token is valid
        if not self.is_token_valid():
            logger.info("Token is invalid, attempting to refresh")
            # Try to refresh the token before downloading
            try:
                new_token_data = self.refresh_access_token()
                if new_token_data:
                    logger.info("Token refreshed successfully")
                else:
                    logger.warning("Token refresh failed, download may fail")
            except Exception as e:
                logger.warning(f"Error refreshing token: {e}")
        else:
            logger.info("Token is valid, proceeding with download")
        
        # Get download URL and product ID
        download_url = None
        product_id = None
        
        # Extract from direct properties 
        if 'product_id' in feature:
            product_id = feature['product_id']
        if 'download_url' in feature:
            download_url = feature['download_url']
            
        # Extract from nested properties
        if 'properties' in feature:
            properties = feature['properties']
            if not product_id:
                product_id = properties.get('product_id')
            if not download_url and 'services' in properties and 'download' in properties['services']:
                download_url = properties['services']['download'].get('url')
        
        # Extract product ID from the download URL if available
        if not product_id and download_url:
            match = re.search(r'/download/([a-f0-9-]+)', download_url)
            if match:
                product_id = match.group(1)
                
        # Extract product ID from the title as a last resort
        if not product_id and title:
            # Try to find a UUID in the title
            uuid_pattern = r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'
            match = re.search(uuid_pattern, title)
            if match:
                product_id = match.group(0)
                
        # Generate download URL from product ID if needed
        if product_id and not download_url:
            download_url = f"{self.ODATA_URL}/Products({product_id})/$value"
            
        # Try different download methods in order of preference
        
        # 1. Try OData API if we have a product ID
        if product_id:
            odata_url = f"{self.ODATA_URL}/Products({product_id})/$value"
            logger.info(f"Trying OData API download URL: {odata_url}")
            
            if self._try_download(odata_url, output_file):
                return output_file
            
            logger.warning("OData API download failed, trying direct download URL if available")
        
        # 2. Try direct download URL if available
        if download_url:
            logger.info(f"Trying direct download URL: {download_url}")
            
            if self._try_download(download_url, output_file):
                return output_file
        else:
            logger.error("No download URL available for this tile")
            
        # If we get here, all download methods failed or were not available
        logger.error("All download methods failed or no valid download method available")
        return None
    
    def _try_download(self, url, output_file):
        """
        Try to download a file with the current access token.
        
        Args:
            url (str): URL to download from
            output_file (str): Path to save the downloaded file
            
        Returns:
            bool: True if download was successful, False otherwise
        """
        # First check if URL is valid
        if not url:
            logger.error("No download URL provided")
            return False
            
        try:
            headers = {}
            if self.access_token:
                # Try with Bearer authentication
                headers['Authorization'] = f"Bearer {self.access_token}"
            
            # Log the headers we're using (without the full token for security)
            auth_header = headers.get('Authorization', 'None')
            if auth_header != 'None':
                auth_header = auth_header[:15] + '...' + auth_header[-5:]
            logger.info(f"Using Authorization header: {auth_header}")
            
            # Check if the URL is from the catalogue domain and might need redirection
            if 'catalogue.dataspace.copernicus.eu' in url:
                logger.info("URL is from catalogue domain, checking for redirection")
                
                # Use a GET request with stream=True to avoid downloading the whole file
                # but still follow redirects to get the final URL
                check_response = requests.get(url, headers=headers, stream=True, allow_redirects=True)
                
                # Close the connection to avoid downloading the file
                check_response.close()
                
                # Check if we were redirected
                if check_response.history:
                    redirect_url = check_response.url
                    logger.info(f"Request was redirected to: {redirect_url}")
                    url = redirect_url  # Use the redirected URL for the actual download
                
                # Check for authentication issues
                if check_response.status_code == 401:
                    logger.warning("Unauthorized: Token may be expired or insufficient permissions")
                    return False
            
            # Stream the download to handle large files
            logger.info(f"Starting download from: {url}")
            with requests.get(url, headers=headers, stream=True, allow_redirects=True) as response:
                if response.status_code == 401:
                    logger.warning("Unauthorized: Token may be expired or insufficient permissions")
                    # Log response headers for debugging
                    logger.info(f"Response headers: {dict(response.headers)}")
                    return False
                elif response.status_code == 405:  # Method Not Allowed
                    logger.warning("Method Not Allowed (405): The server doesn't allow this request method")
                    logger.info(f"Allowed methods: {response.headers.get('allow', 'Unknown')}")
                    
                    # Try alternative URL if this is a download.dataspace.copernicus.eu URL
                    if 'download.dataspace.copernicus.eu' in url:
                        # Extract the ID from the URL
                        import re
                        match = re.search(r'/download/([a-f0-9-]+)', url)
                        if match:
                            file_id = match.group(1)
                            alt_url = f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({file_id})/$value"
                            logger.info(f"Trying alternative URL: {alt_url}")
                            
                            # Try the alternative URL
                            return self._try_download(alt_url, output_file)
                    
                    return False
                elif response.status_code == 404:  # Not Found
                    logger.error(f"Resource not found (404): The requested URL was not found on the server")
                    return False
                elif response.status_code != 200:
                    logger.error(f"HTTP error: {response.status_code} - {response.reason}")
                    return False
                
                try:
                    response.raise_for_status()
                except Exception as e:
                    logger.error(f"HTTP error: {e}")
                    return False
                
                # Get the total file size if available
                total_size = int(response.headers.get('content-length', 0))
                
                # Download the file in chunks with tqdm progress bar
                with open(output_file, 'wb') as f:
                    if total_size > 0:
                        # Convert to MB for display
                        total_size_mb = total_size / (1024 * 1024)
                        logger.info(f"Total file size: {total_size_mb:.2f} MB")
                        
                        # Create a tqdm progress bar
                        # Use larger chunk size for better performance (1MB instead of 8KB)
                        chunk_size = self.chunk_size  # Use the defined chunk size
                        
                        # Update the progress bar less frequently for better performance
                        with tqdm(total=total_size, unit='B', unit_scale=True, 
                                  desc=f"Downloading {os.path.basename(output_file)}",
                                  ncols=100, disable=self.disable_progress_bars,
                                  mininterval=1.0) as pbar:  # Update at most once per second
                            for chunk in response.iter_content(chunk_size=chunk_size):
                                if chunk:
                                    f.write(chunk)
                                    pbar.update(len(chunk))
                                    
                                    # If progress bars are disabled, log progress periodically
                                    if self.disable_progress_bars and total_size > 0 and pbar.n % (10 * 1024 * 1024) < chunk_size:
                                        percent = (pbar.n / total_size) * 100
                                        logger.info(f"Downloaded: {pbar.n / (1024 * 1024):.2f} MB ({percent:.2f}%)")
                    else:
                        # If content length is unknown, just download without progress bar
                        logger.info("Content length unknown, downloading without progress bar")
                        for chunk in response.iter_content(chunk_size=self.chunk_size):
                            if chunk:
                                f.write(chunk)
            
            logger.info(f"Download completed successfully: {output_file}")
            return True
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            # Log response details for debugging
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response headers: {dict(e.response.headers)}")
                logger.error(f"Response content: {e.response.text[:500]}...")  # First 500 chars
            return False
        except Exception as e:
            logger.error(f"Download error: {e}")
            return False

    def download_tiles_from_json(self, json_file, output_dir="downloads"):
        """
        Download all Sentinel-2 tiles specified in a JSON file.
        
        Args:
            json_file (str): Path to the JSON file containing tile information
            output_dir (str): Directory to save downloaded files
        """
        import json
        
        # Load the JSON file
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        # Extract features from the JSON
        features = []
        
        # Case 1: Direct features array (old format)
        if "features" in data:
            features = data["features"]
        # Case 2: Simple list of features (very old format)
        elif isinstance(data, list):
            features = data
        # Case 3: Unified format with areas and quarterly products (new format)
        elif "areas" in data:
            logging.info("Detected unified JSON format with 'areas'")
            # Extract all quarterly products from all areas
            for area in data['areas']:
                city_name = area.get('cityName', 'Unknown')
                year = area.get('year', 'Unknown')
                logging.info(f"Processing area: {city_name} ({year})")
                
                if 'quarterlyProducts' in area:
                    # Convert quarterly products to features format
                    for product in area['quarterlyProducts']:
                        # Extract the tile ID from the product name (e.g., "Sentinel-2_mosaic_2023_Q1_54SUE_0_0")
                        product_name = product.get('Name', '')
                        parts = product_name.split('_')
                        
                        # Extract tile ID, year, and quarter from product name
                        tile_id = None
                        extracted_year = year
                        quarter = None

                        if len(parts) >= 5:
                            tile_id = parts[4]  # Extract the tile ID part (e.g., "54SUE")
                            
                            # Extract quarter if available
                            if len(parts) >= 4:
                                quarter_part = parts[3]  # Should be like "Q1", "Q2", etc.
                                if quarter_part.startswith('Q'):
                                    quarter = quarter_part
                                    
                            # Double-check year from product name
                            if len(parts) >= 3:
                                year_part = parts[2]
                                if year_part.isdigit() and len(year_part) == 4:
                                    extracted_year = year_part
                        
                        # Format the start and end dates based on year and quarter if ContentDate is missing
                        start_date = None
                        end_date = None
                        
                        if 'ContentDate' in product:
                            start_date = product['ContentDate'].get('Start')
                            end_date = product['ContentDate'].get('End')
                        elif extracted_year and quarter:
                            # If we have year and quarter but no ContentDate, generate dates
                            quarter_num = 0
                            if quarter.startswith('Q'):
                                try:
                                    quarter_num = int(quarter[1:])
                                except ValueError:
                                    pass
                                    
                            if 1 <= quarter_num <= 4:
                                start_month = (quarter_num - 1) * 3 + 1
                                end_month = quarter_num * 3
                                start_date = f"{extracted_year}-{start_month:02d}-01T00:00:00Z"
                                end_date = f"{extracted_year}-{end_month:02d}-30T23:59:59Z"
                        
                        # Build the download URL from the product ID
                        product_id = product.get('Id')
                        download_url = None
                        if product_id:
                            download_url = f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value"
                        
                        feature = {
                            "properties": {
                                "title": product_name,
                                "platform": "SENTINEL-2",
                                "startDate": start_date,
                                "completionDate": end_date,
                                "productType": "GLOBAL-MOSAICS",
                                "services": {
                                    "download": {
                                        "url": download_url
                                    }
                                },
                                # Add additional metadata
                                "city_name": city_name,
                                "distance_km": 0,  # Core city has 0 distance
                                "tile_id": tile_id,
                                "year": extracted_year,
                                "quarter": quarter,
                                "product_id": product_id
                            }
                        }
                        features.append(feature)
                    logging.info(f"Found {len(area.get('quarterlyProducts', []))} quarterly products for {city_name}")
                else:
                    logging.warning(f"No quarterly products found for area: {city_name}")
        else:
            raise ValueError("Invalid JSON format. Expected 'features' key, a list, or 'areas' key.")
        
        logging.info(f"Found {len(features)} products/features in JSON file")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Download all tiles
        downloaded_files = []
        for i, feature in enumerate(features):
            try:
                if "properties" in feature:
                    # New format
                    properties = feature["properties"]
                    tile_id = properties.get("title", "unknown")
                else:
                    # Old format
                    properties = feature
                    tile_id = properties.get("id", "unknown")
                
                logging.info(f"Processing {i+1}/{len(features)}: {tile_id}")
                
                # Download the tile (always use hierarchical structure)
                output_file = self.download_tile(properties, output_dir)
                if output_file:
                    downloaded_files.append(output_file)
                
            except Exception as e:
                logging.error(f"Error downloading tile {i+1}: {str(e)}")
                continue
        
        return downloaded_files