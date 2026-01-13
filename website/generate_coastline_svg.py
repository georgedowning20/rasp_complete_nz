#!/usr/bin/env python3
"""Generate NZ coastline SVG for lazy mode overlay using Natural Earth data."""

import os
import sys

def download_and_extract_coastline():
    """Download Natural Earth coastline data."""
    try:
        import geopandas as gpd
    except ImportError:
        print("Installing required packages...", file=sys.stderr)
        os.system(f"{sys.executable} -m pip install geopandas shapely -q")
        import geopandas as gpd
    
    print("Loading Natural Earth coastline data...", file=sys.stderr)
    
    # Try multiple sources for Natural Earth data
    urls_to_try = [
        "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip",
        "https://github.com/nvkelso/natural-earth-vector/raw/master/geojson/ne_10m_admin_0_countries.geojson",
    ]
    
    import tempfile
    import urllib.request
    
    for url in urls_to_try:
        try:
            print(f"Trying to download from {url}...", file=sys.stderr)
            
            if url.endswith('.geojson'):
                # Direct GeoJSON download
                temp_file = os.path.join(tempfile.gettempdir(), "ne_countries.geojson")
                urllib.request.urlretrieve(url, temp_file)
                world = gpd.read_file(temp_file)
            else:
                # Zip file download
                import zipfile
                temp_dir = tempfile.mkdtemp()
                zip_path = os.path.join(temp_dir, "ne_coastline.zip")
                urllib.request.urlretrieve(url, zip_path)
                
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Find the shapefile
                shp_files = [f for f in os.listdir(temp_dir) if f.endswith('.shp')]
                if not shp_files:
                    continue
                world = gpd.read_file(os.path.join(temp_dir, shp_files[0]))
            
            # Filter for New Zealand
            nz = world[world.NAME.str.contains('New Zealand', case=False, na=False)]
            
            if nz.empty:
                nz = world[world.ADMIN.str.contains('New Zealand', case=False, na=False)] if 'ADMIN' in world.columns else None
            
            if nz is not None and not nz.empty:
                print(f"Successfully loaded NZ coastline data from {url}", file=sys.stderr)
                return nz.geometry.iloc[0]
                
        except Exception as e:
            print(f"Failed with {url}: {e}", file=sys.stderr)
            continue
    
    print("All download attempts failed, using fallback data", file=sys.stderr)
    return None

