#!/usr/bin/env python3
"""
RASP Weather Forecast Viewer
A full-featured map-based viewer for RASP forecast images with:
- Date selector dropdown
- Time slider
- Parameter dropdown
- Domain selector
- Proper Lambert Conformal projection overlay
"""

import os
import re
import json
from flask import Flask, render_template_string, jsonify, send_file

try:
    import pyproj
except ImportError:
    print("Installing pyproj...")
    os.system("pip install pyproj")
    import pyproj

app = Flask(__name__)

# Configuration
RESULTS_DIR = '/Users/georgedowning/Desktop/Rasp_complete/results'
OUT_DIR = os.path.join(RESULTS_DIR, 'OUT')

# WRF Domain configuration - Lambert Conformal projection
WRF_CONFIG = {
    'ref_lat': -38.50,
    'ref_lon': 176.00,
    'truelat1': -35.00,
    'truelat2': -42.00,
    'stand_lon': 176.00,
    'd1': {
        'dx': 6000, 'dy': 6000,
        'e_we': 80, 'e_sn': 100,
    },
    'd2': {
        'dx': 2000, 'dy': 2000,
        'e_we': 127, 'e_sn': 127,
        'i_parent_start': 16, 'j_parent_start': 42,
        'parent_grid_ratio': 3,
    }
}


class LambertConformalDomain:
    """Calculate WRF Lambert Conformal Conic domain bounds."""
    def __init__(self, ref_lat, ref_lon, truelat1, truelat2, stand_lon,
                 dx, dy, e_we, e_sn, parent=None, i_parent_start=1, j_parent_start=1,
                 parent_grid_ratio=1):
        self.ref_lat = ref_lat
        self.ref_lon = ref_lon
        self.truelat1 = truelat1
        self.truelat2 = truelat2
        self.stand_lon = stand_lon
        self.dx = dx
        self.dy = dy
        self.e_we = e_we
        self.e_sn = e_sn
        self.parent = parent
        self.i_parent_start = i_parent_start
        self.j_parent_start = j_parent_start
        self.parent_grid_ratio = parent_grid_ratio
        
        # Create pyproj projection
        self.proj = pyproj.Proj(
            proj='lcc',
            lat_1=truelat1,
            lat_2=truelat2,
            lat_0=ref_lat,
            lon_0=stand_lon,
            x_0=0,
            y_0=0,
            ellps='WGS84'
        )
        
        self.proj_latlon = pyproj.Proj(proj='latlong', datum='WGS84')
        self.transformer_to_latlon = pyproj.Transformer.from_proj(
            self.proj, self.proj_latlon, always_xy=True
        )
        self.transformer_to_lcc = pyproj.Transformer.from_proj(
            self.proj_latlon, self.proj, always_xy=True
        )
        
    def get_domain_bounds(self, use_square_image=False):
        """Calculate the lat/lon bounds of the domain corners.
        
        If use_square_image=True, compute bounds for a square image that contains
        the entire domain (NCL generates square images for non-square grids).
        """
        ref_x, ref_y = self.transformer_to_lcc.transform(self.ref_lon, self.ref_lat)
        
        if self.parent is not None:
            parent_ref_x, parent_ref_y = self.transformer_to_lcc.transform(
                self.parent.ref_lon, self.parent.ref_lat
            )
            parent_half_x = (self.parent.e_we - 1) * self.parent.dx / 2.0
            parent_half_y = (self.parent.e_sn - 1) * self.parent.dy / 2.0
            parent_ll_x = parent_ref_x - parent_half_x
            parent_ll_y = parent_ref_y - parent_half_y
            
            nest_ll_x = parent_ll_x + (self.i_parent_start - 1) * self.parent.dx
            nest_ll_y = parent_ll_y + (self.j_parent_start - 1) * self.parent.dy
            nest_ur_x = nest_ll_x + (self.e_we - 1) * self.dx
            nest_ur_y = nest_ll_y + (self.e_sn - 1) * self.dy
        else:
            half_x = (self.e_we - 1) * self.dx / 2.0
            half_y = (self.e_sn - 1) * self.dy / 2.0
            
            # For square images (like NCL produces), use the larger dimension
            if use_square_image:
                half_extent = max(half_x, half_y)
                nest_ll_x = ref_x - half_extent
                nest_ll_y = ref_y - half_extent
                nest_ur_x = ref_x + half_extent
                nest_ur_y = ref_y + half_extent
            else:
                nest_ll_x = ref_x - half_x
                nest_ll_y = ref_y - half_y
                nest_ur_x = ref_x + half_x
                nest_ur_y = ref_y + half_y
        
        ll_lon, ll_lat = self.transformer_to_latlon.transform(nest_ll_x, nest_ll_y)
        ur_lon, ur_lat = self.transformer_to_latlon.transform(nest_ur_x, nest_ur_y)
        lr_lon, lr_lat = self.transformer_to_latlon.transform(nest_ur_x, nest_ll_y)
        ul_lon, ul_lat = self.transformer_to_latlon.transform(nest_ll_x, nest_ur_y)
        
        self.corners = {
            'll': (ll_lat, ll_lon),
            'lr': (lr_lat, lr_lon),
            'ur': (ur_lat, ur_lon),
            'ul': (ul_lat, ul_lon),
        }
        
        return [[ll_lat, ll_lon], [ur_lat, ur_lon]]
    
    def get_corner_polygon(self, use_square_image=False):
        """Get corners as a polygon for boundary display."""
        # Recalculate with the requested square_image setting
        self.get_domain_bounds(use_square_image=use_square_image)
        return [
            list(self.corners['ll']),
            list(self.corners['lr']),
            list(self.corners['ur']),
            list(self.corners['ul']),
            list(self.corners['ll']),
        ]


