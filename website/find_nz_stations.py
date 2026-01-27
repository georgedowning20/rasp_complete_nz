#!/usr/bin/env python3
import requests
import json

api_key = '9e293a6becb034b720f7dc36d5cdbb68b3e681d46667169fb83b49750a0390cf'
base_url = 'https://stations.windy.com/api/v2/opendata/station'

# NZ bounds
min_lat, max_lat = -47.5, -34.0
min_lon, max_lon = 165.0, 179.0

nz_stations = []
page = 0

print("Scanning all pages for NZ stations...")

while True:
    url = f'{base_url}?key={api_key}&page={page}'
    resp = requests.get(url)
    data = resp.json()
    stations = data.get('data', [])
    pagination = data.get('pagination', {})
    
    for s in stations:
        lat = s.get('lat', 0)
        lon = s.get('lon', 0)
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            nz_stations.append(s)
    
    page += 1
    if page >= pagination.get('totalPages', 1):
        break
    if page % 20 == 0:
        print(f'Scanned {page}/{pagination.get("totalPages", 0)} pages, found {len(nz_stations)} NZ stations...')

print(f'\nTotal NZ stations found: {len(nz_stations)}')
online_count = sum(1 for s in nz_stations if s.get('is_online'))
print(f'Online: {online_count}, Offline: {len(nz_stations) - online_count}')

print('\nNZ Stations:')
for s in sorted(nz_stations, key=lambda x: not x.get('is_online')):
    status = 'ONLINE' if s.get('is_online') else 'offline'
    name = s.get('name', 'Unknown')[:40]
    print(f'  {s["id"]:12} {name:40} lat={s["lat"]:7.2f} lon={s["lon"]:7.2f} {status}')
