#!/usr/bin/env python3
"""
Custom MBTiles Server with Style Support
Serves MBTiles vector tiles with custom Mapbox GL style
"""

import sqlite3
import json
import gzip
from flask import Flask, Response, send_file, render_template_string, request
from flask_cors import CORS
import os
import sys

app = Flask(__name__)
CORS(app)

# Configuration
MBTILES_PATH = 'map_output.mbtiles'
PORT = 5002

def get_mbtiles_connection():
    """Get SQLite connection to MBTiles file"""
    if not os.path.exists(MBTILES_PATH):
        print(f"Error: {MBTILES_PATH} not found")
        sys.exit(1)
    return sqlite3.connect(MBTILES_PATH)

def get_metadata():
    """Get MBTiles metadata"""
    conn = get_mbtiles_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, value FROM metadata")
    metadata = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return metadata

def get_tile(z, x, y):
    """Get tile data from MBTiles"""
    conn = get_mbtiles_connection()
    cursor = conn.cursor()

    # Flip Y coordinate for TMS to XYZ
    y_tms = (1 << z) - 1 - y

    cursor.execute("""
        SELECT tile_data FROM tiles
        WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?
    """, (z, x, y_tms))

    row = cursor.fetchone()
    conn.close()

    if row:
        return row[0]
    return None

@app.route('/')
def index():
    """Serve the main map interface"""
    html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Custom Contour Tiles</title>
    <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no">
    <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
    <link href="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css" rel="stylesheet">
    <style>
        body { margin: 0; padding: 0; }
        #map { position: absolute; top: 0; bottom: 0; width: 100%; }
        #level-select { position: absolute; top: 10px; left: 10px; z-index: 1; background: white; padding: 5px; }
    </style>
</head>
<body>
<div id="level-select">
    <label for="level">Contour Level:</label>
    <select id="level">
        <option value="all" selected>All Levels</option>
        <option value="0">Level 0</option>
        <option value="1">Level 1</option>
        <option value="2">Level 2</option>
        <option value="3">Level 3</option>
        <option value="4">Level 4</option>
        <option value="5">Level 5</option>
        <option value="6">Level 6</option>
    </select>
</div>
<div id="map"></div>
<script>
    mapboxgl.accessToken = 'pk.eyJ1IjoiZ2VvcmdlZG93bmluZyIsImEiOiJjbWZlMzBndzYwMmhxMmpyNWFqcnkzdjJmIn0.L9RHEN7ySukYIhsKKu4-Rw';

    const map = new mapboxgl.Map({
        container: 'map',
        style: '/style.json',
        center: [-1.5, 52.5],  // Center on UK
        zoom: 6
    });

    // Level selector
    document.getElementById('level').addEventListener('change', (e) => {
        const selected = e.target.value;
        const styleUrl = selected === 'all' ? '/style.json' : `/style.json?level=${selected}`;
        map.setStyle(styleUrl);
    });
</script>
</body>
</html>
"""
    return html

@app.route('/style.json')
def style():
    """Serve the Mapbox GL style JSON"""
    level = request.args.get('level', 'all')

    # Base style
    style_json = {
        "version": 8,
        "sources": {
            "contours": {
                "type": "vector",
                "tiles": [f"http://localhost:{PORT}/tiles/{{z}}/{{x}}/{{y}}.pbf"],
                "minzoom": 0,
                "maxzoom": 14
            }
        },
        "layers": []
    }

    if level == 'all':
        # Add all levels
        for i in range(7):
            style_json["layers"].extend([
                {
                    "id": f"line-{i}",
                    "type": "line",
                    "source": "contours",
                    "source-layer": "map_output",
                    "paint": {
                        "line-color": ["get", "stroke"],
                        "line-width": [
                            "interpolate", ["linear"], ["zoom"],
                            6, 0.5,
                            10, 1,
                            12, 2,
                            14, 3,
                            16, 4
                        ],
                        "line-opacity": [
                            "interpolate", ["linear"], ["zoom"],
                            6, 0.8,
                            14, 1.0
                        ]
                    }
                },
                {
                    "id": f"fill-{i}",
                    "type": "fill",
                    "source": "contours",
                    "source-layer": "map_output",
                    "filter": ["!=", ["get", "fill"], "none"],
                    "paint": {
                        "fill-color": ["get", "fill"],
                        "fill-opacity": 0.6,
                        "fill-outline-color": ["get", "stroke"]
                    }
                }
            ])
    else:
        # Add single level
        i = int(level)
        style_json["layers"].extend([
            {
                "id": f"line-{i}",
                "type": "line",
                "source": "contours",
                "source-layer": "map_output",
                "paint": {
                    "line-color": ["get", "stroke"],
                    "line-width": [
                        "interpolate", ["linear"], ["zoom"],
                        6, 0.5,
                        10, 1,
                        12, 2,
                        14, 3,
                        16, 4
                    ],
                    "line-opacity": [
                        "interpolate", ["linear"], ["zoom"],
                        6, 0.8,
                        14, 1.0
                    ]
                }
            },
            {
                "id": f"fill-{i}",
                "type": "fill",
                "source": "contours",
                "source-layer": "map_output",
                "filter": ["!=", ["get", "fill"], "none"],
                "paint": {
                    "fill-color": ["get", "fill"],
                    "fill-opacity": 0.6,
                    "fill-outline-color": ["get", "stroke"]
                }
            }
        ])

    return Response(json.dumps(style_json), mimetype='application/json')

@app.route('/tiles/<int:z>/<int:x>/<int:y>.pbf')
def tiles(z, x, y):
    """Serve vector tiles"""
    tile_data = get_tile(z, x, y)

    if tile_data:
        # Return gzipped PBF data
        response = Response(tile_data)
        response.headers['Content-Type'] = 'application/x-protobuf'
        response.headers['Content-Encoding'] = 'gzip'
        return response
    else:
        return Response('', status=404)

@app.route('/metadata.json')
def metadata():
    """Serve MBTiles metadata"""
    meta = get_metadata()
    return Response(json.dumps(meta), mimetype='application/json')

if __name__ == '__main__':
    print(f"Starting custom MBTiles server on port {PORT}")
    print(f"Access at: http://localhost:{PORT}")
    print(f"MBTiles file: {MBTILES_PATH}")

    # Check if MBTiles exists
    if not os.path.exists(MBTILES_PATH):
        print(f"Error: {MBTILES_PATH} not found!")
        print("Please run the display_svg_on_mapbox.py script first to generate MBTiles.")
        sys.exit(1)

    app.run(host='0.0.0.0', port=PORT, debug=True)