def create_domains():
    """Create domain objects with proper projection."""
    d1 = LambertConformalDomain(
        ref_lat=WRF_CONFIG['ref_lat'],
        ref_lon=WRF_CONFIG['ref_lon'],
        truelat1=WRF_CONFIG['truelat1'],
        truelat2=WRF_CONFIG['truelat2'],
        stand_lon=WRF_CONFIG['stand_lon'],
        dx=WRF_CONFIG['d1']['dx'],
        dy=WRF_CONFIG['d1']['dy'],
        e_we=WRF_CONFIG['d1']['e_we'],
        e_sn=WRF_CONFIG['d1']['e_sn'],
    )
    
    d2 = LambertConformalDomain(
        ref_lat=WRF_CONFIG['ref_lat'],
        ref_lon=WRF_CONFIG['ref_lon'],
        truelat1=WRF_CONFIG['truelat1'],
        truelat2=WRF_CONFIG['truelat2'],
        stand_lon=WRF_CONFIG['stand_lon'],
        dx=WRF_CONFIG['d2']['dx'],
        dy=WRF_CONFIG['d2']['dy'],
        e_we=WRF_CONFIG['d2']['e_we'],
        e_sn=WRF_CONFIG['d2']['e_sn'],
        parent=d1,
        i_parent_start=WRF_CONFIG['d2']['i_parent_start'],
        j_parent_start=WRF_CONFIG['d2']['j_parent_start'],
        parent_grid_ratio=WRF_CONFIG['d2']['parent_grid_ratio'],
    )
    
    return {'d1': d1, 'd2': d2}


# Calculate domain bounds at startup
# d1 (outer domain) has a non-square grid (80x100) but NCL generates square images,
# so we use use_square_image=True to get correct bounds for the image overlay
DOMAIN_OBJS = create_domains()
DOMAIN_BOUNDS = {
    'd1': {
        'bounds': DOMAIN_OBJS['d1'].get_domain_bounds(use_square_image=True),
        'polygon': DOMAIN_OBJS['d1'].get_corner_polygon(use_square_image=True),
    },
    'd2': {
        'bounds': DOMAIN_OBJS['d2'].get_domain_bounds(),
        'polygon': DOMAIN_OBJS['d2'].get_corner_polygon(),
    }
}


# Parameter descriptions
PARAMETER_INFO = {
    'wstar': 'Thermal Updraft Velocity (W*)',
    'bsratio': 'Buoyancy/Shear Ratio',
    'wstar_bsratio': 'W* with B/S Ratio',
    'hglider': 'Glider Height (MSL)',
    'dglider': 'Glider Height (AGL)',
    'hwcrit': 'Height of Critical Updraft (MSL)',
    'dwcrit': 'Height of Critical Updraft (AGL)',
    'hbl': 'BL Top Height (MSL)',
    'dbl': 'BL Depth (AGL)',
    'bltopvariab': 'BL Top Variability',
    'wblmaxmin': 'BL Max Up/Down Motion',
    'zwblmaxmin': 'Height of Max BL Up/Down',
    'sfcsunpct': 'Surface Sun %',
    'sfcshf': 'Surface Heat Flux',
    'sfctemp': 'Surface Temperature',
    'sfcdewpt': 'Surface Dewpoint',
    'sfcwind0': 'Surface Wind',
    'blwind': 'BL Average Wind',
    'bltopwind': 'BL Top Wind',
    'blwindshear': 'BL Wind Shear',
    'zsfclcl': 'Sfc LCL Height',
    'zsfclcldif': 'Sfc Cu Cloudbase (AGL)',
    'zsfclclmask': 'Sfc Cu Potential',
    'zblcl': 'BL Top LCL Height',
    'zblcldif': 'OD Cu Cloudbase (AGL)',
    'zblclmask': 'OD Cu Potential',
    'blicw': 'BL Cloud Ice+Water',
    'blcwbase': 'BL Cloud Base',
    'blcloudpct': 'BL Cloud %',
    'cfracl': 'Low Cloud Fraction',
    'cfracm': 'Mid Cloud Fraction',
    'cfrach': 'High Cloud Fraction',
    'rain1': '1hr Rain',
    'cape': 'CAPE',
    'press950': '950mb Wind',
    'press850': '850mb Wind',
    'press700': '700mb Wind',
    'press500': '500mb Wind',
    'stars': 'Star Rating',
    'xcspeed': 'XC Speed',
    'pfd_tot': 'Potential Flight Distance (Total)',
}

# Basic parameters shown in non-expert mode
BASIC_PARAMS = ['pfd_tot', 'xcspeed', 'wstar', 'sfcwind0', 'blcloudpct', 'hglider', 'zsfclclmask', 'stars']

# Sounding locations (from sitedata.ncl)
SOUNDING_SITES = {
    '3': {'name': 'Hamilton', 'lat': -37.7870, 'lon': 175.2793},
    '4': {'name': 'Taupo', 'lat': -38.6857, 'lon': 176.0702},
    '5': {'name': 'Rotorua', 'lat': -38.1368, 'lon': 176.2497},
    '6': {'name': 'Napier', 'lat': -39.4928, 'lon': 176.9120},
    '7': {'name': 'NewPlymouth', 'lat': -39.0556, 'lon': 174.0752},
    '8': {'name': 'Matamata', 'lat': -37.8100, 'lon': 175.7700},
}


