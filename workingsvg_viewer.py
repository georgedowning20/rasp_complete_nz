#!/usr/bin/env python3
"""
Enhanced script to generate an HTML file that displays geoencoded SVG on a Mapbox map.
Supports both GeoJSON and MBTiles viewing modes with automatic conversion.
Usage: python workingsvg_viewer.py <svg_file_path> <output_html_path>
Requires: svg.path (pip install svg.path), tippecanoe (for MBTiles conversion)
"""

import sys
import os
import json
import subprocess
import math
from xml.etree import ElementTree as ET
import cairosvg
from svg.path import parse_path, Move
from PIL import Image
import io
import sqlite3
import base64

def extract_georeference(svg_path):
    """Extract georeference bounds from SVG metadata."""
    tree = ET.parse(svg_path)
    root = tree.getroot()
    metadata = root.find('.//{http://www.w3.org/2000/svg}metadata[@id="georeference"]')
    if metadata is not None and metadata.text:
        geo_data = json.loads(metadata.text)
        return geo_data['bounds']
    return None

def convert_svg_to_png(svg_path, png_path):
    """Convert SVG to PNG."""
    cairosvg.svg2png(url=svg_path, write_to=png_path)

def svg_to_geojson(svg_path):
    """Convert SVG paths to GeoJSON FeatureCollection."""
    tree = ET.parse(svg_path)
    root = tree.getroot()
    
    # Get viewBox
    viewbox = root.get('viewBox')
    if viewbox:
        _, _, width, height = map(float, viewbox.split())
    else:
        width = float(root.get('width', '576'))
        height = float(root.get('height', '213.562498'))
    
    # Get bounds
    metadata = root.find('.//{http://www.w3.org/2000/svg}metadata[@id="georeference"]')
    if metadata is not None and metadata.text:
        geo_data = json.loads(metadata.text)
        lng1, lat1, lng2, lat2 = geo_data['bounds']
    else:
        raise ValueError("No georeference found")
    
    features = []
    
    # Find all path elements
    path_elements = root.findall('.//{http://www.w3.org/2000/svg}path')
    for idx, path_elem in enumerate(path_elements):
        d = path_elem.get('d')
        if not d:
            continue
        
        path = parse_path(d)
        
        # Parse style
        style = path_elem.get('style', '')
        fill = 'none'
        stroke = '#000000'
        if 'fill:' in style:
            fill = style.split('fill:')[1].split(';')[0].strip()
        if 'stroke:' in style:
            stroke = style.split('stroke:')[1].split(';')[0].strip()
        
        current_coords = []
        subpaths = []
        
        for segment in path:
            if isinstance(segment, Move):
                if current_coords:
                    subpaths.append(current_coords)
                    current_coords = []
                # Start new subpath
                current_coords.append((segment.end.real, segment.end.imag))
            else:
                if not current_coords:
                    current_coords.append((segment.start.real, segment.start.imag))
                current_coords.append((segment.end.real, segment.end.imag))
        
        if current_coords:
            subpaths.append(current_coords)
        
        # Create features for each subpath
        subpaths_lnglat = []
        for coords in subpaths:
            # Remove duplicates
            unique_coords = []
            for point in coords:
                if not unique_coords or unique_coords[-1] != point:
                    unique_coords.append(point)
            
            if len(unique_coords) < 2:
                continue  # Skip single points
            
            # Transform to lat/lng
            coords_lnglat = []
            for x, y in unique_coords:
                lng = lng1 + (x / width) * (lng2 - lng1)
                lat = lat2 - (y / height) * (lat2 - lat1)
                coords_lnglat.append([lng, lat])
            
            subpaths_lnglat.append(coords_lnglat)
        
        if not subpaths_lnglat:
            continue
        
        # Smart handling of multiple subpaths with proper geometry validation
        if len(subpaths_lnglat) == 1:
            geom_type = 'LineString'
            coordinates = subpaths_lnglat[0]
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": geom_type,
                    "coordinates": coordinates
                },
                "properties": {
                    "stroke": stroke,
                    "fill": fill,
                    "level": idx
                }
            }
            features.append(feature)
        else:
            # Create complex polygon with holes, but validate and optimize geometry
            # Sort subpaths by area to ensure largest is outer ring
            subpath_areas = []
            for i, coords in enumerate(subpaths_lnglat):
                if len(coords) < 3:
                    continue
                # Calculate approximate area using shoelace formula
                area = 0
                for j in range(len(coords)):
                    k = (j + 1) % len(coords)
                    area += coords[j][0] * coords[k][1]
                    area -= coords[k][0] * coords[j][1]
                area = abs(area) / 2
                subpath_areas.append((area, i, coords))

            if not subpath_areas:
                continue

            # Sort by area (largest first for outer ring)
            subpath_areas.sort(reverse=True, key=lambda x: x[0])

            # Ensure proper winding order
            validated_coords = []
            for i, (area, orig_idx, coords) in enumerate(subpath_areas):
                if len(coords) < 3:
                    continue

                # Check winding order using shoelace formula
                winding_sum = 0
                for j in range(len(coords)):
                    k = (j + 1) % len(coords)
                    winding_sum += (coords[k][0] - coords[j][0]) * (coords[k][1] + coords[j][1])

                # For outer ring (first/largest), ensure clockwise
                # For holes (subsequent), ensure counter-clockwise
                should_be_clockwise = (i == 0)
                is_clockwise = winding_sum > 0

                if should_be_clockwise != is_clockwise:
                    # Reverse the coordinate order
                    coords = coords[::-1]

                validated_coords.append(coords)

            if validated_coords:
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": validated_coords
                    },
                    "properties": {
                        "stroke": stroke,
                        "fill": fill,
                        "level": idx
                    }
                }
                features.append(feature)
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    num_levels = len(path_elements)
    return geojson, num_levels

