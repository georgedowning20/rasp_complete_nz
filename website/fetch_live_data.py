#!/usr/bin/env python3
"""
Fetch live data from external APIs during site generation.

This module handles:
- Weather station ID discovery from Windy Stations API
- Webcam fetching from Windy Webcam API

Both use a shared bounding box for filtering to a specific region.
"""

import requests


def fetch_weather_station_ids(weather_config, bounds):
    """Fetch online weather station IDs from Windy API.
    
    Scans all pages of the Windy opendata API to find online stations
    within the specified bounds.
    """
    if not weather_config.get('enabled') or not weather_config.get('api_key'):
        print("   ⚠️  Weather stations disabled or no API key")
        return weather_config
    
    api_key = weather_config['api_key']
    api_url = weather_config.get('api_url', 'https://stations.windy.com/api/v2')
    
    print("   🌡️  Scanning for weather stations...")
    
    try:
        station_ids = []
        page = 0
        total_pages = 1
        
        while page < total_pages:
            response = requests.get(
                f"{api_url}/opendata/station?key={api_key}&page={page}",
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            pagination = data.get('pagination', {})
            total_pages = pagination.get('totalPages', 1)
            
            for s in data.get('data', []):
                if not s.get('is_online'):
                    continue
                lat, lon = s.get('lat'), s.get('lon')
                if lat is None or lon is None:
                    continue
                if (bounds['min_lat'] <= lat <= bounds['max_lat'] and 
                    bounds['min_lon'] <= lon <= bounds['max_lon']):
                    station_ids.append({
                        'id': s['id'],
                        'name': s.get('name', s['id']),
                        'lat': lat,
                        'lon': lon
                    })
            
            page += 1
            if page % 30 == 0:
                print(f"      Scanned {page}/{total_pages} pages, found {len(station_ids)} stations...")
        
        print(f"   ✅ Found {len(station_ids)} online weather stations")
        
        # Extract just the IDs for backward compatibility
        station_id_list = [s['id'] for s in station_ids]
        
        updated_config = weather_config.copy()
        updated_config['station_ids'] = station_id_list
        updated_config['station_locations'] = station_ids  # Store full location data
        return updated_config
        
    except Exception as e:
        print(f"   ⚠️  Error fetching station IDs: {e}")
        return weather_config


def fetch_webcams_from_api(webcams_config, bounds):
    """Fetch webcams from Windy API filtered by bounds.
    
    Uses multiple search points to cover the entire domain since API limits radius to 250km.
    """
    if not webcams_config.get('api_mode') or not webcams_config.get('api_key'):
        print("   ⚠️  Webcam API mode disabled or no API key")
        return webcams_config
    
    api_key = webcams_config['api_key']
    limit = webcams_config.get('max_webcams', 50)
    
    # Calculate multiple search points to cover the entire D1 domain
    # D1 domain spans ~400km N-S and ~300km E-W, so we need multiple overlapping searches
    domain_center_lat = (bounds['min_lat'] + bounds['max_lat']) / 2
    domain_center_lon = (bounds['min_lon'] + bounds['max_lon']) / 2
    
    # Use 4 search points to cover the domain comprehensively
    search_points = [
        (domain_center_lat, domain_center_lon),  # Center
        (bounds['min_lat'] + 1.5, bounds['min_lon'] + 1.5),  # Southwest
        (bounds['max_lat'] - 1.5, bounds['max_lon'] - 1.5),  # Northeast  
        (bounds['min_lat'] + 1.5, bounds['max_lon'] - 1.5),  # Southeast
        (bounds['max_lat'] - 1.5, bounds['min_lon'] + 1.5),  # Northwest
    ]
    
    radius = 200  # Use 200km radius to allow some overlap
    
    print("   📷 Fetching webcams from Windy API using multiple search points...")
    
    all_webcams = {}
    
    for i, (lat, lon) in enumerate(search_points):
        print(f"   📷 Search point {i+1}/{len(search_points)}: {lat:.2f}, {lon:.2f}")
        
        url = f"https://api.windy.com/webcams/api/v3/webcams?nearby={lat},{lon},{radius}&limit={limit}&include=images,location"
        
        try:
            response = requests.get(url, headers={'x-windy-api-key': api_key}, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            webcam_list = data.get('webcams', [])
            print(f"      Found {len(webcam_list)} webcams at this location")
            
            for cam in webcam_list:
                if cam.get('status') != 'active':
                    continue
                
                cam_id = str(cam.get('webcamId', ''))
                if not cam_id or cam_id in all_webcams:  # Skip duplicates
                    continue
                
                location = cam.get('location', {})
                cam_lat, cam_lon = location.get('latitude'), location.get('longitude')
                
                if cam_lat is None or cam_lon is None:
                    continue
                if not (bounds['min_lat'] <= cam_lat <= bounds['max_lat'] and 
                        bounds['min_lon'] <= cam_lon <= bounds['max_lon']):
                    continue
                
                images = cam.get('images', {}).get('current', {})
                
                all_webcams[cam_id] = {
                    'name': cam.get('title', 'Unknown'),
                    'lat': cam_lat,
                    'lon': cam_lon,
                    'image': images.get('preview', ''),
                }
                
        except Exception as e:
            print(f"      ⚠️  Error fetching from point {i+1}: {e}")
            continue
    
    print(f"   📷 Received {len(all_webcams)} unique webcams from API")
    
    cameras = {}
    for cam_id, cam_data in all_webcams.items():
        cameras[cam_id] = cam_data
    
    print(f"   ✅ Found {len(cameras)} webcams in bounds")
    
    updated_config = webcams_config.copy()
    updated_config['cameras'] = cameras
    updated_config['fetched_from_api'] = True
    return updated_config