def get_available_dates():
    """Get list of available forecast dates from OUT folder."""
    dates = []
    if os.path.exists(OUT_DIR):
        for item in sorted(os.listdir(OUT_DIR)):
            if os.path.isdir(os.path.join(OUT_DIR, item)) and re.match(r'\d{4}-\d{2}-\d{2}', item):
                dates.append(item)
    return dates


def get_available_data(date):
    """Get available parameters, times, and domains for a given date."""
    date_dir = os.path.join(OUT_DIR, date)
    if not os.path.exists(date_dir):
        return {'parameters': [], 'times': [], 'domains': []}
    
    parameters = set()
    times = set()
    domains = set()
    
    pattern = re.compile(r'(\w+)\.curr\.(\d{4})lst\.d(\d)\.body\.png')
    
    for filename in os.listdir(date_dir):
        match = pattern.match(filename)
        if match:
            parameters.add(match.group(1))
            times.add(match.group(2))
            domains.add(f'd{match.group(3)}')
    
    # Check for pfd_tot (special case - no time in filename)
    if os.path.exists(os.path.join(date_dir, 'pfd_tot.body.png')):
        parameters.add('pfd_tot')
    
    return {
        'parameters': sorted(list(parameters)),
        'times': sorted(list(times)),
        'domains': sorted(list(domains))
    }


