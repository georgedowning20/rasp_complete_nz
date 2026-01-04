#!/usr/bin/env python3
"""
RASP PNG Overlay Map Viewer
Overlays generated RASP weather images on an interactive map.
Properly handles Lambert Conformal projection from WRF output.
"""

import os
import glob
import re
import math
from pathlib import Path

try:
    import folium
    from folium import plugins
except ImportError:
    print("Installing folium...")
    os.system("pip install folium")
    import folium
    from folium import plugins

try:
    from PIL import Image
    import base64
    from io import BytesIO
except ImportError:
    print("Installing Pillow...")
    os.system("pip install Pillow")
    from PIL import Image
    import base64
    from io import BytesIO

try:
    import pyproj
except ImportError:
    print("Installing pyproj...")
    os.system("pip install pyproj")
    import pyproj


class LambertConformalDomain:
    """
    Calculate WRF Lambert Conformal Conic domain bounds.
    """
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
        self.e_we = e_we  # number of grid points in x (west-east)
        self.e_sn = e_sn  # number of grid points in y (south-north)
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
        
        # WGS84 for lat/lon
        self.proj_latlon = pyproj.Proj(proj='latlong', datum='WGS84')
        
        # Create transformer
        self.transformer_to_latlon = pyproj.Transformer.from_proj(
            self.proj, self.proj_latlon, always_xy=True
        )
        self.transformer_to_lcc = pyproj.Transformer.from_proj(
            self.proj_latlon, self.proj, always_xy=True
        )
        
    def get_domain_bounds(self):
        """
        Calculate the lat/lon bounds of the domain corners.
        Returns bounds as [[south, west], [north, east]] for folium.
        """
        # Reference point is at domain center in projection coordinates
        ref_x, ref_y = self.transformer_to_lcc.transform(self.ref_lon, self.ref_lat)
        
        # For nested domain, calculate offset from parent
        if self.parent is not None:
            # Get parent's lower-left corner in projection coords
            parent_ref_x, parent_ref_y = self.transformer_to_lcc.transform(
                self.parent.ref_lon, self.parent.ref_lat
            )
            # Parent domain half-widths
            parent_half_x = (self.parent.e_we - 1) * self.parent.dx / 2.0
            parent_half_y = (self.parent.e_sn - 1) * self.parent.dy / 2.0
            # Parent lower-left corner
            parent_ll_x = parent_ref_x - parent_half_x
            parent_ll_y = parent_ref_y - parent_half_y
            
            # Nested domain lower-left corner relative to parent
            # i_parent_start and j_parent_start are 1-indexed
            nest_ll_x = parent_ll_x + (self.i_parent_start - 1) * self.parent.dx
            nest_ll_y = parent_ll_y + (self.j_parent_start - 1) * self.parent.dy
            
            # Nested domain upper-right
            nest_ur_x = nest_ll_x + (self.e_we - 1) * self.dx
            nest_ur_y = nest_ll_y + (self.e_sn - 1) * self.dy
        else:
            # For parent domain: ref point is at center
            half_x = (self.e_we - 1) * self.dx / 2.0
            half_y = (self.e_sn - 1) * self.dy / 2.0
            
            nest_ll_x = ref_x - half_x
            nest_ll_y = ref_y - half_y
            nest_ur_x = ref_x + half_x
            nest_ur_y = ref_y + half_y
        
        # Convert corners to lat/lon
        ll_lon, ll_lat = self.transformer_to_latlon.transform(nest_ll_x, nest_ll_y)
        ur_lon, ur_lat = self.transformer_to_latlon.transform(nest_ur_x, nest_ur_y)
        lr_lon, lr_lat = self.transformer_to_latlon.transform(nest_ur_x, nest_ll_y)
        ul_lon, ul_lat = self.transformer_to_latlon.transform(nest_ll_x, nest_ur_y)
        
        # Store all corners for polygon drawing
        self.corners = {
            'll': (ll_lat, ll_lon),
            'lr': (lr_lat, lr_lon),
            'ur': (ur_lat, ur_lon),
            'ul': (ul_lat, ul_lon),
        }
        
        # For folium ImageOverlay, we need axis-aligned bounds
        # Use min/max of all corners
        min_lat = min(ll_lat, lr_lat, ur_lat, ul_lat)
        max_lat = max(ll_lat, lr_lat, ur_lat, ul_lat)
        min_lon = min(ll_lon, lr_lon, ur_lon, ul_lon)
        max_lon = max(ll_lon, lr_lon, ur_lon, ul_lon)
        
        return [[min_lat, min_lon], [max_lat, max_lon]]
    
    def get_corner_polygon(self):
        """Get corners as a polygon for more accurate boundary display."""
        if not hasattr(self, 'corners'):
            self.get_domain_bounds()
        return [
            self.corners['ll'],
            self.corners['lr'],
            self.corners['ur'],
            self.corners['ul'],
            self.corners['ll'],  # close the polygon
        ]


