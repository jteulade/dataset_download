"""
Map Visualizer Module

This module provides functions for creating interactive maps to visualize
Sentinel-2 data, including city locations and tile footprints.
"""

import folium
from folium.plugins import MeasureControl, MiniMap, MarkerCluster
import random
import os
from shapely.geometry import Polygon, Point
import math

def haversine_distance(point1, point2):
    """
    Calculate the haversine distance between two points.
    
    Args:
        point1: Tuple of (latitude, longitude)
        point2: Tuple of (latitude, longitude)
        
    Returns:
        Distance in kilometers
    """
    # Convert to radians
    lat1, lon1 = point1
    lat2, lon2 = point2
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of Earth in kilometers
    return c * r

def create_mosaic_map(cities_results, output_file='maps/city_mosaics_map.html'):
    """
    Create an interactive map showing cities and their associated Sentinel-2 mosaic tiles.
    
    Args:
        cities_results (list): List of dictionaries containing query results for each city
        output_file (str): Path to save the HTML map file
        
    Returns:
        str: Path to the saved HTML map file
    """
    print(f"Creating interactive map with {len(cities_results)} cities and their Sentinel-2 tiles")
    
    # Create a map centered at the average of all coordinates
    valid_coords = [(r['lat'], r['lon']) for r in cities_results if r['count'] > 0]
    
    if not valid_coords:
        print("No valid coordinates with Sentinel-2 data found")
        return None
    
    avg_lat = sum(lat for lat, _ in valid_coords) / len(valid_coords)
    avg_lon = sum(lon for _, lon in valid_coords) / len(valid_coords)
    
    # Create a map with the default CartoDB positron tiles
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=3, tiles=None)
    
    # Add different base maps
    folium.TileLayer(
        tiles='CartoDB positron',
        name='Light Map',
        control=True,
    ).add_to(m)
    
    folium.TileLayer(
        tiles='CartoDB dark_matter',
        name='Dark Map',
        control=True,
    ).add_to(m)
    
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='OpenStreetMap',
        control=True,
    ).add_to(m)
    
    # Add satellite view
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite',
        control=True,
        overlay=False,
    ).add_to(m)
    
    # Add a hybrid satellite view with labels
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite with Labels',
        control=True,
        overlay=False,
    ).add_to(m)
    
    # Add labels as an overlay for the hybrid view
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Labels',
        control=True,
        overlay=True,
        show=False,
    ).add_to(m)
    
    # Add a terrain view
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Terrain',
        control=True,
        overlay=False,
    ).add_to(m)
    
    # Add a minimap
    minimap = MiniMap(toggle_display=True)
    m.add_child(minimap)
    
    # Add measurement tools
    measure_control = MeasureControl(
        position='topleft',
        primary_length_unit='kilometers',
        secondary_length_unit='miles',
        primary_area_unit='square kilometers',
        secondary_area_unit='acres'
    )
    m.add_child(measure_control)
    
    # Create feature groups for better organization
    city_group = folium.FeatureGroup(name="Cities")
    random_point_group = folium.FeatureGroup(name="Random Points")
    tile_group = folium.FeatureGroup(name="Sentinel-2 Tiles")
    connection_group = folium.FeatureGroup(name="City-Tile Connections")
    random_connection_group = folium.FeatureGroup(name="City-Random Point Connections")
    
    m.add_child(city_group)
    m.add_child(random_point_group)
    m.add_child(tile_group)
    m.add_child(connection_group)
    m.add_child(random_connection_group)
    
    # Define a list of colors to use for different tiles
    tile_colors = ['blue', 'green', 'purple', 'orange', 'darkred', 'darkblue', 'darkgreen', 'cadetblue', 'darkpurple', 'pink']
    
    # Add cities and their tiles to the map
    for result in cities_results:
        lat, lon = result['lat'], result['lon']
        city_name = result.get('city_name', f"City at ({lat}, {lon})")
        
        # Use display_name if available (for random points)
        display_name = result.get('display_name', city_name)
        
        is_mosaic = result.get('is_mosaic', False)
        is_random_point = result.get('is_neighbor', False) or "Random Point" in display_name
        
        # Determine which feature group to add to based on whether it's a random point
        target_group = random_point_group if is_random_point else city_group
        marker_color = 'red'  # Default color for cities
        marker_radius = 5     # Default radius for cities
        
        if is_random_point:
            # Check if the point is on land or in water
            is_on_land = result.get('is_on_land', True)  # Default to land if not specified
            
            if is_on_land:
                marker_color = 'green'  # Green for random points on land
            else:
                marker_color = 'blue'   # Blue for random points in water
                
            marker_radius = 4  # Smaller radius for random points
            
            # For random points with no data, use a lighter shade
            if result['count'] == 0:
                if is_on_land:
                    marker_color = 'lightgreen'
                else:
                    marker_color = 'lightblue'
                marker_radius = 3
        
        # Add a marker for the city or random point
        popup_text = f"<b>{display_name}</b><br>Coordinates: ({lat}, {lon})"
        
        if is_random_point:
            # Add land/water status to popup
            land_status = result.get('land_status', 'unknown')
            popup_text += f"<br>Status: {land_status.capitalize()}"
            
        if result['count'] > 0:
            popup_text += "<br>Best tile selected"
        else:
            popup_text += "<br>No tiles found"
            
        folium.CircleMarker(
            location=[lat, lon],
            radius=marker_radius,
            color=marker_color,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.7,
            popup=popup_text
        ).add_to(target_group)
        
        # If this is a random point, draw a line to the original city
        if is_random_point and 'original_city_lat' in result and 'original_city_lon' in result:
            original_lat = result['original_city_lat']
            original_lon = result['original_city_lon']
            distance = result.get('distance_from_city', 'unknown')
            
            # Choose line color based on land/water status
            is_on_land = result.get('is_on_land', True)
            line_color = 'green' if is_on_land else 'blue'
            
            # Add a line connecting the random point to the original city
            folium.PolyLine(
                locations=[[original_lat, original_lon], [lat, lon]],
                color=line_color,
                weight=2,
                opacity=0.7,
                popup=f"Distance: {distance} km",
                dash_array='5, 5'
            ).add_to(random_connection_group)
        
        # Add polygons for each tile's footprint
        for i, feature in enumerate(result['features']):
            try:
                coords = []
                footprint_source = None
                
                # First try to get the footprint from the feature properties
                footprint = feature.get('footprint')
                if footprint and isinstance(footprint, str) and footprint.startswith("POLYGON"):
                    # Parse the footprint WKT string
                    # Example: "POLYGON((lon1 lat1, lon2 lat2, ...))"
                    footprint = footprint.replace('POLYGON((', '').replace('))', '')
                    coords_str = footprint.split(',')
                    
                    for coord_str in coords_str:
                        try:
                            parts = coord_str.strip().split(' ')
                            if len(parts) >= 2:
                                lon_str, lat_str = parts[0], parts[1]
                                coords.append([float(lat_str), float(lon_str)])
                        except (ValueError, IndexError) as e:
                            # Silently continue when a coordinate can't be parsed
                            pass
                    
                    if len(coords) >= 3:
                        footprint_source = "WKT String"
                
                # If no valid footprint, try to get geometry from the original feature
                if len(coords) < 3:
                    # Try to extract geometry from the original_feature
                    original_feature = feature.get('original_feature', {})
                    
                    # Check for restoGeometry (OpenSearch format)
                    if 'restoGeometry' in original_feature:
                        geom = original_feature['restoGeometry']
                        if 'type' in geom and geom['type'] == 'Polygon' and 'coordinates' in geom:
                            # Get coordinates from the geometry
                            geometry_coords = geom['coordinates'][0]
                            coords = [[coord[1], coord[0]] for coord in geometry_coords]  # Swap lon/lat to lat/lon for folium
                            if len(coords) >= 3:
                                footprint_source = "restoGeometry"
                    
                    # Try standard geometry (STAC format)
                    if len(coords) < 3 and 'geometry' in original_feature:
                        geom = original_feature['geometry']
                        if geom and isinstance(geom, dict) and geom.get('type') == 'Polygon' and 'coordinates' in geom:
                            geometry_coords = geom['coordinates'][0]
                            coords = [[coord[1], coord[0]] for coord in geometry_coords]  # Swap lon/lat to lat/lon for folium
                            if len(coords) >= 3:
                                footprint_source = "GeoJSON geometry"
                    
                    # Try GeoFootprint (OData format)
                    if len(coords) < 3 and 'GeoFootprint' in original_feature:
                        geom = original_feature['GeoFootprint']
                        if geom and isinstance(geom, dict) and geom.get('type') == 'Polygon' and 'coordinates' in geom:
                            geometry_coords = geom['coordinates'][0]
                            coords = [[coord[1], coord[0]] for coord in geometry_coords]  # Swap lon/lat to lat/lon for folium
                            if len(coords) >= 3:
                                footprint_source = "GeoFootprint"
                
                # If still no valid coordinates, create a fallback silently
                if len(coords) < 3:
                    # Try to create a simple square around the point as fallback
                    if result['count'] > 0:
                        # Create a simple square around the point (approximately 20km)
                        box_size = 0.2  # degrees, roughly 20km
                        # Center the box on the point
                        box_coords = [
                            [lat - box_size, lon - box_size],
                            [lat - box_size, lon + box_size],
                            [lat + box_size, lon + box_size],
                            [lat + box_size, lon - box_size],
                            [lat - box_size, lon - box_size],
                        ]
                        coords = box_coords
                        footprint_source = "fallback square"
                    else:
                        continue
                
                # Store the footprint source for logging (without warnings)
                feature['footprint_source'] = footprint_source
                
                # Check if the point is within the polygon
                point_in_polygon = False
                try:
                    # Convert the coordinates to lon/lat for checking
                    poly_coords = [(c[1], c[0]) for c in coords]  # Convert to lon/lat
                    point = (lon, lat)  # Query point
                    
                    # Create a polygon and check if the point is inside
                    polygon = Polygon(poly_coords)
                    point_in_polygon = polygon.contains(Point(point))
                    
                    if not point_in_polygon and is_random_point:
                        # Store the information instead of printing a warning
                        feature['point_within_footprint'] = False
                        
                        # Calculate the distance from the point to the polygon
                        from shapely.ops import nearest_points
                        point_shape = Point(point)
                        nearest_point = nearest_points(point_shape, polygon)[1]
                        
                        # Calculate haversine distance in kilometers
                        distance_to_tile = haversine_distance(
                            (point[1], point[0]),  # Convert lon/lat to lat/lon
                            (nearest_point.y, nearest_point.x)  # Convert lon/lat to lat/lon
                        )
                        # Store the distance instead of printing it
                        feature['distance_to_footprint'] = distance_to_tile
                except Exception as e:
                    print(f"Error checking if point is in polygon: {e}")
                
                # Choose a color and style based on the index and whether it's a random point
                if is_random_point:
                    # Choose color based on land/water status
                    is_on_land = result.get('is_on_land', True)
                    base_color = 'green' if is_on_land else 'blue'
                    
                    # Use a different style if the point is not within the polygon
                    if not point_in_polygon:
                        color = f"dark{base_color}"
                        dash_array = '5, 5'
                        fill_opacity = 0.3
                        # Add a line connecting the random point to the nearest point on the polygon
                        try:
                            from shapely.ops import nearest_points
                            point_shape = Point(point)
                            nearest_point = nearest_points(point_shape, polygon)[1]
                            
                            # Add a line to the nearest point on the polygon boundary
                            folium.PolyLine(
                                locations=[[lat, lon], [nearest_point.y, nearest_point.x]],
                                color='red',
                                weight=2,
                                opacity=0.7,
                                popup='Distance to tile boundary',
                                dash_array='3, 3'
                            ).add_to(tile_group)
                        except Exception as e:
                            print(f"Error creating distance line: {e}")
                    else:
                        color = base_color
                        dash_array = 'none'
                        fill_opacity = 0.5
                else:
                    color = tile_colors[i % len(tile_colors)]
                    dash_array = 'none' if i == 0 else '5, 5'
                    fill_opacity = 0.5
                    
                # Create a popup with information about the tile
                popup_html = f"""
                <b>Tile Information:</b><br>
                <b>Title:</b> {feature['title']}<br>
                """
                
                # Add warning if the random point is not within the tile footprint
                if not feature.get('point_within_footprint', True) and is_random_point:
                    popup_html += f"<b>Note:</b> Point is outside tile boundary ({feature.get('distance_to_footprint', 0):.2f} km away)<br>"
                
                if 'start_date' in feature:
                    popup_html += f"<b>Start Date:</b> {feature['start_date']}<br>"
                
                popup_html += f"<b>Product Type:</b> {feature['product_type']}<br>"
                
                if feature.get('tile_id'):
                    popup_html += f"<b>Tile ID:</b> {feature['tile_id']}<br>"
                
                if feature.get('quarterly_count'):
                    popup_html += f"<b>Quarterly Products:</b> {feature['quarterly_count']}<br>"
                
                if feature.get('quarters'):
                    popup_html += f"<b>Quarters:</b> {', '.join(feature.get('quarters', []))}<br>"
                
                # Add the city metadata to the popup
                # First try to get from feature, then from result if not available
                city_name = feature.get('city_name') or result.get('city_name')
                city_lat = feature.get('city_lat') or result.get('city_lat')
                city_lon = feature.get('city_lon') or result.get('city_lon')
                is_neighbor = feature.get('is_neighbor')
                if is_neighbor is None and 'is_neighbor' in result:
                    is_neighbor = result.get('is_neighbor')
                
                if city_name:
                    popup_html += f"<b>Associated City:</b> {city_name}<br>"
                
                if city_lat is not None and city_lon is not None:
                    popup_html += f"<b>City Coordinates:</b> ({city_lat:.4f}, {city_lon:.4f})<br>"
                
                if is_neighbor is not None:
                    neighbor_status = "Random Point" if is_neighbor else "City Center"
                    popup_html += f"<b>Point Type:</b> {neighbor_status}<br>"
                
                if feature.get('download_url'):
                    popup_html += f"<a href='{feature['download_url']}' target='_blank'>Download Link</a>"
                
                # Add the polygon to the map
                folium.Polygon(
                    locations=coords,
                    color=color,
                    weight=2,
                    dash_array=dash_array,
                    fill=True,
                    fill_color=color,
                    fill_opacity=fill_opacity,
                    popup=folium.Popup(popup_html, max_width=300)
                ).add_to(tile_group)
                
                # Add a line connecting the city to the center of the tile
                # Calculate the center of the polygon
                center_lat = sum(lat for lat, _ in coords) / len(coords)
                center_lon = sum(lon for _, lon in coords) / len(coords)
                
                # Add a line connecting the city to the tile center
                folium.PolyLine(
                    locations=[[lat, lon], [center_lat, center_lon]],
                    color=color,
                    weight=1,
                    opacity=0.5,
                    dash_array='3, 5'
                ).add_to(connection_group)
            except KeyError as e:
                print(f"KeyError processing tile {feature.get('title', 'Unknown')}: {e}")
            except ValueError as e:
                print(f"ValueError processing tile {feature.get('title', 'Unknown')}: {e}")
            except TypeError as e:
                print(f"TypeError processing tile {feature.get('title', 'Unknown')}: {e}")
            except Exception as e:
                print(f"Error processing tile {feature.get('title', 'Unknown')}: {e}")
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Save the map
    m.save(output_file)
    print(f"Interactive map saved to {output_file}")
    
    return output_file