# HTML Template - Map Only View
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RASP Weather Viewer - NZ</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        // Leaflet Distortable Image Overlay - renders image to 4 corner points
        L.DistortableImageOverlay = L.Layer.extend({
            initialize: function(url, corners, options) {
                this._url = url;
                this._corners = corners; // [topLeft, topRight, bottomRight, bottomLeft] as [lat,lng]
                L.setOptions(this, options);
            },
            
            onAdd: function(map) {
                this._map = map;
                
                if (!this._canvas) {
                    this._canvas = L.DomUtil.create('canvas', 'leaflet-image-layer leaflet-zoom-animated');
                }
                
                if (this.options.opacity) {
                    this._canvas.style.opacity = this.options.opacity;
                }
                
                this.getPane().appendChild(this._canvas);
                
                this._image = new Image();
                this._image.crossOrigin = '';
                this._image.onload = () => {
                    this._reset();
                };
                this._image.src = this._url;
                
                map.on('zoomanim', this._animateZoom, this);
                map.on('zoomend viewreset', this._reset, this);
            },
            
            onRemove: function(map) {
                L.DomUtil.remove(this._canvas);
                map.off('zoomanim', this._animateZoom, this);
                map.off('zoomend viewreset', this._reset, this);
            },
            
            setOpacity: function(opacity) {
                this._canvas.style.opacity = opacity;
            },
            
            setUrl: function(url) {
                this._url = url;
                this._image.src = url;
            },
            
            _animateZoom: function(e) {
                const scale = this._map.getZoomScale(e.zoom);
                const offset = this._map._latLngBoundsToNewLayerBounds(
                    L.latLngBounds(this._corners[3], this._corners[1]), 
                    e.zoom, 
                    e.center
                ).min;
                L.DomUtil.setTransform(this._canvas, offset, scale);
            },
            
            _reset: function() {
                if (!this._map || !this._image.complete) return;
                
                const map = this._map;
                const canvas = this._canvas;
                const ctx = canvas.getContext('2d');
                
                // Get pixel positions of corners in layer coordinates
                const corners = this._corners;
                const tl = map.latLngToLayerPoint(L.latLng(corners[0]));
                const tr = map.latLngToLayerPoint(L.latLng(corners[1]));
                const br = map.latLngToLayerPoint(L.latLng(corners[2]));
                const bl = map.latLngToLayerPoint(L.latLng(corners[3]));
                
                // Calculate bounding box
                const minX = Math.min(tl.x, tr.x, br.x, bl.x);
                const maxX = Math.max(tl.x, tr.x, br.x, bl.x);
                const minY = Math.min(tl.y, tr.y, br.y, bl.y);
                const maxY = Math.max(tl.y, tr.y, br.y, bl.y);
                
                const width = Math.ceil(maxX - minX);
                const height = Math.ceil(maxY - minY);
                
                canvas.width = width;
                canvas.height = height;
                canvas.style.width = width + 'px';
                canvas.style.height = height + 'px';
                
                // Position canvas at top-left of bounding box
                L.DomUtil.setPosition(canvas, L.point(minX, minY));
                
                // Adjust corner coordinates relative to canvas origin
                const tlAdj = {x: tl.x - minX, y: tl.y - minY};
                const trAdj = {x: tr.x - minX, y: tr.y - minY};
                const brAdj = {x: br.x - minX, y: br.y - minY};
                const blAdj = {x: bl.x - minX, y: bl.y - minY};
                
                ctx.clearRect(0, 0, width, height);
                
                const img = this._image;
                const w = img.width;
                const h = img.height;
                
                // Draw using two triangles for perspective transform
                this._drawTriangle(ctx, img,
                    0, 0, w, 0, 0, h,
                    tlAdj.x, tlAdj.y, trAdj.x, trAdj.y, blAdj.x, blAdj.y
                );
                this._drawTriangle(ctx, img,
                    w, 0, w, h, 0, h,
                    trAdj.x, trAdj.y, brAdj.x, brAdj.y, blAdj.x, blAdj.y
                );
            },
            
            _drawTriangle: function(ctx, img, x0, y0, x1, y1, x2, y2, sx0, sy0, sx1, sy1, sx2, sy2) {
                ctx.save();
                ctx.beginPath();
                ctx.moveTo(sx0, sy0);
                ctx.lineTo(sx1, sy1);
                ctx.lineTo(sx2, sy2);
                ctx.closePath();
                ctx.clip();
                
                const denom = x0 * (y2 - y1) - x1 * y2 + x2 * y1 + (x1 - x2) * y0;
                if (Math.abs(denom) < 0.01) {
                    ctx.restore();
                    return;
                }
                
                const m11 = -(y0 * (sx2 - sx1) - y1 * sx2 + y2 * sx1 + (y1 - y2) * sx0) / denom;
                const m12 = (y1 * sy2 + y0 * (sy1 - sy2) - y2 * sy1 + (y2 - y1) * sy0) / denom;
                const m21 = (x0 * (sx2 - sx1) - x1 * sx2 + x2 * sx1 + (x1 - x2) * sx0) / denom;
                const m22 = -(x1 * sy2 + x0 * (sy1 - sy2) - x2 * sy1 + (x2 - x1) * sy0) / denom;
                const dx = (x0 * (y2 * sx1 - y1 * sx2) + y0 * (x1 * sx2 - x2 * sx1) + (x2 * y1 - x1 * y2) * sx0) / denom;
                const dy = (x0 * (y2 * sy1 - y1 * sy2) + y0 * (x1 * sy2 - x2 * sy1) + (x2 * y1 - x1 * y2) * sy0) / denom;
                
                ctx.transform(m11, m12, m21, m22, dx, dy);
                ctx.drawImage(img, 0, 0);
                ctx.restore();
            }
        });
        
        L.distortableImageOverlay = function(url, corners, options) {
            return new L.DistortableImageOverlay(url, corners, options);
        };
    </script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
        }
        .controls {
            position: fixed;
            top: 10px;
            left: 10px;
            z-index: 1000;
            background: rgba(22, 33, 62, 0.95);
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            max-width: 320px;
        }
        .controls h2 {
            color: #e94560;
            margin-bottom: 15px;
            font-size: 1.1em;
        }
        .control-group {
            margin-bottom: 12px;
        }
        .control-group label {
            display: block;
            font-size: 0.75em;
            color: #aaa;
            text-transform: uppercase;
            margin-bottom: 4px;
        }
        select {
            width: 100%;
            background: #0f3460;
            color: #fff;
            border: 1px solid #e94560;
            padding: 8px;
            border-radius: 5px;
            font-size: 0.9em;
            cursor: pointer;
        }
        select:focus { outline: none; border-color: #fff; }
        select option { background: #16213e; }
        
        .time-slider-container {
            margin-top: 5px;
        }
        input[type="range"] {
            width: 100%;
            height: 6px;
            -webkit-appearance: none;
            background: #0f3460;
            border-radius: 3px;
            margin: 8px 0;
        }
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 18px;
            height: 18px;
            background: #e94560;
            border-radius: 50%;
            cursor: pointer;
        }
        .time-display {
            text-align: center;
            font-size: 1.4em;
            color: #e94560;
            font-weight: bold;
        }
        .play-controls {
            display: flex;
            gap: 8px;
            margin-top: 10px;
        }
        .play-btn {
            flex: 1;
            background: #e94560;
            color: white;
            border: none;
            padding: 8px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.9em;
        }
        .play-btn:hover { background: #ff6b6b; }
        .speed-select {
            width: 80px;
        }
        .expert-toggle {
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #444;
        }
        .toggle-label {
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            font-size: 0.9em;
        }
        .toggle-label input {
            width: 18px;
            height: 18px;
            cursor: pointer;
        }
        .opacity-control {
            margin-top: 10px;
        }
        .opacity-control input {
            width: 100%;
        }
        #map {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
        }
        .info-box {
            position: fixed;
            bottom: 10px;
            left: 10px;
            z-index: 1000;
            background: rgba(22, 33, 62, 0.9);
            padding: 10px 15px;
            border-radius: 8px;
            font-size: 0.85em;
            color: #aaa;
        }
        .header-box {
            position: fixed;
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            background: rgba(22, 33, 62, 0.95);
            padding: 8px;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }
        .header-box img {
            display: block;
            max-width: 600px;
            height: auto;
        }
        .legend-box {
            position: fixed;
            bottom: 10px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            background: rgba(22, 33, 62, 0.95);
            padding: 8px;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }
        .legend-box img {
            display: block;
            max-width: 600px;
            height: auto;
        }
        .time-nav {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 8px;
        }
        .time-nav-btn {
            background: #e94560;
            color: white;
            border: none;
            width: 36px;
            height: 36px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 1.2em;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .time-nav-btn:hover { background: #ff6b6b; }
        .time-nav-btn:disabled { background: #555; cursor: not-allowed; }
        .leaflet-control-attribution { display: none; }
        
        .sounding-popup {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 2000;
            background: rgba(22, 33, 62, 0.98);
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 4px 30px rgba(0,0,0,0.7);
            display: none;
        }
        .sounding-popup.active {
            display: block;
        }
        .sounding-popup img {
            max-width: 90vw;
            max-height: 80vh;
            display: block;
        }
        .sounding-popup .close-btn {
            position: absolute;
            top: 5px;
            right: 10px;
            background: #e94560;
            color: white;
            border: none;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.2em;
        }
        .sounding-popup .close-btn:hover {
            background: #ff6b6b;
        }
        .sounding-popup h3 {
            color: #e94560;
            margin: 0 0 10px 0;
            padding-right: 30px;
        }
        .sounding-marker {
            background: #e94560;
            border: 2px solid white;
            border-radius: 50%;
            width: 24px;
            height: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 12px;
            cursor: pointer;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
        }
        .sounding-marker:hover {
            background: #ff6b6b;
            transform: scale(1.1);
        }
    </style>
</head>
<body>
    <div id="map"></div>
    
    <div class="controls">
        <h2>🌤️ RASP NZ Forecast</h2>
        
        <div class="control-group">
            <label>Date</label>
            <select id="dateSelect"></select>
        </div>
        
        <div class="control-group">
            <label>Parameter</label>
            <select id="paramSelect"></select>
        </div>
        
        <div class="control-group">
            <label>Domain</label>
            <select id="domainSelect"></select>
        </div>
        
        <div class="control-group">
            <label>Time (Local)</label>
            <div class="time-slider-container">
                <input type="range" id="timeSlider" min="0" max="9" value="4">
                <div class="time-nav">
                    <button class="time-nav-btn" id="timePrev" title="Previous">◀</button>
                    <div class="time-display" id="timeDisplay" style="flex:1">--:--</div>
                    <button class="time-nav-btn" id="timeNext" title="Next">▶</button>
                </div>
            </div>
        </div>
        
        <div class="play-controls">
            <button class="play-btn" id="playBtn">▶ Play</button>
            <select id="speedSelect" class="speed-select">
                <option value="2000">Slow</option>
                <option value="1000" selected>Normal</option>
                <option value="500">Fast</option>
            </select>
        </div>
        
        <div class="control-group expert-toggle">
            <label class="toggle-label">
                <input type="checkbox" id="expertMode">
                <span>Expert Mode</span>
            </label>
        </div>
        
        <div class="control-group opacity-control">
            <label>Overlay Opacity: <span id="opacityValue">70%</span></label>
            <input type="range" id="opacitySlider" min="0" max="100" value="70">
        </div>
    </div>
    
    <div class="info-box" id="infoBox">Loading...</div>
    
    <div class="header-box" id="headerBox">
        <img id="headerImg" src="" alt="Header">
    </div>
    
    <div class="legend-box" id="legendBox">
        <img id="legendImg" src="" alt="Scale">
    </div>
    
    <div class="sounding-popup" id="soundingPopup">
        <button class="close-btn" id="closeSounding">×</button>
        <h3 id="soundingTitle">Sounding</h3>
        <img id="soundingImg" src="" alt="Sounding">
    </div>
    
    <script>
        // State
        let currentData = { parameters: [], times: [], domains: [] };
        let map = null;
        let imageOverlay = null;
        let domainPolygons = {};
        let isPlaying = false;
        let playInterval = null;
        let viewInitialized = false;
        let currentDomain = null;
        let soundingMarkers = [];
        let availableSoundings = [];
        let currentSoundingSite = null; // Track which sounding is currently shown
        let expertMode = false;
        
        // Parameter descriptions
        const paramInfo = {{ param_info | tojson }};
        
        // Basic parameters shown in non-expert mode
        const basicParams = {{ basic_params | tojson }};
        
        // Domain bounds from server (proper Lambert projection)
        const domainData = {{ domain_bounds | tojson }};
        
        // Sounding site locations
        const soundingSites = {{ sounding_sites | tojson }};
        
        // Initialize map
        function initMap() {
            map = L.map('map', {
                center: [-37.81, 175.77],
                zoom: 9,
                zoomControl: true
            });
            
            // Base layers
            const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19
            });
            
            const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                maxZoom: 19
            });
            
            const topo = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
                maxZoom: 17
            });
            
            osm.addTo(map);
            
            L.control.layers({
                'OpenStreetMap': osm,
                'Satellite': satellite,
                'Topographic': topo
            }, {}, {position: 'topright'}).addTo(map);
            
            // Add domain boundary polygons
            Object.keys(domainData).forEach(domain => {
                const polygon = domainData[domain].polygon;
                const color = domain === 'd1' ? '#e94560' : '#4ecdc4';
                
                domainPolygons[domain] = L.polygon(polygon, {
                    color: color,
                    weight: 2,
                    fill: false,
                    dashArray: domain === 'd1' ? '8, 4' : null
                }).addTo(map);
                
                domainPolygons[domain].bindPopup(
                    domain === 'd1' ? 'Outer Domain (6km)' : 'Inner Domain (2km)'
                );
            });
            
            // Add markers for key locations
            const locations = [
                {name: 'Matamata GC', lat: -37.81, lon: 175.77, icon: '🪂'},
                {name: 'Auckland', lat: -36.8485, lon: 174.7633, icon: '🏙️'},
                {name: 'Hamilton', lat: -37.787, lon: 175.2793, icon: '🏙️'},
                {name: 'Taupo', lat: -38.6857, lon: 176.0702, icon: '🏔️'},
                {name: 'Rotorua', lat: -38.1368, lon: 176.2497, icon: '♨️'}
            ];
            
            locations.forEach(loc => {
                L.marker([loc.lat, loc.lon])
                    .addTo(map)
                    .bindPopup(`<b>${loc.name}</b>`);
            });
        }
        
        // Create sounding markers
        function createSoundingMarkers() {
            // Remove existing markers
            soundingMarkers.forEach(m => map.removeLayer(m));
            soundingMarkers = [];
            
            Object.keys(soundingSites).forEach(siteId => {
                if (!availableSoundings.includes(siteId)) return;
                
                const site = soundingSites[siteId];
                const icon = L.divIcon({
                    className: 'sounding-marker',
                    html: `<div class="sounding-marker">S</div>`,
                    iconSize: [24, 24],
                    iconAnchor: [12, 12]
                });
                
                const marker = L.marker([site.lat, site.lon], { icon: icon })
                    .addTo(map)
                    .bindTooltip(`${site.name} Sounding`, { direction: 'top' })
                    .on('click', () => showSounding(siteId, site.name));
                
                soundingMarkers.push(marker);
            });
        }
        
        // Show sounding popup
        function showSounding(siteId, siteName) {
            const date = document.getElementById('dateSelect').value;
            const domain = document.getElementById('domainSelect').value;
            const timeIndex = parseInt(document.getElementById('timeSlider').value);
            const time = currentData.times[timeIndex];
            
            if (!date || !time) return;
            
            currentSoundingSite = { id: siteId, name: siteName };
            
            const url = `/api/sounding/${date}/${siteId}/${time}/${domain}`;
            
            document.getElementById('soundingTitle').textContent = `${siteName} Sounding - ${time.substring(0,2)}:${time.substring(2,4)}`;
            document.getElementById('soundingImg').src = url;
            document.getElementById('soundingPopup').classList.add('active');
        }
        
        // Update sounding if popup is open
        function updateSoundingIfOpen() {
            if (!currentSoundingSite) return;
            if (!document.getElementById('soundingPopup').classList.contains('active')) return;
            
            const date = document.getElementById('dateSelect').value;
            const domain = document.getElementById('domainSelect').value;
            const timeIndex = parseInt(document.getElementById('timeSlider').value);
            const time = currentData.times[timeIndex];
            
            if (!date || !time) return;
            
            const url = `/api/sounding/${date}/${currentSoundingSite.id}/${time}/${domain}`;
            
            document.getElementById('soundingTitle').textContent = `${currentSoundingSite.name} Sounding - ${time.substring(0,2)}:${time.substring(2,4)}`;
            document.getElementById('soundingImg').src = url;
        }
        
        // Close sounding popup
        document.getElementById('closeSounding').addEventListener('click', () => {
            document.getElementById('soundingPopup').classList.remove('active');
            currentSoundingSite = null;
        });
        
        // Close on click outside
        document.getElementById('soundingPopup').addEventListener('click', (e) => {
            if (e.target.id === 'soundingPopup') {
                document.getElementById('soundingPopup').classList.remove('active');
                currentSoundingSite = null;
            }
        });
        
        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                document.getElementById('soundingPopup').classList.remove('active');
                currentSoundingSite = null;
            }
        });
        
        // Load available dates
        async function loadDates() {
            const response = await fetch('/api/dates');
            const dates = await response.json();
            
            const select = document.getElementById('dateSelect');
            select.innerHTML = '';
            
            if (dates.length === 0) {
                select.innerHTML = '<option>No data</option>';
                return;
            }
            
            dates.forEach(date => {
                const option = document.createElement('option');
                option.value = date;
                option.textContent = formatDate(date);
                select.appendChild(option);
            });
            
            select.value = dates[dates.length - 1];
            loadDateData(dates[dates.length - 1]);
        }
        
        function formatDate(dateStr) {
            const date = new Date(dateStr);
            return date.toLocaleDateString('en-NZ', {
                weekday: 'short', month: 'short', day: 'numeric'
            });
        }
        
        // Update parameter dropdown based on expert mode
        function updateParameterDropdown() {
            const paramSelect = document.getElementById('paramSelect');
            const currentParam = paramSelect.value;
            paramSelect.innerHTML = '';
            
            // Filter parameters based on expert mode
            let paramsToShow = currentData.parameters;
            if (!expertMode) {
                paramsToShow = currentData.parameters.filter(p => basicParams.includes(p));
            }
            
            paramsToShow.forEach(param => {
                const option = document.createElement('option');
                option.value = param;
                option.textContent = paramInfo[param] || param;
                paramSelect.appendChild(option);
            });
            
            // Restore selection if still available, otherwise default to first
            if (paramsToShow.includes(currentParam)) {
                paramSelect.value = currentParam;
            } else if (paramsToShow.includes('pfd_tot')) {
                paramSelect.value = 'pfd_tot';
            } else if (paramsToShow.length > 0) {
                paramSelect.value = paramsToShow[0];
            }
        }
        
        async function loadDateData(date) {
            // Save current selections before updating
            const paramSelect = document.getElementById('paramSelect');
            const domainSelect = document.getElementById('domainSelect');
            const timeSlider = document.getElementById('timeSlider');
            
            const prevParam = paramSelect.value;
            const prevDomain = domainSelect.value;
            const prevTimeIndex = parseInt(timeSlider.value);
            const prevTime = currentData.times[prevTimeIndex];
            
            const response = await fetch(`/api/data/${date}`);
            currentData = await response.json();
            
            // Load available soundings for this date
            const soundingsResponse = await fetch(`/api/soundings/${date}`);
            availableSoundings = await soundingsResponse.json();
            
            // Update parameter dropdown based on expert mode
            updateParameterDropdown();
            
            // Restore previous parameter if available
            const currentParams = [...document.getElementById('paramSelect').options].map(o => o.value);
            if (prevParam && currentParams.includes(prevParam)) {
                paramSelect.value = prevParam;
            }
            
            // Update domain dropdown
            domainSelect.innerHTML = '';
            currentData.domains.forEach(domain => {
                const option = document.createElement('option');
                option.value = domain;
                option.textContent = domain === 'd1' ? 'Outer (6km)' : 'Inner (2km)';
                domainSelect.appendChild(option);
            });
            
            // Restore previous domain if available, otherwise default to d2
            if (prevDomain && currentData.domains.includes(prevDomain)) {
                domainSelect.value = prevDomain;
            } else if (currentData.domains.includes('d2')) {
                domainSelect.value = 'd2';
            }
            
            // Update time slider
            timeSlider.max = currentData.times.length - 1;
            
            // Restore previous time if available, otherwise use middle
            if (prevTime && currentData.times.includes(prevTime)) {
                timeSlider.value = currentData.times.indexOf(prevTime);
            } else {
                timeSlider.value = Math.floor(currentData.times.length / 2);
            }
            
            updateTimeDisplay();
            updateImage();
            
            // Create sounding markers
            if (map) {
                createSoundingMarkers();
            }
            
            // Update sounding if popup is open
            updateSoundingIfOpen();
        }
        
        function updateTimeDisplay() {
            const timeSlider = document.getElementById('timeSlider');
            const timeIndex = parseInt(timeSlider.value);
            const time = currentData.times[timeIndex];
            
            if (time) {
                const hours = time.substring(0, 2);
                const mins = time.substring(2, 4);
                document.getElementById('timeDisplay').textContent = `${hours}:${mins}`;
            }
        }
        
        async function updateImage() {
            const date = document.getElementById('dateSelect').value;
            const param = document.getElementById('paramSelect').value;
            const domain = document.getElementById('domainSelect').value;
            const timeIndex = parseInt(document.getElementById('timeSlider').value);
            const time = currentData.times[timeIndex];
            const opacity = parseInt(document.getElementById('opacitySlider').value) / 100;
            
            if (!date || !param || !domain || !time) return;
            
            const url = `/api/image/${date}/${param}/${time}/${domain}`;
            
            // Remove existing overlay
            if (imageOverlay) {
                map.removeLayer(imageOverlay);
            }
            
            // Get polygon corners for this domain (ul, ur, lr, ll order for distortable)
            const polygon = domainData[domain]?.polygon;
            const bounds = domainData[domain]?.bounds;
            if (!polygon || !bounds) return;
            
            // Polygon is: ll, lr, ur, ul, ll
            // Distortable expects: topLeft, topRight, bottomRight, bottomLeft
            const corners = [
                polygon[3], // ul -> topLeft
                polygon[2], // ur -> topRight
                polygon[1], // lr -> bottomRight
                polygon[0], // ll -> bottomLeft
            ];
            
            // Create distortable image overlay with 4 corners
            imageOverlay = L.distortableImageOverlay(url, corners, {
                opacity: opacity
            });
            
            imageOverlay.addTo(map);
            
            // Update info box
            const paramName = paramInfo[param] || param;
            document.getElementById('infoBox').textContent = 
                `${paramName} | ${time.substring(0,2)}:${time.substring(2,4)} NZDT | ${domain === 'd1' ? '6km' : '2km'}`;
            
            // Update legend image
            const legendUrl = `/api/legend/${date}/${param}/${time}/${domain}`;
            document.getElementById('legendImg').src = legendUrl;
            
            // Update header image
            const headerUrl = `/api/header/${date}/${param}/${time}/${domain}`;
            document.getElementById('headerImg').src = headerUrl;
            
            // Only fit bounds on first load or domain change
            if (!viewInitialized || currentDomain !== domain) {
                map.fitBounds(bounds, { padding: [50, 50] });
                viewInitialized = true;
                currentDomain = domain;
            }
        }
        
        function updateOpacity() {
            const opacity = parseInt(document.getElementById('opacitySlider').value) / 100;
            document.getElementById('opacityValue').textContent = Math.round(opacity * 100) + '%';
            if (imageOverlay) {
                imageOverlay.setOpacity(opacity);
            }
        }
        
        function togglePlay() {
            const btn = document.getElementById('playBtn');
            
            if (isPlaying) {
                isPlaying = false;
                btn.textContent = '▶ Play';
                if (playInterval) {
                    clearInterval(playInterval);
                    playInterval = null;
                }
            } else {
                isPlaying = true;
                btn.textContent = '⏸ Pause';
                
                const speed = parseInt(document.getElementById('speedSelect').value);
                playInterval = setInterval(() => {
                    const slider = document.getElementById('timeSlider');
                    let value = parseInt(slider.value);
                    value = (value + 1) % (parseInt(slider.max) + 1);
                    slider.value = value;
                    updateTimeDisplay();
                    updateImage();
                }, speed);
            }
        }
        
        // Event listeners
        document.getElementById('dateSelect').addEventListener('change', (e) => loadDateData(e.target.value));
        document.getElementById('paramSelect').addEventListener('change', updateImage);
        document.getElementById('domainSelect').addEventListener('change', () => {
            updateImage();
            updateSoundingIfOpen();
        });
        document.getElementById('expertMode').addEventListener('change', (e) => {
            expertMode = e.target.checked;
            updateParameterDropdown();
            updateImage();
        });
        document.getElementById('timeSlider').addEventListener('input', () => {
            updateTimeDisplay();
            updateImage();
            updateSoundingIfOpen();
        });
        document.getElementById('opacitySlider').addEventListener('input', updateOpacity);
        document.getElementById('playBtn').addEventListener('click', togglePlay);
        
        // Time arrow navigation
        document.getElementById('timePrev').addEventListener('click', () => {
            const slider = document.getElementById('timeSlider');
            if (parseInt(slider.value) > 0) {
                slider.value = parseInt(slider.value) - 1;
                updateTimeDisplay();
                updateImage();
                updateSoundingIfOpen();
            }
        });
        document.getElementById('timeNext').addEventListener('click', () => {
            const slider = document.getElementById('timeSlider');
            if (parseInt(slider.value) < parseInt(slider.max)) {
                slider.value = parseInt(slider.value) + 1;
                updateTimeDisplay();
                updateImage();
                updateSoundingIfOpen();
            }
        });
        
        // Initialize
        initMap();
        loadDates();
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    """Serve the main viewer page."""
    return render_template_string(
        HTML_TEMPLATE, 
        param_info=PARAMETER_INFO,
        basic_params=BASIC_PARAMS,
        domain_bounds=DOMAIN_BOUNDS,
        sounding_sites=SOUNDING_SITES
    )