def generate_coastline_for_domain(domain='d2'):
    """Generate coastline SVG for a specific domain with proper bounds."""
    from projection import create_domains
    
    try:
        from shapely.geometry import box
        from shapely.ops import transform
        import geopandas as gpd
    except ImportError:
        print("Installing required packages...", file=sys.stderr)
        os.system(f"{sys.executable} -m pip install geopandas shapely -q")
        from shapely.geometry import box
        from shapely.ops import transform
        import geopandas as gpd
    
    # Get domain bounds
    domains = create_domains()
    domain_obj = domains[domain]
    domain_info = domain_obj.get_domain_bounds()
    corners = domain_info['corners']
    
    lats = [c[0] for c in corners]
    lons = [c[1] for c in corners]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    
    print(f"Domain {domain} bounds: lat [{min_lat:.2f}, {max_lat:.2f}], lon [{min_lon:.2f}, {max_lon:.2f}]", file=sys.stderr)
    
    # Get NZ coastline geometry
    nz_geom = download_and_extract_coastline()
    
    if nz_geom is None:
        print("Failed to load coastline data, returning empty SVG", file=sys.stderr)
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600"></svg>'
    
    # Clip coastline to projected domain bounds
    projected_bounds = domain_info.get('projected_bounds')
    if not projected_bounds:
        print(f"Warning: Domain {domain} has no projected bounds", file=sys.stderr)
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600"></svg>'

    proj_min_x, proj_min_y = projected_bounds[0]
    proj_max_x, proj_max_y = projected_bounds[1]
    domain_box = box(proj_min_x, proj_min_y, proj_max_x, proj_max_y)

    projected_geom = transform(domain_obj.transformer_to_lcc.transform, nz_geom)
    clipped = projected_geom.intersection(domain_box)
    
    # Determine target SVG dimensions based on domain
    if domain == 'd1':
        svg_width = 1000
        svg_height = 1000
    elif domain == 'd3':
        svg_width = 1000
        svg_height = 1000
    else:  # d2
        svg_width = 1000
        svg_height = 1000
    
    # Convert geometry to SVG path in projected space
    path_parts = []

    proj_span_x = max(proj_max_x - proj_min_x, 1e-6)
    proj_span_y = max(proj_max_y - proj_min_y, 1e-6)

    def process_linestring(coords):
        """Convert a projected linestring to SVG path commands."""
        parts = []
        for i, (proj_x, proj_y) in enumerate(coords):
            # Convert to SVG coordinates directly in target dimensions
            x = ((proj_x - proj_min_x) / proj_span_x) * svg_width
            y = ((proj_max_y - proj_y) / proj_span_y) * svg_height

            if i == 0:
                parts.append(f"M {x:.1f},{y:.1f}")
            else:
                parts.append(f"L {x:.1f},{y:.1f}")
        return parts
    
    # Handle different geometry types
    if clipped.geom_type == 'MultiPolygon':
        for polygon in clipped.geoms:
            # Exterior ring
            coords = list(polygon.exterior.coords)
            path_parts.extend(process_linestring(coords))
            path_parts.append("Z")
    elif clipped.geom_type == 'Polygon':
        coords = list(clipped.exterior.coords)
        path_parts.extend(process_linestring(coords))
        path_parts.append("Z")
    elif clipped.geom_type == 'MultiLineString':
        for line in clipped.geoms:
            coords = list(line.coords)
            path_parts.extend(process_linestring(coords))
    elif clipped.geom_type == 'LineString':
        coords = list(clipped.coords)
        path_parts.extend(process_linestring(coords))
    elif clipped.geom_type == 'GeometryCollection':
        for geom in clipped.geoms:
            if geom.geom_type in ['Polygon', 'LineString']:
                if geom.geom_type == 'Polygon':
                    coords = list(geom.exterior.coords)
                else:
                    coords = list(geom.coords)
                path_parts.extend(process_linestring(coords))
    
    if len(path_parts) == 0:
        print(f"Warning: No coastline found in domain {domain}", file=sys.stderr)
        viewbox = f"0 0 {svg_width} {svg_height}"
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}"></svg>'
    
    path = " ".join(path_parts)
    
    viewbox = f"0 0 {svg_width} {svg_height}"

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" preserveAspectRatio="none">
  <path d="{path}" stroke="white" stroke-width="3" fill="none" opacity="0.8"/>
</svg>'''
    
    return svg

def save_coastline_svgs(output_dir):
    """Generate and save coastline SVG files for all domains.
    
    Args:
        output_dir: Directory to save SVG files to
    """
    os.makedirs(output_dir, exist_ok=True)
    
    for domain in ['d1', 'd2', 'd3']:
        print(f"Generating {domain} coastline...", file=sys.stderr)
        svg = generate_coastline_for_domain(domain)
        
        output_path = os.path.join(output_dir, f'coastline_{domain}.svg')
        with open(output_path, 'w') as f:
            f.write(svg)
        print(f"  Saved to {output_path}", file=sys.stderr)

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--js':
        # Generate JavaScript object with both domains (legacy)
        print("const COASTLINE_SVG = {")
        for domain in ['d1', 'd2']:
            print(f"Generating {domain} coastline SVG...", file=sys.stderr)
            svg = generate_coastline_for_domain(domain)
            # Escape for JavaScript string
            svg_escaped = svg.replace("'", "\\'").replace("\n", "").replace("  ", "")
            print(f"  '{domain}': '{svg_escaped}',")
        print("};")
    elif len(sys.argv) > 2 and sys.argv[1] == '--output':
        # Save SVG files to specified directory
        save_coastline_svgs(sys.argv[2])
    else:
        print("Usage:")
        print("  python generate_coastline_svg.py --output <directory>  # Save SVG files")
        print("  python generate_coastline_svg.py --js                   # Print JavaScript object")
        sys.exit(1)