# WRF Domain configuration from namelist.wps
# NZ Configuration with Lambert Conformal projection
WRF_CONFIG = {
    'ref_lat': -38.50,
    'ref_lon': 176.00,
    'truelat1': -35.00,
    'truelat2': -42.00,
    'stand_lon': 176.00,
    'd1': {
        'dx': 6000,
        'dy': 6000,
        'e_we': 80,
        'e_sn': 100,
    },
    'd2': {
        'dx': 2000,
        'dy': 2000,
        'e_we': 70,
        'e_sn': 70,
        'i_parent_start': 25,
        'j_parent_start': 52,
        'parent_grid_ratio': 3,
    }
}

def create_domains():
    """Create domain objects with proper projection."""
    # Parent domain (d1)
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
    
    # Nested domain (d2)
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


# Create domain objects
DOMAIN_OBJS = create_domains()

# Domain info for map display
DOMAINS = {
    'd1': {
        'name': 'NZ Outer (6km)',
        'bounds': DOMAIN_OBJS['d1'].get_domain_bounds(),
        'polygon': DOMAIN_OBJS['d1'].get_corner_polygon(),
        'center': [WRF_CONFIG['ref_lat'], WRF_CONFIG['ref_lon']],
    },
    'd2': {
        'name': 'Matamata (2km)',
        'bounds': DOMAIN_OBJS['d2'].get_domain_bounds(),
        'polygon': DOMAIN_OBJS['d2'].get_corner_polygon(),
        'center': [-37.81, 175.77],
    }
}


def find_png_files(results_dir):
    """Find all body PNG files in the results directory."""
    png_files = []
    
    # Look for PNG files in various locations
    search_paths = [
        os.path.join(results_dir, 'OUT', '**', '*.body.png'),
        os.path.join(results_dir, 'NZ', 'OUT', '**', '*.body.png'),
        os.path.join(results_dir, '**', '*.body.png'),
    ]
    
    for pattern in search_paths:
        found = glob.glob(pattern, recursive=True)
        png_files.extend(found)
    
    # Remove duplicates
    png_files = list(set(png_files))
    return sorted(png_files)


def parse_filename(filename):
    """Parse RASP filename to extract parameter, time, and domain info."""
    basename = os.path.basename(filename)
    # Pattern: parameter.curr.HHMMlst.d#.body.png
    match = re.match(r'(\w+)\.curr\.(\d{4})lst\.d(\d)\.body\.png', basename)
    if match:
        return {
            'parameter': match.group(1),
            'time': match.group(2),
            'domain': f'd{match.group(3)}',
            'filename': filename
        }
    return None


def image_to_base64(image_path):
    """Convert image to base64 for embedding in HTML."""
    with Image.open(image_path) as img:
        # Convert to RGBA if not already
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode()