@app.route('/api/dates')
def api_dates():
    """Get available forecast dates."""
    return jsonify(get_available_dates())


@app.route('/api/data/<date>')
def api_data(date):
    """Get available parameters, times, and domains for a date."""
    return jsonify(get_available_data(date))


@app.route('/api/image/<date>/<parameter>/<time>/<domain>')
def api_image(date, parameter, time, domain):
    """Serve a forecast image - always use .body.png (the map data without borders)."""
    # Special case for pfd_tot (no time in filename)
    if parameter == 'pfd_tot':
        path = os.path.join(OUT_DIR, date, 'pfd_tot.body.png')
        if os.path.exists(path):
            return send_file(path, mimetype='image/png')
        return "Image not found", 404
    
    # Use .body.png which contains just the map data (no borders/labels)
    path = os.path.join(OUT_DIR, date, f"{parameter}.curr.{time}lst.{domain}.body.png")
    if os.path.exists(path):
        return send_file(path, mimetype='image/png')
    
    return "Image not found", 404


@app.route('/api/bounds')
def api_bounds():
    """Get domain bounds."""
    return jsonify(DOMAIN_BOUNDS)


@app.route('/api/legend/<date>/<parameter>/<time>/<domain>')
def api_legend(date, parameter, time, domain):
    """Serve the legend/scale image (foot.png)."""
    # Special case for pfd_tot (no time in filename)
    if parameter == 'pfd_tot':
        path = os.path.join(OUT_DIR, date, 'pfd_tot.foot.png')
        if os.path.exists(path):
            return send_file(path, mimetype='image/png')
        return "Legend not found", 404
    
    path = os.path.join(OUT_DIR, date, f"{parameter}.curr.{time}lst.{domain}.foot.png")
    if os.path.exists(path):
        return send_file(path, mimetype='image/png')
    
    return "Legend not found", 404


