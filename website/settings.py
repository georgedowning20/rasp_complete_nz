"""Shared configuration for the static site generator."""

# Configuration
RESULTS_DIR = '/Users/georgedowning/Desktop/Rasp_complete/results'
OUT_DIR = f"{RESULTS_DIR}/OUT"
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
        # 'ref_lat': -37.8239,
        # 'ref_lon': 175.7604,
    },
    'd3': {
        'dx': 500, 'dy': 500,
        'e_we': 81, 'e_sn': 81,
        'i_parent_start': 46, 'j_parent_start': 131,
        'parent_grid_ratio': 4,
        'ref_lat': -37.1386,
        'ref_lon': 175.5593,
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
    'press950': 'Wave 950mb (~2,000ft)',
    'press850': 'Wave 850mb (~5,000ft)',
    'press700': 'Wave 700mb (~10,000ft)',
    'press500': 'Wave 500mb (~18,000ft)',
    'stars': 'Star Rating',
    'xcspeed': 'XC Speed',
    'pfd_tot': 'Potential Flight Distance (Total)',
    'ridgelift': 'Ridge Lift (Vertical Velocity ~300ft AGL)',
    'sh2o': 'Soil Moisture content',
    'smcrel': 'Soil Moisture Relative',
    'sfcmoist': 'Surface Soil Moisture',
    'qfx': 'Surface Moisture Flux',
    'dbz': 'Radar Reflectivity',
}

# 'qfx', 'sfcmoist'', 'sh2o', 'smcrel' 

# Sounding locations
# 1,Auckland,d1,174.7633,-36.8485,
# 2,Wellington,d1,174.7762,-41.2865,
# 3,Hamilton,d1,175.2793,-37.7870,
# 4,Taupo,d1,176.0702,-38.6857,
# 5,Rotorua,d1,176.2497,-38.1368,
# 6,Napier,d1,176.9120,-39.4928,
# 7,NewPlymouth,d1,174.0752,-39.0556,
# 8,Matamata,d1,175.7700,-37.8100,
# 9,Drury,d1,174.9500,-37.1000,
# 10,Thames,d1,175.5593,-37.1386,
# 11,Tauranga,d1,176.1667,-37.6861,
# 12,Taumarunui,d1,175.2833,-38.8667,
# 13,Raglan,d1,174.8833,-37.8000,
# 14,Turangi,d1,175.8000,-38.9833,
SOUNDING_SITES = {
    '1': {'name': 'Auckland', 'lat': -36.8485, 'lon': 174.7633},
    '2': {'name': 'Wellington', 'lat': -41.2865, 'lon': 174.7762},
    '3': {'name': 'Hamilton', 'lat': -37.7870, 'lon': 175.2793},
    '4': {'name': 'Taupo', 'lat': -38.6857, 'lon': 176.0702},
    '5': {'name': 'Rotorua', 'lat': -38.1368, 'lon': 176.2497},
    '6': {'name': 'Napier', 'lat': -39.4928, 'lon': 176.9120},
    '7': {'name': 'NewPlymouth', 'lat': -39.0556, 'lon': 174.0752},
    '8': {'name': 'Matamata', 'lat': -37.8100, 'lon': 175.7700},
    '9': {'name': 'Drury', 'lat': -37.1000, 'lon': 174.9500},
    '10': {'name': 'Thames', 'lat': -37.1386, 'lon': 175.5593},
    '11': {'name': 'Tauranga', 'lat': -37.6861, 'lon': 176.1667},
    '12': {'name': 'Taumarunui', 'lat': -38.8667, 'lon': 175.2833},
    '13': {'name': 'Raglan', 'lat': -37.8000, 'lon': 174.8833},
    '14': {'name': 'Turangi', 'lat': -38.9833, 'lon': 175.8000},
}