def generate_html(levels, bounds, mapbox_token, num_levels, base_name, port, raster_available=False):
    """Generate HTML content with Mapbox map supporting both GeoJSON and MBTiles viewing modes."""
    lng1, lat1, lng2, lat2 = bounds
    center_lng = (lng1 + lng2) / 2
    center_lat = (lat1 + lat2) / 2
    zoom = 8  # Adjust as needed

    # Generate options for select
    level_options = '<option value="all" selected>All Levels</option>'
    for i in range(num_levels):
        level_options += f'<option value="{i}">Level {i}</option>'

    # Generate GeoJSON sources and layers
    geojson_sources_js = ""
    geojson_layers_js = ""
    for level, level_geojson in levels.items():
        geojson_str = json.dumps(level_geojson)
        geojson_sources_js += f"""
        map.addSource('geojson-overlay-level-{level}', {{
            type: 'geojson',
            data: {geojson_str}
        }});"""
        
        geojson_layers_js += f"""
        map.addLayer({{
            id: 'geojson-overlay-fill-{level}',
            type: 'fill',
            source: 'geojson-overlay-level-{level}',
            minzoom: 3,
            maxzoom: 16,
            layout: {{ 'visibility': 'visible' }},
            filter: ['!=', ['get', 'fill'], 'none'],
            paint: {{
                'fill-color': ['get', 'fill'],
                'fill-opacity': ['interpolate', ['linear'], ['zoom'], 3, 0.4, 6, 0.6, 14, 0.8],
                'fill-outline-color': ['get', 'stroke'],
                'fill-antialias': true
            }}
        }}, 'country-label');
        
        map.addLayer({{
            id: 'geojson-overlay-line-{level}',
            type: 'line',
            source: 'geojson-overlay-level-{level}',
            minzoom: 3,
            maxzoom: 16,
            layout: {{ 'visibility': 'visible' }},
            paint: {{
                'line-color': ['get', 'stroke'],
                'line-width': ['interpolate', ['linear'], ['zoom'], 3, 0.3, 6, 0.5, 10, 1, 12, 2, 14, 3, 16, 4],
                'line-opacity': ['interpolate', ['linear'], ['zoom'], 3, 0.6, 6, 0.8, 14, 1.0],
                'line-join': 'round',
                'line-cap': 'round'
            }}
        }}, 'country-label');"""

    # Generate MBTiles sources and layers
    mbtiles_sources_js = f"""
        map.addSource('mbtiles-contours', {{
            type: 'vector',
            tiles: ['http://localhost:{port}/tiles/{{z}}/{{x}}/{{y}}.pbf'],
            minzoom: 3,
            maxzoom: 16
        }});"""

    # Add raster source if available
    if raster_available:
        mbtiles_sources_js += f"""
        map.addSource('raster-contours', {{
            type: 'raster',
            tiles: ['http://localhost:{port}/raster-tiles/{{z}}/{{x}}/{{y}}.png'],
            minzoom: 3,
            maxzoom: 16,
            tileSize: 256
        }});"""

    mbtiles_layers_js = ""
    for i in range(num_levels):
        mbtiles_layers_js += f"""
        map.addLayer({{
            id: 'mbtiles-fill-{i}',
            type: 'fill',
            source: 'mbtiles-contours',
            'source-layer': 'map_output',
            minzoom: 3,
            maxzoom: 16,
            layout: {{ 'visibility': 'none' }},
            filter: ['all', ['!=', ['get', 'fill'], 'none'], ['==', ['get', 'level'], {i}]],
            paint: {{
                'fill-color': ['get', 'fill'],
                'fill-opacity': ['interpolate', ['linear'], ['zoom'], 3, 0.4, 6, 0.6, 14, 0.8],
                'fill-outline-color': ['get', 'stroke'],
                'fill-antialias': true
            }}
        }}, 'country-label');
        
        map.addLayer({{
            id: 'mbtiles-line-{i}',
            type: 'line',
            source: 'mbtiles-contours',
            'source-layer': 'map_output',
            minzoom: 3,
            maxzoom: 16,
            layout: {{ 'visibility': 'none' }},
            filter: ['==', ['get', 'level'], {i}],
            paint: {{
                'line-color': ['get', 'stroke'],
                'line-width': ['interpolate', ['linear'], ['zoom'], 3, 0.3, 6, 0.5, 10, 1, 12, 2, 14, 3, 16, 4],
                'line-opacity': ['interpolate', ['linear'], ['zoom'], 3, 0.6, 6, 0.8, 14, 1.0],
                'line-join': 'round',
                'line-cap': 'round'
            }}
        }}, 'country-label');"""

    # Add raster layer if available
    if raster_available:
        mbtiles_layers_js += f"""
        map.addLayer({{
            id: 'raster-contours',
            type: 'raster',
            source: 'raster-contours',
            minzoom: 3,
            maxzoom: 16,
            layout: {{ 'visibility': 'none' }},
            paint: {{
                'raster-opacity': ['interpolate', ['linear'], ['zoom'], 3, 0.6, 6, 0.8, 14, 1.0]
            }}
        }}, 'country-label');"""

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Enhanced Contour Viewer - GeoJSON & MBTiles</title>
    <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no">
    <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
    <link href="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css" rel="stylesheet">
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
        #controls {{ position: absolute; top: 10px; left: 10px; z-index: 1; background: white; padding: 10px; border-radius: 5px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        #controls div {{ margin-bottom: 8px; }}
        #controls label {{ display: inline-block; margin-right: 8px; font-weight: bold; }}
        #controls select, #controls button {{ padding: 4px 8px; border: 1px solid #ccc; border-radius: 3px; }}
        #status {{ position: absolute; top: 10px; right: 10px; z-index: 1; background: rgba(255,255,255,0.9); padding: 5px 10px; border-radius: 3px; font-size: 12px; }}
    </style>
