"""Projection utilities for the RASP static site generator."""

import os
import re
from pathlib import Path

try:
    import pyproj
except ImportError:  # pragma: no cover - runtime install if missing
    print("Installing pyproj...")
    os.system("pip install pyproj")
    import pyproj

from settings import WRF_CONFIG, OUT_DIR


HEADER_PATTERN = re.compile(
    r"Grid=\s*(d\d)\s+Reskm=\s*([-\d.]+)\s+Indexs=\s*"
    r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+Proj=\s*mercator\s+"
    r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)",
    re.IGNORECASE,
)


def _parse_domain_from_data_file(file_path):
    """Parse a RASP .data file header and return domain projection metadata."""
    try:
        content = Path(file_path).read_text(errors='ignore')
    except OSError:
        return None

    match = HEADER_PATTERN.search(content)
    if not match:
        return None

    (
        grid,
        _reskm,
        i_start,
        i_end,
        j_start,
        j_end,
        dx,
        dy,
        truelat1,
        truelat2,
        stand_lon,
        ref_lat,
        ref_lon,
    ) = match.groups()

    e_we = int(i_end) - int(i_start) + 1
    e_sn = int(j_end) - int(j_start) + 1

    return {
        'grid': grid.lower(),
        'dx': float(dx),
        'dy': float(dy),
        'e_we': e_we,
        'e_sn': e_sn,
        'truelat1': float(truelat1),
        'truelat2': float(truelat2),
        'stand_lon': float(stand_lon),
        'ref_lat': float(ref_lat),
        'ref_lon': float(ref_lon),
    }


def _load_runtime_domain_config():
    """Load latest domain geometry from runtime .data files in OUT_DIR."""
    out_path = Path(OUT_DIR)
    if not out_path.exists():
        return {}

    dated_dirs = sorted(
        [d for d in out_path.iterdir() if d.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}", d.name)],
        reverse=True,
    )

    domains = {}
    for date_dir in dated_dirs:
        for data_file in sorted(date_dir.glob('*.data')):
            parsed = _parse_domain_from_data_file(data_file)
            if not parsed:
                continue
            grid = parsed['grid']
            if grid not in domains:
                domains[grid] = parsed
            if {'d1', 'd2', 'd3'}.issubset(domains.keys()):
                return domains
        if domains:
            return domains

    return domains


class MercatorDomain:
    """Calculate WRF Mercator domain bounds."""

    def __init__(self, ref_lat, ref_lon, truelat1, truelat2, stand_lon,
                 dx, dy, e_we, e_sn, parent=None, i_parent_start=1, j_parent_start=1,
                 parent_grid_ratio=1, use_custom_center=False):
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
        self.use_custom_center = use_custom_center

        self.proj = pyproj.Proj(
            proj='merc',
            lat_ts=truelat1,
            lon_0=stand_lon,
            x_0=0,
            y_0=0,
            ellps='WGS84'
        )

        self.proj_latlon = pyproj.Proj(proj='latlong', datum='WGS84')
        self.transformer_to_latlon = pyproj.Transformer.from_proj(
            self.proj, self.proj_latlon, always_xy=True
        )
        self.transformer_to_merc = pyproj.Transformer.from_proj(
            self.proj_latlon, self.proj, always_xy=True
        )

    def get_domain_bounds(self, use_square_image=False):
        ref_x, ref_y = self.transformer_to_merc.transform(self.ref_lon, self.ref_lat)

        if self.parent is not None and not self.use_custom_center:
            # Use parent-based offset calculation for standard nested domains
            # WRF: e_we stagger points means (e_we-1) mass points spanning (e_we-1)*dx
            parent_ref_x, parent_ref_y = self.transformer_to_merc.transform(
                self.parent.ref_lon, self.parent.ref_lat
            )
            parent_half_x = (self.parent.e_we - 1) * self.parent.dx / 2.0
            parent_half_y = (self.parent.e_sn - 1) * self.parent.dy / 2.0
            parent_ll_x = parent_ref_x - parent_half_x
            parent_ll_y = parent_ref_y - parent_half_y

            # i_parent_start is 1-indexed, so subtract 1 for offset
            nest_ll_x = parent_ll_x + (self.i_parent_start - 1) * self.parent.dx
            nest_ll_y = parent_ll_y + (self.j_parent_start - 1) * self.parent.dy
            nest_ur_x = nest_ll_x + (self.e_we - 1) * self.dx
            nest_ur_y = nest_ll_y + (self.e_sn - 1) * self.dy
            
            # Adjust for WRF staggered grid: move left edge right and top edge down by one grid cell
            nest_ll_x += self.dx
            nest_ur_y -= self.dy
        elif self.parent is not None and self.use_custom_center:
            # Use custom center point for domains with explicit ref_lat/ref_lon
            # Domain spans (e_we-1) mass points, total width = (e_we-1)*dx
            half_x = (self.e_we - 1) * self.dx / 2.0
            half_y = (self.e_sn - 1) * self.dy / 2.0

            nest_ll_x = ref_x - half_x
            nest_ll_y = ref_y - half_y
            nest_ur_x = ref_x + half_x
            nest_ur_y = ref_y + half_y
            
            # Adjust for WRF staggered grid: move left edge right and top edge down by one grid cell
            nest_ll_x += self.dx
            nest_ur_y -= self.dy
        else:
            # Root domain (d1) - no parent adjustment needed
            # Domain spans (e_we-1) mass points, total width = (e_we-1)*dx
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

        self.projected_corners = {
            'll': (nest_ll_x, nest_ll_y),
            'lr': (nest_ur_x, nest_ll_y),
            'ur': (nest_ur_x, nest_ur_y),
            'ul': (nest_ll_x, nest_ur_y),
        }

        self.projected_bounds = [[nest_ll_x, nest_ll_y], [nest_ur_x, nest_ur_y]]

        return {
            'bounds': [[ll_lat, ll_lon], [ur_lat, ur_lon]],
            'corners': [
                [ll_lat, ll_lon],  # SW
                [lr_lat, lr_lon],  # SE
                [ur_lat, ur_lon],  # NE
                [ul_lat, ul_lon],  # NW
            ],
            'projected_bounds': self.projected_bounds,
            'projected_corners': [
                [nest_ll_x, nest_ll_y],  # SW
                [nest_ur_x, nest_ll_y],  # SE
                [nest_ur_x, nest_ur_y],  # NE
                [nest_ll_x, nest_ur_y],  # NW
            ]
        }