def create_map(results_dir, output_html='rasp_map.html'):
    """Create an interactive map with RASP overlays."""
    
    # Find PNG files
    png_files = find_png_files(results_dir)
    
    if not png_files:
        print(f"No PNG files found in {results_dir}")
        print("Looking for .body.png files...")
        # Try a broader search
        all_pngs = glob.glob(os.path.join(results_dir, '**', '*.png'), recursive=True)
        print(f"All PNGs found: {len(all_pngs)}")
        for p in all_pngs[:10]:
            print(f"  {p}")
        return None
    
    print(f"Found {len(png_files)} PNG files")
    
    # Parse file info
    images = []
    for f in png_files:
        info = parse_filename(f)
        if info:
            images.append(info)
            print(f"  {info['parameter']} @ {info['time']} ({info['domain']})")
    
    if not images:
        print("Could not parse any PNG filenames")
        return None
    
    # Create base map centered on NZ
    m = folium.Map(
        location=[-38.5, 176.0],
        zoom_start=7,
        tiles='OpenStreetMap'
    )
    
    # Add different tile layers
    folium.TileLayer('cartodbpositron', name='Light').add_to(m)
    folium.TileLayer('cartodbdark_matter', name='Dark').add_to(m)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite'
    ).add_to(m)
    
    # Group images by parameter and time
    grouped = {}
    for img in images:
        key = f"{img['parameter']}_{img['time']}_{img['domain']}"
        grouped[key] = img
    
    # Add image overlays
    for key, img in grouped.items():
        domain = img['domain']
        if domain in DOMAINS:
            bounds = DOMAINS[domain]['bounds']
            
            # Create feature group for this layer
            fg = folium.FeatureGroup(
                name=f"{img['parameter']} {img['time']} {DOMAINS[domain]['name']}",
                show=False  # Hidden by default
            )
            
            # Add image overlay
            folium.raster_layers.ImageOverlay(
                image=img['filename'],
                bounds=bounds,
                opacity=0.7,
                interactive=True,
                cross_origin=False,
            ).add_to(fg)
            
            fg.add_to(m)
    
    # Add domain boundary polygons (more accurate than rectangles)
    for domain_id, domain in DOMAINS.items():
        if 'polygon' in domain:
            folium.Polygon(
                locations=domain['polygon'],
                color='red' if domain_id == 'd1' else 'blue',
                weight=2,
                fill=False,
                popup=f"{domain['name']}<br>Bounds: {domain['bounds']}",
            ).add_to(m)
        else:
            folium.Rectangle(
                bounds=domain['bounds'],
                color='red' if domain_id == 'd1' else 'blue',
                weight=2,
                fill=False,
                popup=domain['name'],
            ).add_to(m)
    
    # Add markers for key locations
    locations = [
        {'name': 'Matamata GC', 'lat': -37.81, 'lon': 175.77},
        {'name': 'Auckland', 'lat': -36.8485, 'lon': 174.7633},
        {'name': 'Hamilton', 'lat': -37.787, 'lon': 175.2793},
        {'name': 'Taupo', 'lat': -38.6857, 'lon': 176.0702},
        {'name': 'Rotorua', 'lat': -38.1368, 'lon': 176.2497},
    ]
    
    for loc in locations:
        folium.Marker(
            location=[loc['lat'], loc['lon']],
            popup=loc['name'],
            icon=folium.Icon(color='green', icon='info-sign')
        ).add_to(m)
    
    # Add layer control
    folium.LayerControl(collapsed=False).add_to(m)
    
    # Add fullscreen button
    plugins.Fullscreen().add_to(m)
    
    # Save map
    output_path = os.path.join(results_dir, output_html)
    m.save(output_path)
    print(f"\nMap saved to: {output_path}")
    
    return output_path


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Overlay RASP PNGs on a map')
    parser.add_argument('--results-dir', '-r', 
                        default='/Users/georgedowning/Desktop/Rasp_complete/results',
                        help='Path to results directory')
    parser.add_argument('--output', '-o',
                        default='rasp_map.html',
                        help='Output HTML filename')
    
    args = parser.parse_args()
    
    print(f"Looking for RASP images in: {args.results_dir}")
    
    output = create_map(args.results_dir, args.output)
    
    if output:
        print(f"\nOpen {output} in a web browser to view the map")
        # Try to open in browser
        import webbrowser
        webbrowser.open(f'file://{output}')


if __name__ == '__main__':
    main()