</head>
<body>
<div id="controls">
    <div>
        <label for="view-mode">View Mode:</label>
        <select id="view-mode">
            <option value="geojson" selected>GeoJSON</option>
            <option value="mbtiles">Vector MBTiles</option>
            {'<option value="raster">Raster MBTiles</option>' if raster_available else ''}
        </select>
    </div>
    <div>
        <label for="level">Contour Level:</label>
        <select id="level">
            {level_options}
        </select>
    </div>
    <div>
        <button id="start-server">Start MBTiles Server</button>
    </div>
</div>
<div id="status">Ready</div>
<div id="map"></div>
<script>
    mapboxgl.accessToken = '{mapbox_token}';
    const map = new mapboxgl.Map({{
        container: 'map',
        style: 'mapbox://styles/mapbox/streets-v11',
        center: [{center_lng}, {center_lat}],
        zoom: {zoom}
    }});

    let currentMode = 'geojson';
    let serverStarted = false;

    map.on('load', () => {{
        // Add GeoJSON sources and layers
        {geojson_sources_js}
        {geojson_layers_js}
        
        // Add MBTiles source (layers will be added when needed)
        {mbtiles_sources_js}
        
        updateStatus('GeoJSON mode active');
    }});

    // View mode selector
    document.getElementById('view-mode').addEventListener('change', (e) => {{
        const newMode = e.target.value;
        if ((newMode === 'mbtiles' || newMode === 'raster') && !serverStarted) {{
            alert('Please start the MBTiles server first by clicking the "Start MBTiles Server" button.');
            e.target.value = currentMode;
            return;
        }}
        
        switchViewMode(newMode);
    }});

    // Level selector
    document.getElementById('level').addEventListener('change', (e) => {{
        const selected = e.target.value;
        updateLevelVisibility(selected);
    }});

    // Start server button
    document.getElementById('start-server').addEventListener('click', () => {{
        const button = document.getElementById('start-server');
        button.disabled = true;
        button.textContent = 'Checking...';
        updateStatus('Checking server status...');

        // Check if server is running by trying to access the info endpoint
        fetch(`http://localhost:{port}/info`)
            .then(response => {{
                if (response.ok) {{
                    return response.json();
                }} else {{
                    throw new Error('Server not responding');
                }}
            }})
            .then(data => {{
                serverStarted = true;
                button.textContent = 'Server Running';
                updateStatus('Server is running and ready');

                // Add MBTiles layers
                {mbtiles_layers_js}

                // Switch to MBTiles mode
                document.getElementById('view-mode').value = 'mbtiles';
                switchViewMode('mbtiles');
            }})
            .catch(error => {{
                console.error('Server check failed:', error);
                button.disabled = false;
                button.textContent = 'Start Server';
                updateStatus('Server not running. Please start the Python script with server enabled.');
                alert(`Server is not running. Please run: python workingsvg_viewer.py --port {port} your_file.svg output.html`);
            }});
    }});

    function switchViewMode(mode) {{
        currentMode = mode;
        
        if (mode === 'geojson') {{
            // Hide MBTiles layers
            for (let i = 0; i < {num_levels}; i++) {{
                setLayerVisibility('mbtiles-line-' + i, false);
                setLayerVisibility('mbtiles-fill-' + i, false);
            }}
            setLayerVisibility('raster-contours', false);
            
            // Show GeoJSON layers
            const selectedLevel = document.getElementById('level').value;
            updateLevelVisibility(selectedLevel);
            
            updateStatus('GeoJSON mode active');
        }} else if (mode === 'mbtiles') {{
            // Hide GeoJSON layers and raster layer
            for (let i = 0; i < {num_levels}; i++) {{
                setLayerVisibility('geojson-overlay-line-' + i, false);
                setLayerVisibility('geojson-overlay-fill-' + i, false);
            }}
            setLayerVisibility('raster-contours', false);
            
            // Show MBTiles layers
            const selectedLevel = document.getElementById('level').value;
            updateMBTilesLevelVisibility(selectedLevel);
            
            updateStatus('Vector MBTiles mode active');
        }} else if (mode === 'raster') {{
            // Hide GeoJSON and vector MBTiles layers
            for (let i = 0; i < {num_levels}; i++) {{
                setLayerVisibility('geojson-overlay-line-' + i, false);
                setLayerVisibility('geojson-overlay-fill-' + i, false);
                setLayerVisibility('mbtiles-line-' + i, false);
                setLayerVisibility('mbtiles-fill-' + i, false);
            }}
            
            // Show raster layer
            setLayerVisibility('raster-contours', true);
            
            updateStatus('Raster MBTiles mode active');
        }}
    }}

    function updateLevelVisibility(selected) {{
        for (let i = 0; i < {num_levels}; i++) {{
            const visible = (selected === 'all' || selected == i);
            setLayerVisibility('geojson-overlay-line-' + i, visible);
            setLayerVisibility('geojson-overlay-fill-' + i, visible);
        }}
    }}

    function updateMBTilesLevelVisibility(selected) {{
        for (let i = 0; i < {num_levels}; i++) {{
            const visible = (selected === 'all' || selected == i);
            setLayerVisibility('mbtiles-line-' + i, visible);
            setLayerVisibility('mbtiles-fill-' + i, visible);
        }}
    }}

    function setLayerVisibility(layerId, visible) {{
        if (map.getLayer(layerId)) {{
            map.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none');
        }}
    }}

    function updateStatus(message) {{
        document.getElementById('status').textContent = message;
    }}
