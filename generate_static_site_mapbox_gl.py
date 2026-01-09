#!/usr/bin/env python3
"""
Static Site Generator for RASP Weather Viewer
Generates a GitHub Pages compatible static site from forecast data.
Uses Mapbox GL with Lambert Conformal Conic projection for proper geographic display.

Usage:
    python generate_static_site_mapbox_gl.py

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

# Mapbox Configuration
# Get your access token from https://account.mapbox.com/access-tokens/
MAPBOX_ACCESS_TOKEN = 'pk.eyJ1IjoiZ2VvcmdlZG93bmluZyIsImEiOiJjbWZlMzBndzYwMmhxMmpyNWFqcnkzdjJmIn0.L9RHEN7ySukYIhsKKu4-Rw'

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
        'e_we': 151, 'e_sn': 151,
        'i_parent_start': 12, 'j_parent_start': 38,
        'parent_grid_ratio': 3,
    }
}

# Parameter descriptions
PARAMETER_INFO = {
    'wstar': 'Thermal Updraft Velocity (W*)',
    'bsratio': 'Buoyancy/Shear Ratio',
    'wstar_bsratio': 'W* with B/S Ratio',
    'hglider': 'Thermalling Height (MSL)',
    'dglider': 'Thermalling Height (AGL)',
    'hwcrit': 'Height of Critical Updraft (MSL)',
    'dwcrit': 'Height of Critical Updraft (AGL)',
    'hbl': 'BL Top Height (MSL)',
    'dbl': 'BL Depth (AGL)',
    'bltopvariab': 'BL Top Variability',
    'wblmaxmin': 'Convergence',
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
    'ridgelift': 'Ridge Lift (Vertical Velocity ~300ft AGL)',
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
            'll': (ll_lon, ll_lat),
            'lr': (lr_lon, lr_lat),
            'ur': (ur_lon, ur_lat),
            'ul': (ul_lon, ul_lat),
        }
        
        return {
            'bounds': [[ll_lat, ll_lon], [ur_lat, ur_lon]],
            'corners': [
                [ll_lat, ll_lon],  # SW
                [lr_lat, lr_lon],  # SE
                [ur_lat, ur_lon],  # NE
                [ul_lat, ul_lon],  # NW
            ]
        }


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


def generate_html(domain_bounds, manifest, help_text, mapbox_token):
    """Generate the static HTML viewer using Mapbox GL with Lambert projection."""
    help_text_json = json.dumps(help_text)
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <title>RASP Weather Viewer - NZ</title>
    <link href="https://api.mapbox.com/mapbox-gl-js/v3.0.1/mapbox-gl.css" rel="stylesheet" />
    <script src="https://api.mapbox.com/mapbox-gl-js/v3.0.1/mapbox-gl.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            overflow: hidden;
            height: 100%;
            width: 100%;
            position: fixed;
            touch-action: none;
            -webkit-overflow-scrolling: touch;
        }}
        
        /* Loading Screen */
        .loading-screen {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: #1a1a2e;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            transition: opacity 0.5s ease, visibility 0.5s ease;
        }}
        .loading-screen.hidden {{
            opacity: 0;
            visibility: hidden;
            pointer-events: none;
        }}
        .loading-content {{
            text-align: center;
            max-width: 400px;
            padding: 20px;
        }}
        .loading-title {{
            font-size: 2em;
            color: #e94560;
            margin-bottom: 10px;
        }}
        .loading-subtitle {{
            font-size: 1em;
            color: #aaa;
            margin-bottom: 30px;
        }}
        .loading-bar-container {{
            width: 100%;
            height: 8px;
            background: #0f3460;
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 15px;
        }}
        .loading-bar {{
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, #e94560, #ff6b6b);
            border-radius: 4px;
            transition: width 0.3s ease;
        }}
        .loading-status {{
            font-size: 0.85em;
            color: #888;
            min-height: 1.2em;
        }}
        .loading-spinner {{
            width: 40px;
            height: 40px;
            border: 3px solid #0f3460;
            border-top-color: #e94560;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 20px auto 0;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        #map {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            width: 100%;
            height: 100%;
            touch-action: none;
            z-index: 1;
        }}
        
        /* Controls Panel */
        .controls {{
            position: fixed;
            top: 10px;
            left: 10px;
            z-index: 1100;
            background: rgba(22, 33, 62, 0.95);
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            max-width: 320px;
            max-height: calc(100vh - 20px);
            overflow-y: auto;
            transition: transform 0.3s ease, opacity 0.3s ease, max-width 0.3s ease, padding 0.3s ease;
        }}
        .controls.collapsed {{
            transform: translateX(-100%);
            opacity: 0;
            pointer-events: none;
        }}
        .controls.small {{
            max-width: none;
            width: calc(100% - 80px);
            left: 10px;
            right: 70px;
            padding: 6px 10px;
            border-radius: 8px;
        }}
        .controls.small h2,
        .controls.small .mobile-row,
        .controls.small .expert-toggle,
        .controls.small .opacity-control,
        .controls.small .play-controls,
        .controls.small .help-btn {{
            display: none;
        }}
        .controls.small .control-group {{
            display: none;
        }}
        .controls.small .control-group.time-control {{
            display: block;
            margin-bottom: 0;
        }}
        .controls.small .control-group.time-control label {{
            display: none;
        }}
        .controls.small .time-slider-container {{
            margin-top: 0;
        }}
        .controls.small .time-nav-btn {{
            width: 36px;
            height: 36px;
            font-size: 1.1em;
        }}
        .controls.small .time-display {{
            font-size: 1.3em;
        }}
        .controls.small input[type="range"] {{
            margin: 6px 0;
        }}
        .controls h2 {{
            color: #e94560;
            margin-bottom: 15px;
            font-size: 1.1em;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .controls-toggle {{
            display: none;
            position: fixed;
            top: 10px;
            right: 10px;
            z-index: 1101;
            background: rgba(233, 69, 96, 0.95);
            color: white;
            border: none;
            width: 44px;
            height: 44px;
            border-radius: 10px;
            font-size: 1.2em;
            cursor: pointer;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            transition: transform 0.3s ease;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        .controls-toggle.active {{
            transform: translateX(0);
        }}
        .state-indicator {{
            font-size: 0.7em;
            color: #aaa;
            margin-top: 2px;
        }}
        .close-controls {{
            display: none;
            background: none;
            border: none;
            color: #aaa;
            font-size: 1.5em;
            cursor: pointer;
            padding: 0;
            line-height: 1;
        }}
        .close-controls:hover {{ color: #fff; }}
        
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
            padding: 10px 8px;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            -webkit-appearance: none;
            appearance: none;
        }}
        select:focus {{ outline: none; border-color: #fff; }}
        
        .time-slider-container {{
            margin-top: 5px;
        }}
        input[type="range"] {{
            width: 100%;
            height: 8px;
            -webkit-appearance: none;
            background: #0f3460;
            border-radius: 4px;
            margin: 10px 0;
        }}
        input[type="range"]::-webkit-slider-thumb {{
            -webkit-appearance: none;
            width: 24px;
            height: 24px;
            background: #e94560;
            border-radius: 50%;
            cursor: pointer;
        }}
        .time-display {{
            text-align: center;
            font-size: 1.6em;
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
            padding: 12px 8px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 1em;
        }}
        .play-btn:hover, .play-btn:active {{ background: #ff6b6b; }}
        .speed-select {{
            width: 80px;
        }}
        .expert-toggle {{
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #444;
        }}
        .toggle-label {{
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            font-size: 0.9em;
        }}
        .toggle-label input {{
            width: 18px;
            height: 18px;
            cursor: pointer;
        }}
        .opacity-control {{
            margin-top: 10px;
        }}
        .opacity-control input {{
            width: 100%;
        }}
        
        .info-box {{
            position: fixed;
            bottom: 10px;
            left: 10px;
            z-index: 1000;
            background: rgba(22, 33, 62, 0.9);
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 0.8em;
            color: #aaa;
            max-width: calc(100vw - 20px);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .header-box {{
            position: fixed;
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1099;
            background: rgba(22, 33, 62, 0.95);
            padding: 6px;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            max-width: calc(100vw - 20px);
        }}
        .header-box img {{
            display: block;
            max-width: 100%;
            height: auto;
        }}
        
        .legend-box {{
            position: fixed;
            bottom: 10px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 999;
            background: rgba(22, 33, 62, 0.95);
            padding: 6px;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            max-width: calc(100vw - 20px);
        }}
        .legend-box img {{
            display: block;
            max-width: 100%;
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
            width: 44px;
            height: 44px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 1.3em;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .time-nav-btn:hover, .time-nav-btn:active {{ background: #ff6b6b; }}
        .time-nav-btn:disabled {{ background: #555; cursor: not-allowed; }}
        
        .help-btn {{
            background: #0f3460;
            color: #e94560;
            border: 1px solid #e94560;
            padding: 8px 16px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.9em;
            width: 100%;
            margin-top: 10px;
            transition: all 0.2s ease;
        }}
        .help-btn:hover {{
            background: #e94560;
            color: white;
        }}
        
        /* Location Button */
        .location-btn {{
            position: fixed;
            bottom: 100px;
            right: 10px;
            z-index: 1100;
            background: rgba(22, 33, 62, 0.95);
            color: #4a9eff;
            border: 2px solid #4a9eff;
            width: 44px;
            height: 44px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.3em;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            transition: all 0.3s ease;
        }}
        .location-btn:hover {{
            background: #4a9eff;
            color: white;
        }}
        .location-btn.active {{
            background: #4a9eff;
            color: white;
            animation: pulse-location 2s infinite;
        }}
        .location-btn.searching {{
            animation: pulse-search 1s infinite;
        }}
        @keyframes pulse-location {{
            0%, 100% {{ box-shadow: 0 0 0 0 rgba(74, 158, 255, 0.7); }}
            50% {{ box-shadow: 0 0 0 10px rgba(74, 158, 255, 0); }}
        }}
        @keyframes pulse-search {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        
        /* GPS Marker */
        .gps-marker {{
            width: 20px;
            height: 20px;
            background: #4a9eff;
            border: 3px solid white;
            border-radius: 50%;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }}
        .gps-marker-pulse {{
            position: absolute;
            width: 40px;
            height: 40px;
            background: rgba(74, 158, 255, 0.3);
            border-radius: 50%;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            animation: gps-pulse 2s infinite;
        }}
        @keyframes gps-pulse {{
            0% {{ transform: translate(-50%, -50%) scale(0.5); opacity: 1; }}
            100% {{ transform: translate(-50%, -50%) scale(2); opacity: 0; }}
        }}
        .gps-accuracy-circle {{
            background: rgba(74, 158, 255, 0.15);
            border: 1px solid rgba(74, 158, 255, 0.3);
            border-radius: 50%;
        }}
        
        .help-modal {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            z-index: 3000;
            background: rgba(0, 0, 0, 0.85);
            display: none;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }}
        .help-modal.active {{
            display: flex;
        }}
        .help-content {{
            background: #16213e;
            border-radius: 10px;
            max-width: 800px;
            max-height: 90vh;
            width: 100%;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            box-shadow: 0 4px 30px rgba(0,0,0,0.7);
        }}
        .help-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 20px;
            border-bottom: 1px solid #444;
            background: #0f3460;
        }}
        .help-header h2 {{
            color: #e94560;
            margin: 0;
            font-size: 1.2em;
        }}
        .help-close-btn {{
            background: #e94560;
            color: white;
            border: none;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.4em;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .help-close-btn:hover {{
            background: #ff6b6b;
        }}
        .help-body {{
            padding: 20px;
            overflow-y: auto;
            flex: 1;
        }}
        .help-text {{
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 0.85em;
            line-height: 1.5;
            white-space: pre-wrap;
            color: #ddd;
        }}
        
        .sounding-popup {{
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 2000;
            background: rgba(22, 33, 62, 0.98);
            padding: 10px;
            border-radius: 10px;
            box-shadow: 0 4px 30px rgba(0,0,0,0.7);
            display: none;
            max-width: calc(100vw - 20px);
            max-height: calc(100vh - 20px);
            overflow: auto;
        }}
        .sounding-popup.active {{
            display: block;
        }}
        .sounding-popup img {{
            max-width: 100%;
            max-height: calc(100vh - 80px);
            display: block;
        }}
        .sounding-popup .close-btn {{
            position: absolute;
            top: 5px;
            right: 5px;
            background: #e94560;
            color: white;
            border: none;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.4em;
        }}
        .sounding-popup h3 {{
            color: #e94560;
            margin: 0 0 10px 0;
            padding-right: 40px;
            font-size: 1em;
        }}
        
        /* Mobile Styles */
        @media (max-width: 768px) {{
            .controls {{
                top: 0;
                left: 0;
                right: 0;
                max-width: 100%;
                border-radius: 0 0 10px 10px;
                padding: 12px 15px;
                max-height: 70vh;
            }}
            .controls.collapsed {{
                transform: translateY(-100%);
            }}
            .controls-toggle {{
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            .close-controls {{
                display: block;
            }}
            .controls h2 {{
                font-size: 1em;
                margin-bottom: 10px;
            }}
            .header-box {{
                top: auto;
                bottom: 70px;
                left: 5px;
                right: 5px;
                transform: none;
                max-width: none;
                padding: 4px;
            }}
            .legend-box {{
                bottom: 5px;
                left: 5px;
                right: 5px;
                transform: none;
                padding: 6px;
                max-width: none;
            }}
            .legend-box img {{
                max-height: none;
                width: 100%;
                height: auto;
                min-height: 50px;
            }}
            .info-box {{
                display: none;
            }}
            .time-display {{
                font-size: 1.4em;
            }}
            .play-controls {{
                gap: 6px;
            }}
            .time-nav {{
                gap: 6px;
            }}
            .time-nav-btn {{
                width: 40px;
                height: 40px;
            }}
            .mobile-row {{
                display: flex;
                gap: 10px;
            }}
            .mobile-row .control-group {{
                flex: 1;
                margin-bottom: 8px;
            }}
        }}
        
        @media (max-width: 480px) {{
            .controls {{
                padding: 10px 12px;
            }}
            .header-box {{
                display: none;
            }}
            .legend-box img {{
                min-height: 45px;
            }}
        }}
    </style>
</head>
<body>
    <!-- Loading Screen -->
    <div class="loading-screen" id="loadingScreen">
        <div class="loading-content">
            <div class="loading-title">🌤️ RASP NZ</div>
            <div class="loading-subtitle">Loading Weather Forecast...</div>
            <div class="loading-bar-container">
                <div class="loading-bar" id="loadingBar"></div>
            </div>
            <div class="loading-status" id="loadingStatus">Initializing...</div>
            <div class="loading-spinner"></div>
        </div>
    </div>
    
    <div id="map"></div>
    
    <button class="controls-toggle" id="controlsToggle" aria-label="Open controls">☰<span class="state-indicator" id="stateIndicator"></span></button>
    
    <div class="controls" id="controlsPanel">
        <h2>
            <span>🌤️ RASP NZ</span>
            <button class="close-controls" id="closeControls" aria-label="Close controls">×</button>
        </h2>
        
        <div class="mobile-row">
            <div class="control-group">
                <label>Map Style</label>
                <select id="styleSelect">
                    <option value="mapbox://styles/mapbox/streets-v12">Streets</option>
                    <option value="mapbox://styles/mapbox/satellite-streets-v12">Satellite</option>
                    <option value="mapbox://styles/mapbox/outdoors-v12">Outdoors</option>
                    <option value="mapbox://styles/mapbox/light-v11">Light</option>
                    <option value="mapbox://styles/mapbox/dark-v11">Dark</option>
                </select>
            </div>
            
            <div class="control-group">
                <label>Date</label>
                <select id="dateSelect"></select>
            </div>
            
            <div class="control-group">
                <label>Domain</label>
                <select id="domainSelect"></select>
            </div>
        </div>
        
        <div class="control-group">
            <label>Parameter</label>
            <select id="paramSelect"></select>
        </div>
        
        <div class="control-group time-control">
            <label>Time (Local)</label>
            <div class="time-slider-container">
                <input type="range" id="timeSlider" min="0" max="9" value="4">
                <div class="time-nav">
                    <button class="time-nav-btn" id="timePrev" title="Previous" aria-label="Previous time">◀</button>
                    <div class="time-display" id="timeDisplay" style="flex:1">--:--</div>
                    <button class="time-nav-btn" id="timeNext" title="Next" aria-label="Next time">▶</button>
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
            <label>Opacity: <span id="opacityValue">70%</span></label>
            <input type="range" id="opacitySlider" min="0" max="100" value="70">
        </div>
        
        <button class="help-btn" id="helpBtn">❓ Parameter Help</button>
    </div>
    
    <button class="location-btn" id="locationBtn" title="Find my location" aria-label="Find my location">📍</button>
    
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
    
    <div class="help-modal" id="helpModal">
        <div class="help-content">
            <div class="help-header">
                <h2>📖 RASP Parameter Reference</h2>
                <button class="help-close-btn" id="helpCloseBtn">×</button>
            </div>
            <div class="help-body">
                <pre class="help-text" id="helpText"></pre>
            </div>
        </div>
    </div>
    
    <script>
        // =====================================================
        // EMBEDDED DATA - Generated by static site generator
        // =====================================================
        
        mapboxgl.accessToken = '{mapbox_token}';
        
        const paramInfo = {json.dumps(PARAMETER_INFO)};
        const basicParams = ['pfd_tot', 'xcspeed', 'wstar', 'sfcwind0', 'blcloudpct', 'hglider', 'zsfclclmask', 'stars', 'wblmaxmin'];
        const domainData = {json.dumps(domain_bounds)};
        const soundingSites = {json.dumps(SOUNDING_SITES)};
        const manifest = {json.dumps(manifest)};
        const helpText = {help_text_json};
        
        // =====================================================
        // APPLICATION CODE
        // =====================================================
        
        let currentData = {{ parameters: [], times: [], domains: [], soundings: [] }};
        let map = null;
        let isPlaying = false;
        let playInterval = null;
        let viewInitialized = false;
        let currentDomain = null;
        let currentSoundingSite = null;
        let expertMode = false;
        let preloadedImages = {{}};
        let activeLayer = 'A'; // Toggle between 'A' and 'B' for double buffering
        
        // Loading state management
        let loadingProgress = 0;
        const loadingStages = {{
            mapbox: {{ weight: 20, done: false, label: 'Loading Mapbox...' }},
            style: {{ weight: 25, done: false, label: 'Loading map style...' }},
            terrain: {{ weight: 15, done: false, label: 'Loading terrain...' }},
            data: {{ weight: 20, done: false, label: 'Loading forecast data...' }},
            image: {{ weight: 20, done: false, label: 'Loading forecast overlay...' }}
        }};
        
        function updateLoadingProgress(stage) {{
            if (loadingStages[stage] && !loadingStages[stage].done) {{
                loadingStages[stage].done = true;
                loadingProgress = Object.values(loadingStages)
                    .filter(s => s.done)
                    .reduce((sum, s) => sum + s.weight, 0);
                
                const loadingBar = document.getElementById('loadingBar');
                const loadingStatus = document.getElementById('loadingStatus');
                
                if (loadingBar) {{
                    loadingBar.style.width = loadingProgress + '%';
                }}
                
                // Find next incomplete stage for status message
                const nextStage = Object.values(loadingStages).find(s => !s.done);
                if (loadingStatus && nextStage) {{
                    loadingStatus.textContent = nextStage.label;
                }} else if (loadingStatus) {{
                    loadingStatus.textContent = 'Almost ready...';
                }}
                
                console.log(`Loading progress: ${{loadingProgress}}% (${{stage}} complete)`);
                
                // Hide loading screen when complete
                if (loadingProgress >= 100) {{
                    hideLoadingScreen();
                }}
            }}
        }}
        
        function hideLoadingScreen() {{
            const loadingScreen = document.getElementById('loadingScreen');
            if (loadingScreen) {{
                loadingScreen.classList.add('hidden');
                // Remove from DOM after animation
                setTimeout(() => {{
                    loadingScreen.style.display = 'none';
                }}, 500);
            }}
        }}
        
        function getBasePath() {{
            const path = window.location.pathname;
            if (path.includes('/docs/')) {{
                return path.substring(0, path.indexOf('/docs/') + 6);
            }}
            return path.substring(0, path.lastIndexOf('/') + 1);
        }}
        
        const basePath = getBasePath();
        
        // Initialize map with Lambert Conformal projection
        function initMap() {{
            console.log('Initializing map...');
            updateLoadingProgress('mapbox');
            
            try {{
                map = new mapboxgl.Map({{
                    container: 'map',
                    style: 'mapbox://styles/mapbox/streets-v12',
                    center: [176.0, -38.5],
                    zoom: 8,
                    pitch: 45,
                    bearing: 0,
                    attributionControl: true
                }});
                
                console.log('Map created, waiting for style.load...');
                
                map.on('style.load', () => {{
                    console.log('Map style loaded, adding layers...');
                    updateLoadingProgress('style');
                    
                    // Add terrain source and layer for 3D
                    map.addSource('mapbox-dem', {{
                        'type': 'raster-dem',
                        'url': 'mapbox://mapbox.mapbox-terrain-dem-v1',
                        'tileSize': 512,
                        'maxzoom': 14
                    }});
                    
                    // Set terrain with zoom-based exaggeration
                    map.setTerrain({{
                        'source': 'mapbox-dem',
                        'exaggeration': [
                            'interpolate',
                            ['linear'],
                            ['zoom'],
                            0, 20,
                            8, 5,
                            12, 2,
                            16, 1
                        ]
                    }});
                    
                    updateLoadingProgress('terrain');
                    addMapLayers();
                    
                    // Only load dates on initial load, not on style change
                    if (!viewInitialized) {{
                        setTimeout(() => {{
                            console.log('Loading dates...');
                            updateLoadingProgress('data');
                            loadDates();
                        }}, 100);
                    }} else {{
                        // Re-add the forecast layer after style change
                        setTimeout(() => {{
                            updateImageSource();
                        }}, 100);
                    }}
                }});
                
                map.on('error', (e) => {{
                    console.error('Map error:', e);
                }});
            }} catch (e) {{
                console.error('Error initializing map:', e);
            }}
        }}
        
        function addMapLayers() {{
            // Add two image sources for double-buffering (no flash on time change)
            const defaultCoords = [
                [172.5, -35.77],  // NW (top-left)
                [179.5, -35.77],  // NE (top-right)
                [179.5, -41.13],  // SE (bottom-right)
                [172.5, -41.13]   // SW (bottom-left)
            ];
            const transparentPixel = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
            
            if (!map.getSource('forecast-image-A')) {{
                map.addSource('forecast-image-A', {{
                    type: 'image',
                    url: transparentPixel,
                    coordinates: defaultCoords
                }});
                map.addLayer({{
                    id: 'forecast-layer-A',
                    type: 'raster',
                    source: 'forecast-image-A',
                    paint: {{ 'raster-opacity': 0.7 }}
                }});
            }}
            
            if (!map.getSource('forecast-image-B')) {{
                map.addSource('forecast-image-B', {{
                    type: 'image',
                    url: transparentPixel,
                    coordinates: defaultCoords
                }});
                map.addLayer({{
                    id: 'forecast-layer-B',
                    type: 'raster',
                    source: 'forecast-image-B',
                    paint: {{ 'raster-opacity': 0 }}
                }});
            }}
            
            // Add sounding site markers
            addSoundingMarkers();
        }}
        
        // Sounding markers - using native Mapbox layers for proper anchoring
        function addSoundingMarkers() {{
            // Create GeoJSON data for sounding sites
            const soundingGeoJSON = {{
                type: 'FeatureCollection',
                features: Object.entries(soundingSites).map(([siteId, site]) => ({{
                    type: 'Feature',
                    properties: {{
                        id: siteId,
                        name: site.name
                    }},
                    geometry: {{
                        type: 'Point',
                        coordinates: [site.lon, site.lat]
                    }}
                }}))
            }};
            
            // Remove existing source/layers if they exist (for style changes)
            if (map.getLayer('sounding-labels')) map.removeLayer('sounding-labels');
            if (map.getLayer('sounding-markers')) map.removeLayer('sounding-markers');
            if (map.getSource('sounding-sites')) map.removeSource('sounding-sites');
            
            // Add source
            map.addSource('sounding-sites', {{
                type: 'geojson',
                data: soundingGeoJSON
            }});
            
            // Create custom skew-T icon as an image
            const iconSize = 48;
            const canvas = document.createElement('canvas');
            canvas.width = iconSize;
            canvas.height = iconSize;
            const ctx = canvas.getContext('2d');
            
            // Helper function for rounded rectangle (cross-browser compatible)
            function drawRoundedRect(ctx, x, y, width, height, radius) {{
                ctx.beginPath();
                ctx.moveTo(x + radius, y);
                ctx.lineTo(x + width - radius, y);
                ctx.arcTo(x + width, y, x + width, y + radius, radius);
                ctx.lineTo(x + width, y + height - radius);
                ctx.arcTo(x + width, y + height, x + width - radius, y + height, radius);
                ctx.lineTo(x + radius, y + height);
                ctx.arcTo(x, y + height, x, y + height - radius, radius);
                ctx.lineTo(x, y + radius);
                ctx.arcTo(x, y, x + radius, y, radius);
                ctx.closePath();
            }}
            
            // Draw background
            ctx.fillStyle = 'rgba(22, 33, 62, 0.95)';
            ctx.strokeStyle = '#e94560';
            ctx.lineWidth = 2;
            drawRoundedRect(ctx, 4, 4, iconSize - 8, iconSize - 8, 4);
            ctx.fill();
            ctx.stroke();
            
            // Draw skewed isotherms (temperature lines tilted right)
            ctx.strokeStyle = 'rgba(233, 69, 96, 0.25)';
            ctx.lineWidth = 0.8;
            for (let i = 0; i < 4; i++) {{
                ctx.beginPath();
                ctx.moveTo(8 + i * 9, iconSize - 8);
                ctx.lineTo(16 + i * 9, 8);
                ctx.stroke();
            }}
            
            // Draw horizontal pressure lines (isobars)
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
            for (let y of [12, 20, 28, 36]) {{
                ctx.beginPath();
                ctx.moveTo(8, y);
                ctx.lineTo(iconSize - 8, y);
                ctx.stroke();
            }}
            
            // Draw temperature profile (red) with inversion
            // Starts warm at surface, cools, then WARMS (inversion), then cools again
            ctx.strokeStyle = '#e94560';
            ctx.lineWidth = 2.5;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            ctx.setLineDash([]);
            ctx.beginPath();
            ctx.moveTo(28, 40);      // Surface - warm
            ctx.lineTo(22, 32);      // Cooling with height
            ctx.lineTo(28, 26);      // INVERSION - temperature increases (bulge right)
            ctx.lineTo(20, 18);      // Above inversion - cooling again
            ctx.lineTo(16, 10);      // Upper level - cold
            ctx.stroke();
            
            // Draw dewpoint profile (green/cyan dashed) - stays left of temp
            ctx.strokeStyle = '#00d4aa';
            ctx.lineWidth = 2;
            ctx.setLineDash([3, 2]);
            ctx.beginPath();
            ctx.moveTo(18, 40);      // Surface dewpoint
            ctx.lineTo(14, 32);      // Decreasing
            ctx.lineTo(12, 26);      // Dry at inversion (big temp-dewpoint spread)
            ctx.lineTo(10, 18);      // Still dry above
            ctx.lineTo(8, 10);       // Upper level
            ctx.stroke();
            
            // Add as image to map
            const imageData = ctx.getImageData(0, 0, iconSize, iconSize);
            
            if (!map.hasImage('skewt-icon')) {{
                map.addImage('skewt-icon', imageData, {{ pixelRatio: 2 }});
            }}
            
            // Add symbol layer for markers
            map.addLayer({{
                id: 'sounding-markers',
                type: 'symbol',
                source: 'sounding-sites',
                layout: {{
                    'icon-image': 'skewt-icon',
                    'icon-size': 0.7,
                    'icon-allow-overlap': true,
                    'icon-ignore-placement': true,
                    'icon-pitch-alignment': 'viewport',
                    'icon-rotation-alignment': 'viewport'
                }}
            }});
            
            // Add labels layer
            map.addLayer({{
                id: 'sounding-labels',
                type: 'symbol',
                source: 'sounding-sites',
                layout: {{
                    'text-field': ['get', 'name'],
                    'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold'],
                    'text-size': 11,
                    'text-offset': [0, 1.8],
                    'text-anchor': 'top',
                    'text-allow-overlap': false
                }},
                paint: {{
                    'text-color': '#ffffff',
                    'text-halo-color': 'rgba(22, 33, 62, 0.9)',
                    'text-halo-width': 2
                }}
            }});
            
            // Add click handler for markers
            map.on('click', 'sounding-markers', (e) => {{
                if (e.features && e.features.length > 0) {{
                    const feature = e.features[0];
                    const siteId = feature.properties.id;
                    const siteName = feature.properties.name;
                    showSounding(siteId, siteName);
                }}
            }});
            
            // Change cursor on hover
            map.on('mouseenter', 'sounding-markers', () => {{
                map.getCanvas().style.cursor = 'pointer';
            }});
            
            map.on('mouseleave', 'sounding-markers', () => {{
                map.getCanvas().style.cursor = '';
            }});
            
            console.log(`Added ${{soundingGeoJSON.features.length}} sounding markers using symbol layer`);
        }}
        
        function showSounding(siteId, siteName) {{
            const date = document.getElementById('dateSelect').value;
            const timeIdx = document.getElementById('timeSlider').value;
            const time = currentData.times[timeIdx];
            const domain = document.getElementById('domainSelect').value;
            
            if (!date || !time) {{
                console.warn('Cannot show sounding: missing date or time');
                return;
            }}
            
            // Check if this sounding site is available
            if (!currentData.soundings.includes(siteId)) {{
                alert(`Sounding for ${{siteName}} is not available for this date`);
                return;
            }}
            
            // Build sounding image URL
            const soundingUrl = `${{basePath}}data/${{date}}/sounding${{siteId}}.curr.${{time}}lst.${{domain}}.png`;
            
            // Update popup content
            document.getElementById('soundingTitle').textContent = `${{siteName}} Sounding - ${{time.substring(0,2)}}:${{time.substring(2)}} ${{date}}`;
            document.getElementById('soundingImg').src = soundingUrl;
            
            // Show popup
            document.getElementById('soundingPopup').classList.add('active');
            currentSoundingSite = siteId;
            
            console.log(`Showing sounding: ${{soundingUrl}}`);
        }}
        
        // Preload all time images for current selection
        function preloadImages() {{
            const date = document.getElementById('dateSelect').value;
            const param = document.getElementById('paramSelect').value;
            const domain = document.getElementById('domainSelect').value;
            
            if (!date || !param || !domain) return;
            
            const key = `${{date}}-${{param}}-${{domain}}`;
            if (preloadedImages[key]) return; // Already preloaded
            
            preloadedImages[key] = {{}};
            
            currentData.times.forEach(time => {{
                const img = new Image();
                let url;
                if (param === 'pfd_tot') {{
                    url = `${{basePath}}data/${{date}}/pfd_tot.body.png`;
                }} else {{
                    url = `${{basePath}}data/${{date}}/${{param}}.curr.${{time}}lst.${{domain}}.body.png`;
                }}
                img.src = url;
                preloadedImages[key][time] = img;
            }});
            
            console.log(`Preloaded ${{currentData.times.length}} images for ${{key}}`);
        }}
        
        function updateImageSource() {{
            const date = document.getElementById('dateSelect').value;
            const param = document.getElementById('paramSelect').value;
            const domain = document.getElementById('domainSelect').value;
            const timeIdx = document.getElementById('timeSlider').value;
            const time = currentData.times[timeIdx];
            
            if (!date || !param || !domain || !time) {{
                console.warn('Missing required data:', {{ date, param, domain, time }});
                return;
            }}
            
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
            
            // Double-buffer update to prevent flash
            const domainInfo = domainData[domain];
            if (!domainInfo || !domainInfo.corners || !map) return;
            
            const corners = domainInfo.corners;
            const coordinates = [
                [corners[3][1], corners[3][0]],  // NW (top-left)
                [corners[2][1], corners[2][0]],  // NE (top-right)
                [corners[1][1], corners[1][0]],  // SE (bottom-right)
                [corners[0][1], corners[0][0]]   // SW (bottom-left)
            ];
            
            const opacity = document.getElementById('opacitySlider').value / 100;
            const nextLayer = activeLayer === 'A' ? 'B' : 'A';
            const nextSourceId = `forecast-image-${{nextLayer}}`;
            const nextLayerId = `forecast-layer-${{nextLayer}}`;
            const currentLayerId = `forecast-layer-${{activeLayer}}`;
            
            // Remove and re-add the inactive source with new image
            if (map.getLayer(nextLayerId)) {{
                map.removeLayer(nextLayerId);
            }}
            if (map.getSource(nextSourceId)) {{
                map.removeSource(nextSourceId);
            }}
            
            map.addSource(nextSourceId, {{
                type: 'image',
                url: imageUrl,
                coordinates: coordinates
            }});
            
            // Add layer with 0 opacity initially
            map.addLayer({{
                id: nextLayerId,
                type: 'raster',
                source: nextSourceId,
                paint: {{ 'raster-opacity': 0 }}
            }});
            
            // Wait for image to load, then crossfade
            map.once('idle', () => {{
                // Show new layer
                map.setPaintProperty(nextLayerId, 'raster-opacity', opacity);
                // Hide old layer
                if (map.getLayer(currentLayerId)) {{
                    map.setPaintProperty(currentLayerId, 'raster-opacity', 0);
                }}
                activeLayer = nextLayer;
                
                // Mark image loading complete for initial load
                updateLoadingProgress('image');
            }});
            
            // Only fit map to domain on initial load
            if (!viewInitialized) {{
                const bounds = domainData[domain].bounds;
                map.fitBounds(
                    [[bounds[0][1], bounds[0][0]], [bounds[1][1], bounds[1][0]]],
                    {{ padding: 20 }}
                );
                viewInitialized = true;
            }}
            currentDomain = domain;
            
            const paramName = paramInfo[param] || param;
            document.getElementById('infoBox').textContent = `${{date}} | ${{paramName}} | ${{domain.toUpperCase()}}`;
        }}
        
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
                const today = new Date().toISOString().split('T')[0];
                const defaultDate = dates.includes(today) ? today : dates[0];
                select.value = defaultDate;
                loadDateData(defaultDate);
            }}
        }}
        
        function loadDateData(date) {{
            currentData = manifest[date] || {{ parameters: [], times: [], domains: [], soundings: [] }};
            updateParameterDropdown();
            
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
            
            const timeSlider = document.getElementById('timeSlider');
            const currentTimeIdx = parseInt(timeSlider.value);
            timeSlider.max = currentData.times.length - 1;
            
            // Preserve time index if valid, otherwise keep at same position or max
            if (currentTimeIdx <= parseInt(timeSlider.max)) {{
                timeSlider.value = currentTimeIdx;
            }} else {{
                timeSlider.value = timeSlider.max;
            }}
            
            updateTimeDisplay();
            updateImageSource();
            preloadImages(); // Preload all time images for this selection
        }}
        
        function updateParameterDropdown() {{
            const paramSelect = document.getElementById('paramSelect');
            const currentParam = paramSelect.value;
            paramSelect.innerHTML = '';
            
            let paramsToShow = currentData.parameters;
            if (!expertMode) {{
                paramsToShow = currentData.parameters.filter(p => basicParams.includes(p));
            }}
            
            paramsToShow.forEach(p => {{
                const option = document.createElement('option');
                option.value = p;
                option.textContent = paramInfo[p] || p;
                paramSelect.appendChild(option);
            }});
            
            if (paramsToShow.includes(currentParam)) {{
                paramSelect.value = currentParam;
            }} else if (paramsToShow.length > 0) {{
                paramSelect.value = paramsToShow[0];
            }}
        }}
        
        function updateTimeDisplay() {{
            const slider = document.getElementById('timeSlider');
            const display = document.getElementById('timeDisplay');
            const time = currentData.times[slider.value];
            
            if (time) {{
                display.textContent = time.substring(0, 2) + ':' + time.substring(2);
            }}
        }}
        
        function updateOpacity() {{
            const slider = document.getElementById('opacitySlider');
            const value = slider.value;
            document.getElementById('opacityValue').textContent = value + '%';
            
            const currentLayerId = `forecast-layer-${{activeLayer}}`;
            if (map && map.getLayer(currentLayerId)) {{
                map.setPaintProperty(currentLayerId, 'raster-opacity', value / 100);
            }}
        }}
        
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
                    updateImageSource();
                }}, speed);
            }}
        }}
        
        // Event listeners
        document.getElementById('dateSelect').addEventListener('change', (e) => loadDateData(e.target.value));
        document.getElementById('paramSelect').addEventListener('change', () => {{
            updateImageSource();
            preloadImages();
        }});
        document.getElementById('domainSelect').addEventListener('change', () => {{
            updateImageSource();
            preloadImages();
        }});
        document.getElementById('styleSelect').addEventListener('change', (e) => {{
            console.log('Changing map style to:', e.target.value);
            map.setStyle(e.target.value);
        }});
        document.getElementById('expertMode').addEventListener('change', (e) => {{
            expertMode = e.target.checked;
            updateParameterDropdown();
            updateImageSource();
            preloadImages();
        }});
        document.getElementById('timeSlider').addEventListener('input', () => {{
            updateTimeDisplay();
            updateImageSource();
        }});
        document.getElementById('opacitySlider').addEventListener('input', updateOpacity);
        document.getElementById('playBtn').addEventListener('click', togglePlay);
        
        document.getElementById('timePrev').addEventListener('click', () => {{
            const slider = document.getElementById('timeSlider');
            if (parseInt(slider.value) > 0) {{
                slider.value = parseInt(slider.value) - 1;
                updateTimeDisplay();
                updateImageSource();
            }}
        }});
        document.getElementById('timeNext').addEventListener('click', () => {{
            const slider = document.getElementById('timeSlider');
            if (parseInt(slider.value) < parseInt(slider.max)) {{
                slider.value = parseInt(slider.value) + 1;
                updateTimeDisplay();
                updateImageSource();
            }}
        }});
        
        // Mobile controls - three state system
        const controlsPanel = document.getElementById('controlsPanel');
        const controlsToggle = document.getElementById('controlsToggle');
        const closeControls = document.getElementById('closeControls');
        const stateIndicator = document.getElementById('stateIndicator');
        let controlState = 'expanded'; // expanded, small, or away
        
        function updateStateIndicator() {{
            stateIndicator.textContent = controlState === 'small' ? 's' : controlState === 'away' ? 'x' : '';
        }}
        
        function setControlState(newState) {{
            controlState = newState;
            if (newState === 'expanded') {{
                controlsPanel.classList.remove('collapsed', 'small');
                controlsToggle.style.display = 'none';
            }} else if (newState === 'small') {{
                controlsPanel.classList.remove('collapsed');
                controlsPanel.classList.add('small');
                controlsToggle.style.display = 'flex';
            }} else {{
                controlsPanel.classList.add('collapsed');
                controlsToggle.style.display = 'flex';
            }}
            updateStateIndicator();
        }}
        
        controlsToggle.addEventListener('click', () => {{
            if (controlState === 'away') {{
                setControlState('expanded');
            }} else if (controlState === 'expanded') {{
                setControlState('small');
            }} else {{
                setControlState('away');
            }}
        }});
        
        closeControls.addEventListener('click', () => {{
            setControlState('away');
        }});
        
        document.getElementById('map').addEventListener('click', (e) => {{
            if (window.innerWidth <= 768 && controlState === 'expanded') {{
                setControlState('small');
            }}
        }});
        
        window.addEventListener('resize', () => {{
            if (window.innerWidth > 768) {{
                setControlState('expanded');
            }}
        }});
        
        // Help modal
        document.getElementById('helpText').textContent = helpText;
        
        document.getElementById('helpBtn').addEventListener('click', () => {{
            document.getElementById('helpModal').classList.add('active');
        }});
        
        document.getElementById('helpCloseBtn').addEventListener('click', () => {{
            document.getElementById('helpModal').classList.remove('active');
        }});
        
        document.getElementById('helpModal').addEventListener('click', (e) => {{
            if (e.target.id === 'helpModal') {{
                document.getElementById('helpModal').classList.remove('active');
            }}
        }});
        
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape') {{
                document.getElementById('helpModal').classList.remove('active');
                document.getElementById('soundingPopup').classList.remove('active');
                currentSoundingSite = null;
            }}
        }});
        
        // Close sounding popup
        document.getElementById('closeSounding').addEventListener('click', () => {{
            document.getElementById('soundingPopup').classList.remove('active');
            currentSoundingSite = null;
        }});
        
        // =====================================================
        // GPS LOCATION TRACKING
        // =====================================================
        
        let gpsMarker = null;
        let gpsAccuracyCircle = null;
        let watchId = null;
        let locationEnabled = false;
        
        function createGpsMarker() {{
            // Create marker element
            const el = document.createElement('div');
            el.className = 'gps-marker';
            
            // Add pulse effect
            const pulse = document.createElement('div');
            pulse.className = 'gps-marker-pulse';
            el.appendChild(pulse);
            
            return el;
        }}
        
        function updateGpsPosition(position) {{
            const {{ latitude, longitude, accuracy }} = position.coords;
            const lngLat = [longitude, latitude];
            
            console.log(`GPS position: ${{latitude}}, ${{longitude}} (accuracy: ${{accuracy}}m)`);
            
            // Create or update marker
            if (!gpsMarker) {{
                gpsMarker = new mapboxgl.Marker({{
                    element: createGpsMarker(),
                    anchor: 'center'
                }})
                .setLngLat(lngLat)
                .addTo(map);
            }} else {{
                gpsMarker.setLngLat(lngLat);
            }}
            
            // Create or update accuracy circle
            const accuracyCircleId = 'gps-accuracy-circle';
            const metersPerPixel = 156543.03392 * Math.cos(latitude * Math.PI / 180) / Math.pow(2, map.getZoom());
            const radiusInPixels = accuracy / metersPerPixel;
            
            // Use a source/layer for the accuracy circle
            if (map.getSource(accuracyCircleId)) {{
                map.getSource(accuracyCircleId).setData({{
                    type: 'Feature',
                    geometry: {{
                        type: 'Point',
                        coordinates: lngLat
                    }},
                    properties: {{
                        accuracy: accuracy
                    }}
                }});
            }} else {{
                map.addSource(accuracyCircleId, {{
                    type: 'geojson',
                    data: {{
                        type: 'Feature',
                        geometry: {{
                            type: 'Point',
                            coordinates: lngLat
                        }},
                        properties: {{
                            accuracy: accuracy
                        }}
                    }}
                }});
                
                map.addLayer({{
                    id: accuracyCircleId,
                    type: 'circle',
                    source: accuracyCircleId,
                    paint: {{
                        'circle-radius': {{
                            stops: [
                                [0, 0],
                                [20, accuracy * 1000]
                            ],
                            base: 2
                        }},
                        'circle-color': 'rgba(74, 158, 255, 0.15)',
                        'circle-stroke-color': 'rgba(74, 158, 255, 0.3)',
                        'circle-stroke-width': 1,
                        'circle-pitch-alignment': 'map'
                    }}
                }}, 'forecast-layer-A'); // Add below forecast layer
            }}
            
            // Update button state
            const btn = document.getElementById('locationBtn');
            btn.classList.remove('searching');
            btn.classList.add('active');
        }}
        
        function handleGpsError(error) {{
            console.error('GPS error:', error);
            const btn = document.getElementById('locationBtn');
            btn.classList.remove('searching', 'active');
            
            let message = 'Unable to get location';
            switch (error.code) {{
                case error.PERMISSION_DENIED:
                    message = 'Location permission denied';
                    break;
                case error.POSITION_UNAVAILABLE:
                    message = 'Location unavailable';
                    break;
                case error.TIMEOUT:
                    message = 'Location request timed out';
                    break;
            }}
            alert(message);
            disableLocationTracking();
        }}
        
        function enableLocationTracking() {{
            if (!navigator.geolocation) {{
                alert('Geolocation is not supported by your browser');
                return;
            }}
            
            const btn = document.getElementById('locationBtn');
            btn.classList.add('searching');
            locationEnabled = true;
            
            // Get initial position and fly to it
            navigator.geolocation.getCurrentPosition(
                (position) => {{
                    updateGpsPosition(position);
                    map.flyTo({{
                        center: [position.coords.longitude, position.coords.latitude],
                        zoom: Math.max(map.getZoom(), 10)
                    }});
                }},
                handleGpsError,
                {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }}
            );
            
            // Start watching position
            watchId = navigator.geolocation.watchPosition(
                updateGpsPosition,
                handleGpsError,
                {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 5000 }}
            );
        }}
        
        function disableLocationTracking() {{
            locationEnabled = false;
            
            if (watchId !== null) {{
                navigator.geolocation.clearWatch(watchId);
                watchId = null;
            }}
            
            // Remove marker
            if (gpsMarker) {{
                gpsMarker.remove();
                gpsMarker = null;
            }}
            
            // Remove accuracy circle
            if (map.getLayer('gps-accuracy-circle')) {{
                map.removeLayer('gps-accuracy-circle');
            }}
            if (map.getSource('gps-accuracy-circle')) {{
                map.removeSource('gps-accuracy-circle');
            }}
            
            const btn = document.getElementById('locationBtn');
            btn.classList.remove('active', 'searching');
        }}
        
        document.getElementById('locationBtn').addEventListener('click', () => {{
            if (locationEnabled) {{
                disableLocationTracking();
            }} else {{
                enableLocationTracking();
            }}
        }});
        
        // Initialize
        initMap();
    </script>
</body>
</html>
'''


def generate_static_site():
    """Generate the complete static site."""
    print("🌤️  RASP Static Site Generator (Mapbox GL with Lambert Projection)")
    print("=" * 60)
    
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
        'd1': domain_objs['d1'].get_domain_bounds(use_square_image=True),
        'd2': domain_objs['d2'].get_domain_bounds(),
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
    
    # Read help.txt content
    print("📖 Loading help text...")
    help_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'help.txt')
    help_text = ""
    if os.path.exists(help_file_path):
        with open(help_file_path, 'r') as f:
            help_text = f.read()
    else:
        help_text = "Help file not found."
    
    # Generate HTML
    print("📝 Generating index.html with Mapbox GL Lambert projection...")
    
    if MAPBOX_ACCESS_TOKEN == 'YOUR_MAPBOX_ACCESS_TOKEN_HERE':
        print("⚠️  WARNING: Using placeholder Mapbox token!")
        print("   Get your token from: https://account.mapbox.com/access-tokens/")
        print("   Update MAPBOX_ACCESS_TOKEN in generate_static_site_mapbox_gl.py")
    
    html = generate_html(domain_bounds, manifest, help_text, MAPBOX_ACCESS_TOKEN)
    
    with open(os.path.join(DOCS_DIR, 'index.html'), 'w') as f:
        f.write(html)
    
    # Create .nojekyll file for GitHub Pages
    with open(os.path.join(DOCS_DIR, '.nojekyll'), 'w') as f:
        pass
    
    print("=" * 60)
    print(f"✅ Static site generated successfully!")
    print(f"   📁 Output: {DOCS_DIR}")
    print(f"   📅 Dates: {len(dates)}")
    print(f"   🖼️  Images: {total_images}")
    print(f"   🗺️  Projection: Lambert Conformal Conic")
    print()
    print("Features:")
    print("  • Mapbox GL with native Lambert Conformal projection")
    print("  • Proper geographic registration of WRF forecast imagery")
    print("  • No image warping - uses correct map projection")
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
