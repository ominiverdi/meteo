#!/usr/bin/env python3
"""
Download Catalunya administrative boundaries and cities from OSM
"""

import os
import json
import requests
from pathlib import Path

def download_osm_data(query, output_file):
    """Download data from Overpass API"""
    
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    try:
        response = requests.post(overpass_url, data=query, timeout=60)
        response.raise_for_status()
        
        osm_data = response.json()
        
        # Convert to GeoJSON
        features = []
        for element in osm_data.get('elements', []):
            if element['type'] == 'node':
                feature = {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [element['lon'], element['lat']]
                    },
                    'properties': element.get('tags', {})
                }
                features.append(feature)
            elif element['type'] == 'relation':
                # Basic relation info (geometry handling is complex)
                feature = {
                    'type': 'Feature',
                    'geometry': None,
                    'properties': element.get('tags', {})
                }
                features.append(feature)
        
        geojson = {
            'type': 'FeatureCollection',
            'features': features
        }
        
        # Save file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        
        print(f"Downloaded {len(features)} features to {output_file}")
        return len(features)
        
    except Exception as e:
        print(f"Error: {e}")
        return 0

def main():
    Path("../osm").mkdir(exist_ok=True)
    

    
    # Cities with population data
    cities_query = """
[out:json][bbox:38.1,-0.7,42.9,4.4];
node["place"~"city|town"]["population"];
out;
"""
    

    
    print("Downloading Catalunya cities...")
    city_count = download_osm_data(cities_query, "../osm/catalunya_cities.geojson")
    
    # Filter cities >100k
    if city_count > 0:
        print("Filtering large cities by population...")
        
        with open("../osm/catalunya_cities.geojson", 'r') as f:
            data = json.load(f)
        
        large_cities = []
        for feature in data['features']:
            pop_str = feature['properties'].get('population', '0')
            try:
                population = int(pop_str.replace(',', '').replace('.', ''))
                if population > 30000:
                    feature['properties']['population_int'] = population
                    large_cities.append(feature)
            except:
                pass
        
        # Sort by population
        large_cities.sort(key=lambda x: x['properties']['population_int'], reverse=True)
        
        filtered_data = {
            'type': 'FeatureCollection',
            'features': large_cities
        }
        
        with open("../osm/catalunya_large_cities.geojson", 'w') as f:
            json.dump(filtered_data, f, ensure_ascii=False, indent=2)
        
        print(f"Filtered {len(large_cities)} cities >100k population")
        for city in large_cities:
            name = city['properties'].get('name', 'Unknown')
            pop = city['properties']['population_int']
            print(f"  {name}: {pop:,}")

if __name__ == "__main__":
    main()