@app.route('/api/header/<date>/<parameter>/<time>/<domain>')
def api_header(date, parameter, time, domain):
    """Serve the header image (head.png)."""
    # Special case for pfd_tot (no time in filename)
    if parameter == 'pfd_tot':
        path = os.path.join(OUT_DIR, date, 'pfd_tot.head.png')
        if os.path.exists(path):
            return send_file(path, mimetype='image/png')
        return "Header not found", 404
    
    path = os.path.join(OUT_DIR, date, f"{parameter}.curr.{time}lst.{domain}.head.png")
    if os.path.exists(path):
        return send_file(path, mimetype='image/png')
    
    return "Header not found", 404


@app.route('/api/sounding/<date>/<site_id>/<time>/<domain>')
def api_sounding(date, site_id, time, domain):
    """Serve a sounding image."""
    path = os.path.join(OUT_DIR, date, f"sounding{site_id}.curr.{time}lst.{domain}.png")
    if os.path.exists(path):
        return send_file(path, mimetype='image/png')
    return "Sounding not found", 404


@app.route('/api/soundings/<date>')
def api_soundings(date):
    """Get available soundings for a date."""
    date_dir = os.path.join(OUT_DIR, date)
    if not os.path.exists(date_dir):
        return jsonify([])
    
    soundings = set()
    pattern = re.compile(r'sounding(\d+)\.curr\.\d{4}lst\.d\d\.png')
    
    for filename in os.listdir(date_dir):
        match = pattern.match(filename)
        if match:
            soundings.add(match.group(1))
    
    return jsonify(sorted(list(soundings)))


if __name__ == '__main__':
    print(f"\n🌤️  RASP Weather Viewer")
    print(f"   Results: {RESULTS_DIR}")
    print(f"   Dates: {get_available_dates()}")
    print(f"\n   Domain d1 bounds: {DOMAIN_BOUNDS['d1']['bounds']}")
    print(f"   Domain d2 bounds: {DOMAIN_BOUNDS['d2']['bounds']}")
    print(f"\n   Open http://localhost:8080\n")
    
    app.run(host='0.0.0.0', port=8080, debug=True)
