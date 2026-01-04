#!/usr/bin/env python3
"""
Static Site Generator for RASP Weather Viewer
Generates a GitHub Pages compatible static site from forecast data.

Usage:
    python generate_static_site.py

This will create a 'docs/' folder with:
    - index.html (the viewer)
    - data/[date]/[images] (all forecast images)
    - data/manifest.json (list of available data)
"""

import os
import re
import json
import shutil
from pathlib import Path

try:
    import pyproj
except ImportError:
    print("Installing pyproj...")
    os.system("pip install pyproj")
    import pyproj

# Configuration
RESULTS_DIR = '/Users/georgedowning/Desktop/Rasp_complete/results'
OUT_DIR = os.path.join(RESULTS_DIR, 'OUT')
DOCS_DIR = '/Users/georgedowning/Desktop/Rasp_complete/docs'

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
        'e_we': 70, 'e_sn': 70,
        'i_parent_start': 25, 'j_parent_start': 52,
        'parent_grid_ratio': 3,
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

# Sounding locations
SOUNDING_SITES = {
    '3': {'name': 'Hamilton', 'lat': -37.7870, 'lon': 175.2793},
    '4': {'name': 'Taupo', 'lat': -38.6857, 'lon': 176.0702},
    '5': {'name': 'Rotorua', 'lat': -38.1368, 'lon': 176.2497},
    '6': {'name': 'Napier', 'lat': -39.4928, 'lon': 176.9120},
    '7': {'name': 'NewPlymouth', 'lat': -39.0556, 'lon': 174.0752},
    '8': {'name': 'Matamata', 'lat': -37.8100, 'lon': 175.7700},
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


def get_available_dates():
    """Get list of available forecast dates from OUT folder."""
    dates = []
    if os.path.exists(OUT_DIR):
        for item in sorted(os.listdir(OUT_DIR)):
            if os.path.isdir(os.path.join(OUT_DIR, item)) and re.match(r'\d{4}-\d{2}-\d{2}', item):
                dates.append(item)
    return dates


def get_available_data(date):
    """Get available parameters, times, domains, and soundings for a given date."""
    date_dir = os.path.join(OUT_DIR, date)
    if not os.path.exists(date_dir):
        return {'parameters': [], 'times': [], 'domains': [], 'soundings': []}
    
    parameters = set()
    times = set()
    domains = set()
    soundings = set()
    
    pattern = re.compile(r'(\w+)\.curr\.(\d{4})lst\.d(\d)\.body\.png')
    sounding_pattern = re.compile(r'sounding(\d+)\.curr\.\d{4}lst\.d\d\.png')
    
    for filename in os.listdir(date_dir):
        match = pattern.match(filename)
        if match:
            parameters.add(match.group(1))
            times.add(match.group(2))
            domains.add(f'd{match.group(3)}')
        
        sounding_match = sounding_pattern.match(filename)
        if sounding_match:
            soundings.add(sounding_match.group(1))
    
    # Check for pfd_tot (special case - no time in filename)
    if os.path.exists(os.path.join(date_dir, 'pfd_tot.body.png')):
        parameters.add('pfd_tot')
    
    return {
        'parameters': sorted(list(parameters)),
        'times': sorted(list(times)),
        'domains': sorted(list(domains)),
        'soundings': sorted(list(soundings))
    }


def copy_images(date, dest_dir):
    """Copy all images for a date to the destination directory."""
    src_dir = os.path.join(OUT_DIR, date)
    if not os.path.exists(src_dir):
        return 0
    
    os.makedirs(dest_dir, exist_ok=True)
    count = 0
    
    for filename in os.listdir(src_dir):
        if filename.endswith('.png'):
            src_path = os.path.join(src_dir, filename)
            dest_path = os.path.join(dest_dir, filename)
            shutil.copy2(src_path, dest_path)
            count += 1
    
    return count


def generate_html(domain_bounds, manifest):
    """Generate the static HTML viewer."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RASP Weather Viewer - NZ</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        // Leaflet Distortable Image Overlay - renders image to 4 corner points
        L.DistortableImageOverlay = L.Layer.extend({{
            initialize: function(url, corners, options) {{
                this._url = url;
                this._corners = corners;
                L.setOptions(this, options);
            }},
            
            onAdd: function(map) {{
                this._map = map;
                
                if (!this._canvas) {{
                    this._canvas = L.DomUtil.create('canvas', 'leaflet-image-layer leaflet-zoom-animated');
                }}
                
                if (this.options.opacity) {{
                    this._canvas.style.opacity = this.options.opacity;
                }}
                
                this.getPane().appendChild(this._canvas);
                
                this._image = new Image();
                this._image.crossOrigin = '';
                this._image.onload = () => {{
                    this._reset();
                }};
                this._image.src = this._url;
                
                map.on('zoomanim', this._animateZoom, this);
                map.on('zoomend viewreset', this._reset, this);
            }},
            
            onRemove: function(map) {{
                L.DomUtil.remove(this._canvas);
                map.off('zoomanim', this._animateZoom, this);
                map.off('zoomend viewreset', this._reset, this);
            }},
            
            setOpacity: function(opacity) {{
                this._canvas.style.opacity = opacity;
            }},
            
            setUrl: function(url) {{
                this._url = url;
                this._image.src = url;
            }},
            
            _animateZoom: function(e) {{
                const scale = this._map.getZoomScale(e.zoom);
                const offset = this._map._latLngBoundsToNewLayerBounds(
                    L.latLngBounds(this._corners[3], this._corners[1]), 
                    e.zoom, 
                    e.center
                ).min;
                L.DomUtil.setTransform(this._canvas, offset, scale);
            }},
            
            _reset: function() {{
                if (!this._map || !this._image.complete) return;
                
                const map = this._map;
                const canvas = this._canvas;
                const ctx = canvas.getContext('2d');
                
                const corners = this._corners;
                const tl = map.latLngToLayerPoint(L.latLng(corners[0]));
                const tr = map.latLngToLayerPoint(L.latLng(corners[1]));
                const br = map.latLngToLayerPoint(L.latLng(corners[2]));
                const bl = map.latLngToLayerPoint(L.latLng(corners[3]));
                
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
                
                L.DomUtil.setPosition(canvas, L.point(minX, minY));
                
                const tlAdj = {{x: tl.x - minX, y: tl.y - minY}};
                const trAdj = {{x: tr.x - minX, y: tr.y - minY}};
                const brAdj = {{x: br.x - minX, y: br.y - minY}};
                const blAdj = {{x: bl.x - minX, y: bl.y - minY}};
                
                ctx.clearRect(0, 0, width, height);
                
                const img = this._image;
                const w = img.width;
                const h = img.height;
                
                this._drawTriangle(ctx, img,
                    0, 0, w, 0, 0, h,
                    tlAdj.x, tlAdj.y, trAdj.x, trAdj.y, blAdj.x, blAdj.y
                );
                this._drawTriangle(ctx, img,
                    w, 0, w, h, 0, h,
                    trAdj.x, trAdj.y, brAdj.x, brAdj.y, blAdj.x, blAdj.y
                );
            }},
            
            _drawTriangle: function(ctx, img, x0, y0, x1, y1, x2, y2, sx0, sy0, sx1, sy1, sx2, sy2) {{
                ctx.save();
                ctx.beginPath();
                ctx.moveTo(sx0, sy0);
                ctx.lineTo(sx1, sy1);
                ctx.lineTo(sx2, sy2);
                ctx.closePath();
                ctx.clip();
                
                const denom = x0 * (y2 - y1) - x1 * y2 + x2 * y1 + (x1 - x2) * y0;
                if (Math.abs(denom) < 0.01) {{
                    ctx.restore();
                    return;
                }}
                
                const m11 = -(y0 * (sx2 - sx1) - y1 * sx2 + y2 * sx1 + (y1 - y2) * sx0) / denom;
                const m12 = (y1 * sy2 + y0 * (sy1 - sy2) - y2 * sy1 + (y2 - y1) * sy0) / denom;
                const m21 = (x0 * (sx2 - sx1) - x1 * sx2 + x2 * sx1 + (x1 - x2) * sx0) / denom;
                const m22 = -(x1 * sy2 + x0 * (sy1 - sy2) - x2 * sy1 + (x2 - x1) * sy0) / denom;
                const dx = (x0 * (y2 * sx1 - y1 * sx2) + y0 * (x1 * sx2 - x2 * sx1) + (x2 * y1 - x1 * y2) * sx0) / denom;
                const dy = (x0 * (y2 * sy1 - y1 * sy2) + y0 * (x1 * sy2 - x2 * sy1) + (x2 * y1 - x1 * y2) * sy0) / denom;
                
                ctx.transform(m11, m12, m21, m22, dx, dy);
                ctx.drawImage(img, 0, 0);
                ctx.restore();
            }}
        }});
        
        L.distortableImageOverlay = function(url, corners, options) {{
            return new L.DistortableImageOverlay(url, corners, options);
        }};
    </script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
        }}
        .controls {{
            position: fixed;
            top: 10px;
            left: 10px;
            z-index: 1000;
            background: rgba(22, 33, 62, 0.95);
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            max-width: 320px;
        }}
        .controls h2 {{
            color: #e94560;
            margin-bottom: 15px;
            font-size: 1.1em;
        }}
        .control-group {{
            margin-bottom: 12px;
        }}
        .control-group label {{
            display: block;
            font-size: 0.75em;
            color: #aaa;
            text-transform: uppercase;
            margin-bottom: 4px;
        }}
        select {{
            width: 100%;
            background: #0f3460;
            color: #fff;
            border: 1px solid #e94560;
            padding: 8px;
            border-radius: 5px;
            font-size: 0.9em;
            cursor: pointer;
        }}
        select:focus {{ outline: none; border-color: #fff; }}
        select option {{ background: #16213e; }}
        
        .time-slider-container {{
            margin-top: 5px;
        }}
        input[type="range"] {{
            width: 100%;
            height: 6px;
            -webkit-appearance: none;
            background: #0f3460;
            border-radius: 3px;
            margin: 8px 0;
        }}
        input[type="range"]::-webkit-slider-thumb {{
            -webkit-appearance: none;
            width: 18px;
            height: 18px;
            background: #e94560;
            border-radius: 50%;
            cursor: pointer;
        }}
        .time-display {{
            text-align: center;
            font-size: 1.4em;
            color: #e94560;
            font-weight: bold;
        }}
        .play-controls {{
            display: flex;
            gap: 8px;
            margin-top: 10px;
        }}
        .play-btn {{
            flex: 1;
            background: #e94560;
            color: white;
            border: none;
            padding: 8px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.9em;
        }}
        .play-btn:hover {{ background: #ff6b6b; }}
        .speed-select {{
            width: 80px;
        }}
        .opacity-control {{
            margin-top: 10px;
        }}
        .opacity-control input {{
            width: 100%;
        }}
        #map {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
        }}
        .info-box {{
            position: fixed;
            bottom: 10px;
            left: 10px;
            z-index: 1000;
            background: rgba(22, 33, 62, 0.9);
            padding: 10px 15px;
            border-radius: 8px;
            font-size: 0.85em;
            color: #aaa;
        }}
        .header-box {{
            position: fixed;
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            background: rgba(22, 33, 62, 0.95);
            padding: 8px;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }}
        .header-box img {{
            display: block;
            max-width: 600px;
            height: auto;
        }}
        .legend-box {{
            position: fixed;
            bottom: 10px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            background: rgba(22, 33, 62, 0.95);
            padding: 8px;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }}
        .legend-box img {{
            display: block;
            max-width: 600px;
            height: auto;
        }}
        .time-nav {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 8px;
        }}
        .time-nav-btn {{
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
        }}
        .time-nav-btn:hover {{ background: #ff6b6b; }}
        .time-nav-btn:disabled {{ background: #555; cursor: not-allowed; }}
        .leaflet-control-attribution {{ display: none; }}
        
        .sounding-popup {{
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
        }}
        .sounding-popup.active {{
            display: block;
        }}
        .sounding-popup img {{
            max-width: 90vw;
            max-height: 80vh;
            display: block;
        }}
        .sounding-popup .close-btn {{
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
        }}
        .sounding-popup .close-btn:hover {{
            background: #ff6b6b;
        }}
        .sounding-popup h3 {{
            color: #e94560;
            margin: 0 0 10px 0;
            padding-right: 30px;
        }}
        .sounding-marker {{
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
        }}
        .sounding-marker:hover {{
            background: #ff6b6b;
            transform: scale(1.1);
        }}
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
        // =====================================================
        // EMBEDDED DATA - Generated by static site generator
        // =====================================================
        
        // Parameter descriptions
        const paramInfo = {json.dumps(PARAMETER_INFO)};
        
        // Domain bounds (pre-calculated Lambert projection)
        const domainData = {json.dumps(domain_bounds)};
        
        // Sounding site locations
        const soundingSites = {json.dumps(SOUNDING_SITES)};
        
        // Available data manifest
        const manifest = {json.dumps(manifest)};
        
        // =====================================================
        // APPLICATION CODE
        // =====================================================
        
        // State
        let currentData = {{ parameters: [], times: [], domains: [], soundings: [] }};
        let map = null;
        let imageOverlay = null;
        let domainPolygons = {{}};
        let isPlaying = false;
        let playInterval = null;
        let viewInitialized = false;
        let currentDomain = null;
        let soundingMarkers = [];
        let availableSoundings = [];
        let currentSoundingSite = null;
        
        // Get base path for images (works for both local and GitHub Pages)
        function getBasePath() {{
            const path = window.location.pathname;
            if (path.includes('/docs/')) {{
                return path.substring(0, path.indexOf('/docs/') + 6);
            }}
            return path.substring(0, path.lastIndexOf('/') + 1);
        }}
        
        const basePath = getBasePath();
        
        // Initialize map
        function initMap() {{
            map = L.map('map', {{
                center: [-37.81, 175.77],
                zoom: 9,
                zoomControl: true
            }});
            
            const osm = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19
            }});
            
            const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                maxZoom: 19
            }});
            
            const topo = L.tileLayer('https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 17
            }});
            
            osm.addTo(map);
            
            L.control.layers({{
                'OpenStreetMap': osm,
                'Satellite': satellite,
                'Topographic': topo
            }}, {{}}, {{position: 'topright'}}).addTo(map);
            
            // Add domain boundary polygons
            for (const [domainId, data] of Object.entries(domainData)) {{
                const polygon = L.polygon(data.polygon, {{
                    color: domainId === 'd1' ? '#e94560' : '#4ecdc4',
                    weight: 2,
                    fillOpacity: 0,
                    dashArray: domainId === 'd1' ? '10, 5' : null
                }});
                domainPolygons[domainId] = polygon;
            }}
        }}
        
        // Load dates into selector
        function loadDates() {{
            const select = document.getElementById('dateSelect');
            select.innerHTML = '';
            
            const dates = Object.keys(manifest).sort().reverse();
            
            dates.forEach(date => {{
                const option = document.createElement('option');
                option.value = date;
                option.textContent = date;
                select.appendChild(option);
            }});
            
            if (dates.length > 0) {{
                loadDateData(dates[0]);
            }}
        }}
        
        // Load data for a specific date
        function loadDateData(date) {{
            currentData = manifest[date] || {{ parameters: [], times: [], domains: [], soundings: [] }};
            availableSoundings = currentData.soundings || [];
            
            // Update parameter dropdown
            const paramSelect = document.getElementById('paramSelect');
            const currentParam = paramSelect.value;
            paramSelect.innerHTML = '';
            
            currentData.parameters.forEach(p => {{
                const option = document.createElement('option');
                option.value = p;
                option.textContent = paramInfo[p] || p;
                paramSelect.appendChild(option);
            }});
            
            if (currentData.parameters.includes(currentParam)) {{
                paramSelect.value = currentParam;
            }}
            
            // Update domain dropdown
            const domainSelect = document.getElementById('domainSelect');
            const currentDomainVal = domainSelect.value;
            domainSelect.innerHTML = '';
            
            currentData.domains.forEach(d => {{
                const option = document.createElement('option');
                option.value = d;
                option.textContent = d === 'd1' ? 'Domain 1 (6km)' : 'Domain 2 (2km)';
                domainSelect.appendChild(option);
            }});
            
            if (currentData.domains.includes(currentDomainVal)) {{
                domainSelect.value = currentDomainVal;
            }} else if (currentData.domains.includes('d2')) {{
                domainSelect.value = 'd2';
            }}
            
            // Update time slider
            const timeSlider = document.getElementById('timeSlider');
            timeSlider.max = currentData.times.length - 1;
            
            updateTimeDisplay();
            updateImage();
            updateSoundingMarkers();
        }}
        
        // Update sounding markers on map
        function updateSoundingMarkers() {{
            soundingMarkers.forEach(m => map.removeLayer(m));
            soundingMarkers = [];
            
            availableSoundings.forEach(siteId => {{
                const site = soundingSites[siteId];
                if (site) {{
                    const icon = L.divIcon({{
                        className: 'sounding-marker',
                        html: siteId,
                        iconSize: [24, 24],
                        iconAnchor: [12, 12]
                    }});
                    
                    const marker = L.marker([site.lat, site.lon], {{ icon }})
                        .addTo(map)
                        .on('click', () => showSounding(siteId));
                    
                    marker.bindTooltip(site.name, {{ direction: 'top', offset: [0, -10] }});
                    soundingMarkers.push(marker);
                }}
            }});
        }}
        
        // Show sounding popup
        function showSounding(siteId) {{
            const site = soundingSites[siteId];
            if (!site) return;
            
            currentSoundingSite = siteId;
            const date = document.getElementById('dateSelect').value;
            const timeIdx = document.getElementById('timeSlider').value;
            const time = currentData.times[timeIdx];
            const domain = document.getElementById('domainSelect').value;
            
            const popup = document.getElementById('soundingPopup');
            const title = document.getElementById('soundingTitle');
            const img = document.getElementById('soundingImg');
            
            title.textContent = `${{site.name}} Sounding - ${{time.substring(0,2)}}:${{time.substring(2)}}`;
            img.src = `${{basePath}}data/${{date}}/sounding${{siteId}}.curr.${{time}}lst.${{domain}}.png`;
            
            img.onerror = () => {{
                img.alt = 'Sounding not available for this time/domain';
                img.style.minHeight = '100px';
            }};
            
            popup.classList.add('active');
        }}
        
        // Update sounding if popup is open
        function updateSoundingIfOpen() {{
            if (currentSoundingSite && document.getElementById('soundingPopup').classList.contains('active')) {{
                showSounding(currentSoundingSite);
            }}
        }}
        
        // Close sounding popup
        document.getElementById('closeSounding').addEventListener('click', () => {{
            document.getElementById('soundingPopup').classList.remove('active');
            currentSoundingSite = null;
        }});
        
        // Update time display
        function updateTimeDisplay() {{
            const slider = document.getElementById('timeSlider');
            const display = document.getElementById('timeDisplay');
            const time = currentData.times[slider.value];
            
            if (time) {{
                display.textContent = time.substring(0, 2) + ':' + time.substring(2);
            }}
        }}
        
        // Update the forecast image overlay
        function updateImage() {{
            const date = document.getElementById('dateSelect').value;
            const param = document.getElementById('paramSelect').value;
            const domain = document.getElementById('domainSelect').value;
            const timeIdx = document.getElementById('timeSlider').value;
            const time = currentData.times[timeIdx];
            
            if (!date || !param || !domain || !time) return;
            
            // Build image URL for static files
            let imageUrl;
            if (param === 'pfd_tot') {{
                imageUrl = `${{basePath}}data/${{date}}/pfd_tot.body.png`;
            }} else {{
                imageUrl = `${{basePath}}data/${{date}}/${{param}}.curr.${{time}}lst.${{domain}}.body.png`;
            }}
            
            // Update header and legend
            let headerUrl, legendUrl;
            if (param === 'pfd_tot') {{
                headerUrl = `${{basePath}}data/${{date}}/pfd_tot.head.png`;
                legendUrl = `${{basePath}}data/${{date}}/pfd_tot.foot.png`;
            }} else {{
                headerUrl = `${{basePath}}data/${{date}}/${{param}}.curr.${{time}}lst.${{domain}}.head.png`;
                legendUrl = `${{basePath}}data/${{date}}/${{param}}.curr.${{time}}lst.${{domain}}.foot.png`;
            }}
            
            document.getElementById('headerImg').src = headerUrl;
            document.getElementById('legendImg').src = legendUrl;
            
            // Update domain polygon visibility
            const selectedDomain = domain;
            Object.entries(domainPolygons).forEach(([d, poly]) => {{
                if (d === selectedDomain) {{
                    if (!map.hasLayer(poly)) poly.addTo(map);
                }} else {{
                    if (map.hasLayer(poly)) map.removeLayer(poly);
                }}
            }});
            
            // Get corner coordinates for the distortable overlay
            const domainInfo = domainData[domain];
            if (!domainInfo) return;
            
            const poly = domainInfo.polygon;
            const corners = [
                [poly[3][0], poly[3][1]], // UL
                [poly[2][0], poly[2][1]], // UR
                [poly[1][0], poly[1][1]], // LR
                [poly[0][0], poly[0][1]], // LL
            ];
            
            const opacity = document.getElementById('opacitySlider').value / 100;
            
            if (imageOverlay) {{
                imageOverlay.setUrl(imageUrl);
            }} else {{
                imageOverlay = L.distortableImageOverlay(imageUrl, corners, {{
                    opacity: opacity
                }}).addTo(map);
            }}
            
            // Fit map to domain on first load or domain change
            if (!viewInitialized || currentDomain !== domain) {{
                const bounds = domainInfo.bounds;
                map.fitBounds([[bounds[0][0], bounds[0][1]], [bounds[1][0], bounds[1][1]]], {{
                    padding: [20, 20]
                }});
                viewInitialized = true;
                currentDomain = domain;
            }}
            
            // Update info
            const paramName = paramInfo[param] || param;
            document.getElementById('infoBox').textContent = `${{date}} | ${{paramName}} | ${{domain.toUpperCase()}}`;
        }}
        
        // Update opacity
        function updateOpacity() {{
            const slider = document.getElementById('opacitySlider');
            const value = slider.value;
            document.getElementById('opacityValue').textContent = value + '%';
            
            if (imageOverlay) {{
                imageOverlay.setOpacity(value / 100);
            }}
        }}
        
        // Play/pause animation
        function togglePlay() {{
            const btn = document.getElementById('playBtn');
            
            if (isPlaying) {{
                isPlaying = false;
                btn.textContent = '▶ Play';
                if (playInterval) {{
                    clearInterval(playInterval);
                    playInterval = null;
                }}
            }} else {{
                isPlaying = true;
                btn.textContent = '⏸ Pause';
                
                const speed = parseInt(document.getElementById('speedSelect').value);
                playInterval = setInterval(() => {{
                    const slider = document.getElementById('timeSlider');
                    let value = parseInt(slider.value);
                    value = (value + 1) % (parseInt(slider.max) + 1);
                    slider.value = value;
                    updateTimeDisplay();
                    updateImage();
                }}, speed);
            }}
        }}
        
        // Event listeners
        document.getElementById('dateSelect').addEventListener('change', (e) => loadDateData(e.target.value));
        document.getElementById('paramSelect').addEventListener('change', updateImage);
        document.getElementById('domainSelect').addEventListener('change', () => {{
            updateImage();
            updateSoundingIfOpen();
        }});
        document.getElementById('timeSlider').addEventListener('input', () => {{
            updateTimeDisplay();
            updateImage();
            updateSoundingIfOpen();
        }});
        document.getElementById('opacitySlider').addEventListener('input', updateOpacity);
        document.getElementById('playBtn').addEventListener('click', togglePlay);
        
        document.getElementById('timePrev').addEventListener('click', () => {{
            const slider = document.getElementById('timeSlider');
            if (parseInt(slider.value) > 0) {{
                slider.value = parseInt(slider.value) - 1;
                updateTimeDisplay();
                updateImage();
                updateSoundingIfOpen();
            }}
        }});
        document.getElementById('timeNext').addEventListener('click', () => {{
            const slider = document.getElementById('timeSlider');
            if (parseInt(slider.value) < parseInt(slider.max)) {{
                slider.value = parseInt(slider.value) + 1;
                updateTimeDisplay();
                updateImage();
                updateSoundingIfOpen();
            }}
        }});
        
        // Initialize
        initMap();
        loadDates();
    </script>
</body>
</html>
'''


def generate_static_site():
    """Generate the complete static site."""
    print("🌤️  RASP Static Site Generator")
    print("=" * 50)
    
    # Create docs directory
    if os.path.exists(DOCS_DIR):
        print(f"📁 Cleaning existing docs folder...")
        shutil.rmtree(DOCS_DIR)
    
    os.makedirs(DOCS_DIR)
    data_dir = os.path.join(DOCS_DIR, 'data')
    os.makedirs(data_dir)
    
    # Calculate domain bounds
    print("📐 Calculating domain bounds...")
    domain_objs = create_domains()
    domain_bounds = {
        'd1': {
            'bounds': domain_objs['d1'].get_domain_bounds(use_square_image=True),
            'polygon': domain_objs['d1'].get_corner_polygon(use_square_image=True),
        },
        'd2': {
            'bounds': domain_objs['d2'].get_domain_bounds(),
            'polygon': domain_objs['d2'].get_corner_polygon(),
        }
    }
    
    # Get available dates and build manifest
    print("📅 Scanning available forecast data...")
    dates = get_available_dates()
    manifest = {}
    total_images = 0
    
    for date in dates:
        print(f"   Processing {date}...")
        data = get_available_data(date)
        manifest[date] = data
        
        # Copy images
        dest_dir = os.path.join(data_dir, date)
        count = copy_images(date, dest_dir)
        total_images += count
        print(f"      Copied {count} images")
    
    # Generate HTML
    print("📝 Generating index.html...")
    html = generate_html(domain_bounds, manifest)
    
    with open(os.path.join(DOCS_DIR, 'index.html'), 'w') as f:
        f.write(html)
    
    # Create .nojekyll file for GitHub Pages
    with open(os.path.join(DOCS_DIR, '.nojekyll'), 'w') as f:
        pass
    
    print("=" * 50)
    print(f"✅ Static site generated successfully!")
    print(f"   📁 Output: {DOCS_DIR}")
    print(f"   📅 Dates: {len(dates)}")
    print(f"   🖼️  Images: {total_images}")
    print()
    print("To deploy to GitHub Pages:")
    print("  1. Push this repo to GitHub")
    print("  2. Go to Settings > Pages")
    print("  3. Set Source to 'Deploy from a branch'")
    print("  4. Select 'main' branch and '/docs' folder")
    print("  5. Save and wait for deployment")
    print()
    print("To test locally:")
    print(f"  cd {DOCS_DIR}")
    print("  python -m http.server 8080")
    print("  Open http://localhost:8080")


if __name__ == '__main__':
    generate_static_site()
