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
import shutil
from pathlib import Path

from settings import (
    RESULTS_DIR,
    OUT_DIR,
    DOCS_DIR,
    MAPBOX_ACCESS_TOKEN,
    PARAMETER_INFO,
    SOUNDING_SITES,
)
from projection import create_domains
from favicon import create_favicon
from data_pipeline import copy_images, get_available_data, get_available_dates
from templating import generate_html


def generate_static_site():
    """Generate the complete static site."""
    print("🌤️  RASP Static Site Generator (Mapbox GL with Lambert Projection)")
    print("=" * 60)

    cname_content = None
    if os.path.exists(DOCS_DIR):
        cname_path = os.path.join(DOCS_DIR, 'CNAME')
        if os.path.exists(cname_path):
            with open(cname_path, 'r') as f:
                cname_content = f.read()
        print("📁 Cleaning existing docs folder...")
        shutil.rmtree(DOCS_DIR)

    os.makedirs(DOCS_DIR)
    if cname_content:
        with open(os.path.join(DOCS_DIR, 'CNAME'), 'w') as f:
            f.write(cname_content)
    data_dir = os.path.join(DOCS_DIR, 'data')
    os.makedirs(data_dir)

    print("📐 Calculating domain bounds...")
    domain_objs = create_domains()
    domain_bounds = {
        'd1': domain_objs['d1'].get_domain_bounds(use_square_image=True),
        'd2': domain_objs['d2'].get_domain_bounds(),
        'd3': domain_objs['d3'].get_domain_bounds(),
    }

    print("📅 Scanning available forecast data...")
    dates = get_available_dates()
    manifest = {}
    total_images = 0

    for date in dates:
        print(f"   Processing {date}...")
        data = get_available_data(date)
        manifest[date] = data

        dest_dir = os.path.join(data_dir, date)
        count = copy_images(date, dest_dir)
        total_images += count
        print(f"      Copied {count} images")

    create_favicon(DOCS_DIR)

    print("📖 Loading help text...")
    help_file_path = Path(__file__).parent / 'help.txt'
    help_text = help_file_path.read_text() if help_file_path.exists() else "Help file not found."

    print("📝 Generating index.html with Mapbox GL Lambert projection...")
    if MAPBOX_ACCESS_TOKEN == 'YOUR_MAPBOX_ACCESS_TOKEN_HERE':
        print("⚠️  WARNING: Using placeholder Mapbox token!")
        print("   Get your token from: https://account.mapbox.com/access-tokens/")
        print("   Update MAPBOX_ACCESS_TOKEN in generate_static_site_mapbox_gl.py")

    html = generate_html(
        domain_bounds,
        manifest,
        help_text,
        MAPBOX_ACCESS_TOKEN,
        PARAMETER_INFO,
        SOUNDING_SITES,
    )
    (Path(DOCS_DIR) / 'index.html').write_text(html)

    (Path(DOCS_DIR) / '.nojekyll').write_text('')

    print("=" * 60)
    print("✅ Static site generated successfully!")
    print(f"   📁 Output: {DOCS_DIR}")
    print(f"   📅 Dates: {len(dates)}")
    print(f"   🖼️  Images: {total_images}")
    print("   🗺️  Projection: Lambert Conformal Conic")
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