</script>
</body>
</html>
"""
    return html

def convert_geojson_to_mbtiles(geojson_path, mbtiles_path):
    """Convert GeoJSON to MBTiles using tippecanoe."""
    try:
        cmd = [
            'tippecanoe',
            '--force',
            '--no-simplification',
            '--no-tile-size-limit',
            '--no-feature-limit',
            '--no-tiny-polygon-reduction',
            '--no-line-simplification',
            '--no-polygon-splitting',
            '--preserve-input-order',
            '--cluster-distance=0',
            '--drop-smallest-as-needed',
            '--layer=map_output',
            '--include=stroke',
            '--include=fill',
            '--include=level',
            '--minimum-zoom=3',
            '--maximum-zoom=16',
            '--no-tile-compression',
            '--no-duplication',
            '-o', mbtiles_path,
            geojson_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"Converted {geojson_path} to {mbtiles_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error converting to MBTiles: {e}")
        print(f"tippecanoe stdout: {e.stdout.decode()}")
        print(f"tippecanoe stderr: {e.stderr.decode()}")
        return False
    except FileNotFoundError:
        print("Error: tippecanoe not found. Please install tippecanoe for MBTiles conversion.")
        return False

def create_raster_mbtiles(svg_path, mbtiles_path, bounds, zoom_levels=(3, 16)):
    """Create raster MBTiles from SVG by converting to high-res PNG and tiling."""
    try:
        lng1, lat1, lng2, lat2 = bounds
        min_zoom, max_zoom = zoom_levels

        # Convert SVG to high-resolution PNG
        png_path = mbtiles_path.replace('.mbtiles', '_temp.png')

        # Calculate image dimensions for high quality
        width = 4096  # High resolution for good quality
        height = int(width * (lat2 - lat1) / (lng2 - lng1))

        # Convert SVG to PNG with high resolution
        cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=width, output_height=height)

        # Create MBTiles database
        conn = sqlite3.connect(mbtiles_path)
        cursor = conn.cursor()

        # Create MBTiles tables
        cursor.execute('''
            CREATE TABLE metadata (
                name TEXT,
                value TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE tiles (
                zoom_level INTEGER,
                tile_column INTEGER,
                tile_row INTEGER,
                tile_data BLOB
            )
        ''')

        cursor.execute('''
            CREATE UNIQUE INDEX tile_index ON tiles (zoom_level, tile_column, tile_row)
        ''')

        # Insert metadata
        metadata = [
            ('name', 'raster_contours'),
            ('type', 'overlay'),
            ('version', '1.0'),
            ('description', 'Raster contours from SVG'),
            ('format', 'png'),
            ('bounds', f'{lng1},{lat1},{lng2},{lat2}'),
            ('center', f'{(lng1+lng2)/2},{(lat1+lat2)/2},{min_zoom}'),
            ('minzoom', str(min_zoom)),
            ('maxzoom', str(max_zoom))
        ]

        cursor.executemany('INSERT INTO metadata VALUES (?, ?)', metadata)

        # Load the PNG image
        img = Image.open(png_path)
        img_width, img_height = img.size

        # Create tiles for each zoom level
        for zoom in range(min_zoom, max_zoom + 1):
            tiles_per_side = 1 << zoom

            # Calculate tile size in pixels at this zoom level
            tile_size_pixels = 256

            # Calculate the geographic bounds of the image
            lng_range = lng2 - lng1
            lat_range = lat2 - lat1

            for tile_x in range(tiles_per_side):
                for tile_y in range(tiles_per_side):
                    # Convert tile coordinates to geographic bounds
                    tile_lng1 = lng1 + (tile_x / tiles_per_side) * lng_range
                    tile_lng2 = lng1 + ((tile_x + 1) / tiles_per_side) * lng_range
                    tile_lat1 = lat2 - ((tile_y + 1) / tiles_per_side) * lat_range
                    tile_lat2 = lat2 - (tile_y / tiles_per_side) * lat_range

                    # Check if this tile intersects with our data bounds
                    if tile_lng2 < lng1 or tile_lng1 > lng2 or tile_lat2 > lat2 or tile_lat1 < lat1:
                        continue

                    # Calculate pixel coordinates in the source image
                    pixel_x1 = int((tile_lng1 - lng1) / lng_range * img_width)
                    pixel_x2 = int((tile_lng2 - lng1) / lng_range * img_width)
                    pixel_y1 = int((lat2 - tile_lat2) / lat_range * img_height)
                    pixel_y2 = int((lat2 - tile_lat1) / lat_range * img_height)

                    # Ensure coordinates are within image bounds
                    pixel_x1 = max(0, min(pixel_x1, img_width))
                    pixel_x2 = max(0, min(pixel_x2, img_width))
                    pixel_y1 = max(0, min(pixel_y1, img_height))
                    pixel_y2 = max(0, min(pixel_y2, img_height))

                    # Skip if tile would be empty
                    if pixel_x2 <= pixel_x1 or pixel_y2 <= pixel_y1:
                        continue

                    # Extract tile from source image
                    tile_img = img.crop((pixel_x1, pixel_y1, pixel_x2, pixel_y2))

                    # Resize to standard tile size
                    tile_img = tile_img.resize((tile_size_pixels, tile_size_pixels), Image.Resampling.LANCZOS)

                    # Convert to RGBA if not already
                    if tile_img.mode != 'RGBA':
                        tile_img = tile_img.convert('RGBA')

                    # Save tile to bytes
                    tile_bytes = io.BytesIO()
                    tile_img.save(tile_bytes, format='PNG')
                    tile_data = tile_bytes.getvalue()

                    # Insert tile into database (use TMS coordinates)
                    tms_y = (1 << zoom) - 1 - tile_y
                    cursor.execute(
                        'INSERT OR REPLACE INTO tiles VALUES (?, ?, ?, ?)',
                        (zoom, tile_x, tms_y, tile_data)
                    )

        conn.commit()
        conn.close()

        # Clean up temporary PNG
        if os.path.exists(png_path):
            os.remove(png_path)

        print(f"Created raster MBTiles: {mbtiles_path}")
        return True

    except Exception as e:
        print(f"Error creating raster MBTiles: {e}")
        return False

def start_mbtiles_server(mbtiles_path, port, base_name):
    """Start a comprehensive server that serves both GeoJSON and MBTiles content."""
    from flask import Flask, Response, jsonify, send_file
    from flask_cors import CORS
    import gzip
    import sqlite3
    import os

    app = Flask(__name__)
    CORS(app)

    # Store paths for serving files
    mbtiles_file = mbtiles_path
    geojson_dir = os.path.dirname(mbtiles_path) or os.getcwd()

    def get_mbtiles_connection():
        if not os.path.exists(mbtiles_file):
            return None
        return sqlite3.connect(mbtiles_file)

    def get_tile(z, x, y):
        conn = get_mbtiles_connection()
        if not conn:
            return None
        cursor = conn.cursor()
        y_tms = (1 << z) - 1 - y
        cursor.execute("SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?", (z, x, y_tms))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def get_raster_tile(z, x, y):
        raster_mbtiles = mbtiles_file.replace('.mbtiles', '_raster.mbtiles')
        if not os.path.exists(raster_mbtiles):
            return None
        conn = sqlite3.connect(raster_mbtiles)
        cursor = conn.cursor()
        # Use TMS coordinates for raster tiles
        y_tms = (1 << z) - 1 - y
        cursor.execute("SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?", (z, x, y_tms))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    @app.route('/')
    def index():
        return jsonify({
            'status': 'running',
            'endpoints': {
                'vector_tiles': '/tiles/{z}/{x}/{y}.pbf',
                'raster_tiles': '/raster-tiles/{z}/{x}/{y}.png',
                'geojson': '/geojson/{level}',
                'geojson_all': '/geojson/all',
                'mbtiles_info': '/info'
            }
        })

    @app.route('/tiles/<int:z>/<int:x>/<int:y>.pbf')
    def tiles(z, x, y):
        tile_data = get_tile(z, x, y)
        if tile_data:
            response = Response(tile_data)
            response.headers['Content-Type'] = 'application/x-protobuf'
            response.headers['Content-Encoding'] = 'gzip'
            return response
        return Response('', status=404)

    @app.route('/raster-tiles/<int:z>/<int:x>/<int:y>.png')
    def raster_tiles(z, x, y):
        tile_data = get_raster_tile(z, x, y)
        if tile_data:
            response = Response(tile_data)
            response.headers['Content-Type'] = 'image/png'
            return response
        return Response('', status=404)

    @app.route('/geojson/<level>')
    def get_geojson(level):
        if level == 'all':
            geojson_path = os.path.join(geojson_dir, f"{base_name}.geojson")
        else:
            geojson_path = os.path.join(geojson_dir, f"{base_name}_level_{level}.geojson")

        if os.path.exists(geojson_path):
            return send_file(geojson_path, mimetype='application/json')
        return jsonify({'error': 'GeoJSON file not found'}), 404

    @app.route('/geojson/all')
    def get_all_geojson():
        geojson_path = os.path.join(geojson_dir, f"{base_name}.geojson")
        if os.path.exists(geojson_path):
            return send_file(geojson_path, mimetype='application/json')
        return jsonify({'error': 'Combined GeoJSON file not found'}), 404

    @app.route('/info')
    def get_info():
        conn = get_mbtiles_connection()
        if not conn:
            return jsonify({'error': 'MBTiles file not found'})

        cursor = conn.cursor()

        # Get metadata
        cursor.execute("SELECT name, value FROM metadata")
        metadata = dict(cursor.fetchall())

        # Get tile statistics
        cursor.execute("SELECT zoom_level, COUNT(*) FROM tiles GROUP BY zoom_level ORDER BY zoom_level")
        zoom_stats = cursor.fetchall()

        # Get total tiles
        cursor.execute("SELECT COUNT(*) FROM tiles")
        total_tiles = cursor.fetchone()[0]

        conn.close()

        # Get available GeoJSON files
        try:
            available_geojson = [f for f in os.listdir(geojson_dir) if f.endswith('.geojson')]
        except (OSError, FileNotFoundError):
            available_geojson = []

        return jsonify({
            'mbtiles_path': mbtiles_file,
            'metadata': metadata,
            'zoom_levels': [{'zoom': z, 'tiles': c} for z, c in zoom_stats],
            'total_tiles': total_tiles,
            'available_geojson': available_geojson
        })

    @app.route('/start-server', methods=['POST'])
    def start_server():
        return jsonify({'success': True, 'message': 'Server is running'})

    print(f"Enhanced server starting on port {port}...")
    print(f"Serving MBTiles: {mbtiles_file}")
    print(f"Serving GeoJSON from: {geojson_dir}")
    print(f"Available at: http://localhost:{port}")
    print("Endpoints:")
    print("  - MBTiles tiles: /tiles/{z}/{x}/{y}.pbf")
    print("  - GeoJSON by level: /geojson/{level} or /geojson/all")
    print("  - Server info: /info")

    # Run the server (this will block)
    app.run(host='0.0.0.0', port=port, debug=False)

def main():
    import argparse
    from flask import Flask, Response, request, jsonify
    import sqlite3
    import threading
    import time

    parser = argparse.ArgumentParser(description="Generate enhanced HTML viewer with GeoJSON and MBTiles support.")
    parser.add_argument('svg_file_path', nargs='?', default='stars.curr.1400lst.d2.data_contour_simple.svg', help='Path to the SVG file')
    parser.add_argument('output_html_path', nargs='?', default='enhanced_viewer.html', help='Path for the output HTML file')
    parser.add_argument('--port', type=int, default=5003, help='Port for MBTiles server (default: 5003)')
    parser.add_argument('--no-server', action='store_true', help='Skip starting the MBTiles server')

    args = parser.parse_args()

    svg_path = args.svg_file_path
    output_html_path = args.output_html_path
    port = args.port

    if not os.path.exists(svg_path):
        print(f"SVG file not found: {svg_path}")
        sys.exit(1)

    bounds = extract_georeference(svg_path)
    if not bounds:
        print("No georeference found in SVG.")
        sys.exit(1)

    # Convert SVG to GeoJSON
    geojson_data, num_levels = svg_to_geojson(svg_path)
    print(f"Converted SVG to GeoJSON with {len(geojson_data['features'])} features from {num_levels} levels")

    mapbox_token = os.getenv('MAPBOX_ACCESS_TOKEN', 'pk.eyJ1IjoiZ2VvcmdlZG93bmluZyIsImEiOiJjbWZlMzBndzYwMmhxMmpyNWFqcnkzdjJmIn0.L9RHEN7ySukYIhsKKu4-Rw')
    if not mapbox_token:
        print("Please set MAPBOX_ACCESS_TOKEN environment variable.")
        sys.exit(1)

    # Save separate GeoJSONs for each level
    levels = {}
    for feature in geojson_data['features']:
        level = feature['properties']['level']
        if level not in levels:
            levels[level] = {"type": "FeatureCollection", "features": []}
        levels[level]['features'].append(feature)
    
    base_name = output_html_path.replace('.html', '')
    
    # Save level-specific GeoJSONs
    for level, level_geojson in levels.items():
        level_path = f"{base_name}_level_{level}.geojson"
        with open(level_path, 'w') as f:
            json.dump(level_geojson, f, indent=2)
        print(f"GeoJSON for level {level} saved: {level_path}")
    
    # Convert to MBTiles
    print("\nConverting GeoJSON to MBTiles...")
    combined_geojson_path = f"{base_name}.geojson"
    combined_mbtiles_path = f"{base_name}.mbtiles"
    
    # Save combined GeoJSON
    with open(combined_geojson_path, 'w') as f:
        json.dump(geojson_data, f, indent=2)
    print(f"Combined GeoJSON saved: {combined_geojson_path}")
    
    # Convert to MBTiles
    if convert_geojson_to_mbtiles(combined_geojson_path, combined_mbtiles_path):
        print(f"MBTiles conversion successful: {combined_mbtiles_path}")
    else:
        print("MBTiles conversion failed - viewer will work in GeoJSON-only mode")
        combined_mbtiles_path = None

    # Create raster MBTiles version
    raster_mbtiles_path = combined_mbtiles_path.replace('.mbtiles', '_raster.mbtiles') if combined_mbtiles_path else f"{base_name}_raster.mbtiles"
    if create_raster_mbtiles(svg_path, raster_mbtiles_path, bounds):
        print(f"Raster MBTiles created: {raster_mbtiles_path}")
        raster_mbtiles_available = True
    else:
        print("Raster MBTiles creation failed")
        raster_mbtiles_path = None
        raster_mbtiles_available = False

    # Generate enhanced HTML
    base_name_for_html = base_name
    html_content = generate_html(levels, bounds, mapbox_token, num_levels, base_name_for_html, port, raster_mbtiles_available)
    with open(output_html_path, 'w') as f:
        f.write(html_content)
    
    print(f"\nEnhanced HTML viewer generated: {output_html_path}")
    print("Features:")
    print("- Toggle between GeoJSON, Vector MBTiles, and Raster MBTiles viewing modes")
    print("- Select individual contour levels or view all levels")
    print("- Improved line widths for better visibility at high zoom levels")
    print("- Automatic MBTiles server integration")

    # Start MBTiles server if requested and conversion was successful
    if not args.no_server and combined_mbtiles_path and os.path.exists(combined_mbtiles_path):
        print(f"\nStarting Enhanced server on port {port}...")
        print("This server will serve GeoJSON, Vector MBTiles, and Raster MBTiles content.")
        print("Press Ctrl+C to stop the server and exit.")
        try:
            # Run server in main thread (blocking)
            start_mbtiles_server(combined_mbtiles_path, port, base_name)
        except KeyboardInterrupt:
            print("\nServer stopped by user.")
        except Exception as e:
            print(f"Server error: {e}")
    else:
        print("\nServer not started.")
        if args.no_server:
            print("Use --no-server flag was specified.")
        elif not combined_mbtiles_path:
            print("MBTiles conversion failed.")
        else:
            print("MBTiles file not found.")
        print("You can still use the HTML viewer in GeoJSON-only mode.")

    print(f"MBTiles file saved: {combined_mbtiles_path}")
    print("You can now use this MBTiles file with Mapbox or other GIS software.")

if __name__ == "__main__":
    main()