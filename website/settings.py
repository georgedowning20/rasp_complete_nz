"""Shared configuration for the static site generator."""

import os
from pathlib import Path

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    # python-dotenv not installed, will use system environment variables
    pass

# Configuration
RESULTS_DIR = '/Users/georgedowning/Desktop/Rasp_complete/results'
OUT_DIR = f"{RESULTS_DIR}/OUT"
DOCS_DIR = '/Users/georgedowning/Desktop/Rasp_complete/docs'

# Mapbox Configuration
# Get your access token from https://account.mapbox.com/access-tokens/
# Load from environment variable for security
MAPBOX_ACCESS_TOKEN = os.getenv('MAPBOX_ACCESS_TOKEN', '')

# WRF Domain configuration - Mercator projection
#  ref_lat   = -44.50,
#  ref_lon   = 170.00,
#  truelat1  = -42.00,
#  truelat2  = -47.00,
#  stand_lon = 170.00,

WRF_CONFIG = {
    # 'ref_lat': -38.50,
    # 'ref_lon': 176.00,
    # 'truelat1': -35.00,
    # 'truelat2': -42.00,
    # 'stand_lon': 176.00,
    'ref_lat': -44.50,
    'ref_lon': 170.00,
    'truelat1': -42.00,
    'truelat2': -47.00,
    'stand_lon': 170.00,

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

# Shared North Island bounding box (used for both webcams and weather stations)
# Now matches the D1 WRF domain bounds
ISLAND_BOUNDS = {
    'min_lat': -46.4132,  # Southernmost sounding site (Invercargill)
    'max_lat': -42.5270,  # Northernmost sounding site (Hanmer Springs)
    'min_lon': 167.7180,  # Westernmost sounding site (Te Anau)
    'max_lon': 172.8290   # Easternmost sounding site (Hanmer Springs)
}

# Weather Station Data Configuration
# Uses Windy Stations API - station IDs are discovered during site generation
WEATHER_STATIONS = {
    'enabled': True,
    # Station IDs will be populated during site generation by scanning the Windy API
    'station_ids': [],  # Populated at build time
    # Windy Staos.getenv('WEATHER_STATIONS_API_KEY', '')
    'api_key': '9e293a6becb034b720f7dc36d5cdbb68b3e681d46667169fb83b49750a0390cf',
    'api_url': 'https://stations.windy.com/api/v2',
    'refresh_interval': 300000,  # 5 minutes in milliseconds
}

# Webcam Configuration
# Uses Windy Webcam API to fetch webcams during site generation
WEBCAMS = {
    'enabled': True,
    'cameras': {},  # Will be populated from API during site generation
    # Windy Webcam API configuration
    'api_key': os.getenv('WEBCAMS_API_KEY', ''),
    'api_mode': True,  # Fetch webcams from API during site generation
    'max_webcams': 50,  # Max allowed is 50 per request per search point
    # Uses ISLAND_BOUNDS for filtering and calculating search points
}

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
# SOUNDING_SITES = {
#     '1': {'name': 'Auckland', 'lat': -36.8485, 'lon': 174.7633},
#     '2': {'name': 'Wellington', 'lat': -41.2865, 'lon': 174.7762},
#     '3': {'name': 'Hamilton', 'lat': -37.7870, 'lon': 175.2793},
#     '4': {'name': 'Taupo', 'lat': -38.6857, 'lon': 176.0702},
#     '5': {'name': 'Rotorua', 'lat': -38.1368, 'lon': 176.2497},
#     '6': {'name': 'Napier', 'lat': -39.4928, 'lon': 176.9120},
#     '7': {'name': 'NewPlymouth', 'lat': -39.0556, 'lon': 174.0752},
#     '8': {'name': 'Matamata', 'lat': -37.8100, 'lon': 175.7700},
#     '9': {'name': 'Drury', 'lat': -37.1000, 'lon': 174.9500},
#     '10': {'name': 'Thames', 'lat': -37.1386, 'lon': 175.5593},
#     '11': {'name': 'Tauranga', 'lat': -37.6861, 'lon': 176.1667},
#     '12': {'name': 'Taumarunui', 'lat': -38.8667, 'lon': 175.2833},
#     '13': {'name': 'Raglan', 'lat': -37.8000, 'lon': 174.8833},
#     '14': {'name': 'Turangi', 'lat': -38.9833, 'lon': 175.8000},
# }


# 1,Omarama,d1,169.9650,-44.4860,
# 2,Queenstown,d1,168.7332,-45.0312,
# 3,Wanaka,d1,169.2430,-44.7000,
# 4,MtCook,d1,170.0980,-43.7350,
# 5,Christchurch,d1,172.5320,-43.4895,
# 6,Ashburton,d1,171.7470,-43.9060,
# 7,Timaru,d1,171.2540,-44.3960,
# 8,Tekapo,d1,170.4770,-44.0050,
# 9,Alexandra,d1,169.3800,-45.2490,
# 10,Geraldine,d1,171.2460,-44.0910,
# 11,HanmerSprings,d1,172.8290,-42.5270,
# 12,Springfield,d1,171.9310,-43.3470,
# 13,Invercargill,d1,168.3538,-46.4132,
# 14,TeAnau,d1,167.7180,-45.4145,

SOUNDING_SITES = {
    '1': {'name': 'Omarama', 'lat': -44.4860, 'lon': 169.9650},
    '2': {'name': 'Queenstown', 'lat': -45.0312, 'lon': 168.7332},
    '3': {'name': 'Wanaka', 'lat': -44.7000, 'lon': 169.2430},
    '4': {'name': 'Mt Cook', 'lat': -43.7350, 'lon': 170.0980},
    '5': {'name': 'Christchurch', 'lat': -43.4895, 'lon': 172.5320},
    '6': {'name': 'Ashburton', 'lat': -43.9060, 'lon': 171.7470},
    '7': {'name': 'Timaru', 'lat': -44.3960, 'lon': 171.2540},
    '8': {'name': 'Tekapo', 'lat': -44.0050, 'lon': 170.4770},
    '9': {'name': 'Alexandra', 'lat': -45.2490, 'lon': 169.3800},
    '10': {'name': 'Geraldine', 'lat': -44.0910, 'lon': 171.2460},
    '11': {'name': 'Hanmer Springs', 'lat': -42.5270, 'lon': 172.8290},
    '12': {'name': 'Springfield', 'lat': -43.3470, 'lon': 171.9310},
    '13': {'name': 'Invercargill', 'lat': -46.4132, 'lon': 168.3538},
    '14': {'name': 'Te Anau', 'lat': -45.4145, 'lon': 167.7180},
}