def create_domains():
    """Create domain objects with proper projection."""
    runtime = _load_runtime_domain_config()

    d1_cfg = runtime.get('d1')
    d2_cfg = runtime.get('d2')
    d3_cfg = runtime.get('d3')

    d1 = MercatorDomain(
        ref_lat=d1_cfg['ref_lat'] if d1_cfg else WRF_CONFIG['ref_lat'],
        ref_lon=d1_cfg['ref_lon'] if d1_cfg else WRF_CONFIG['ref_lon'],
        truelat1=d1_cfg['truelat1'] if d1_cfg else WRF_CONFIG['truelat1'],
        truelat2=d1_cfg['truelat2'] if d1_cfg else WRF_CONFIG['truelat2'],
        stand_lon=d1_cfg['stand_lon'] if d1_cfg else WRF_CONFIG['stand_lon'],
        dx=d1_cfg['dx'] if d1_cfg else WRF_CONFIG['d1']['dx'],
        dy=d1_cfg['dy'] if d1_cfg else WRF_CONFIG['d1']['dy'],
        e_we=d1_cfg['e_we'] if d1_cfg else WRF_CONFIG['d1']['e_we'],
        e_sn=d1_cfg['e_sn'] if d1_cfg else WRF_CONFIG['d1']['e_sn'],
    )

    d2 = MercatorDomain(
        ref_lat=d2_cfg['ref_lat'] if d2_cfg else WRF_CONFIG['ref_lat'],
        ref_lon=d2_cfg['ref_lon'] if d2_cfg else WRF_CONFIG['ref_lon'],
        truelat1=d2_cfg['truelat1'] if d2_cfg else WRF_CONFIG['truelat1'],
        truelat2=d2_cfg['truelat2'] if d2_cfg else WRF_CONFIG['truelat2'],
        stand_lon=d2_cfg['stand_lon'] if d2_cfg else WRF_CONFIG['stand_lon'],
        dx=d2_cfg['dx'] if d2_cfg else WRF_CONFIG['d2']['dx'],
        dy=d2_cfg['dy'] if d2_cfg else WRF_CONFIG['d2']['dy'],
        e_we=d2_cfg['e_we'] if d2_cfg else WRF_CONFIG['d2']['e_we'],
        e_sn=d2_cfg['e_sn'] if d2_cfg else WRF_CONFIG['d2']['e_sn'],
        parent=None if d2_cfg else d1,
        i_parent_start=WRF_CONFIG['d2']['i_parent_start'],
        j_parent_start=WRF_CONFIG['d2']['j_parent_start'],
        parent_grid_ratio=WRF_CONFIG['d2']['parent_grid_ratio'],
    )

    d3 = MercatorDomain(
        ref_lat=d3_cfg['ref_lat'] if d3_cfg else WRF_CONFIG['d3'].get('ref_lat', WRF_CONFIG['ref_lat']),
        ref_lon=d3_cfg['ref_lon'] if d3_cfg else WRF_CONFIG['d3'].get('ref_lon', WRF_CONFIG['ref_lon']),
        truelat1=d3_cfg['truelat1'] if d3_cfg else WRF_CONFIG['truelat1'],
        truelat2=d3_cfg['truelat2'] if d3_cfg else WRF_CONFIG['truelat2'],
        stand_lon=d3_cfg['stand_lon'] if d3_cfg else WRF_CONFIG['stand_lon'],
        dx=d3_cfg['dx'] if d3_cfg else WRF_CONFIG['d3']['dx'],
        dy=d3_cfg['dy'] if d3_cfg else WRF_CONFIG['d3']['dy'],
        e_we=d3_cfg['e_we'] if d3_cfg else WRF_CONFIG['d3']['e_we'],
        e_sn=d3_cfg['e_sn'] if d3_cfg else WRF_CONFIG['d3']['e_sn'],
        parent=None if d3_cfg else d2,
        i_parent_start=WRF_CONFIG['d3']['i_parent_start'],
        j_parent_start=WRF_CONFIG['d3']['j_parent_start'],
        parent_grid_ratio=WRF_CONFIG['d3']['parent_grid_ratio'],
        use_custom_center=('ref_lat' in WRF_CONFIG['d3']) and not d3_cfg,
    )

    return {'d1': d1, 'd2': d2, 'd3': d3}
