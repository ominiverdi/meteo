#!/usr/bin/env python3
import requests
import json
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Load API key from .env
api_key = os.getenv('opendata_apikey')
if not api_key:
    print("Error: opendata_apikey not found in .env file")
    exit(1)

# Create data directory
Path("data").mkdir(exist_ok=True)

def download_catalunya_radar():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Requesting Catalunya radar data URL...")
    
    # Step 1: Get Catalunya regional radar data URL
    url = "https://opendata.aemet.es/opendata/api/red/radar/regional/ba"
    headers = {'cache-control': 'no-cache'}
    params = {'api_key': api_key}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
    except requests.exceptions.ConnectionError:
        print("Connection error - likely rate limit or invalid endpoint. Wait and try again.")
        return False
    except requests.exceptions.Timeout:
        print("Request timeout. Try again later.")
        return False
    except Exception as e:
        print(f"Request failed: {e}")
        return False
    
    if response.status_code == 429:
        print("Rate limit exceeded. Wait 1 minute before trying again.")
        return False
    
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        print("Tip: 'cat' region code might not exist. Try 'coo' or check available regions.")
        return False
    
    data = response.json()
    print(f"Status: {data['descripcion']}")
    
    # Step 2: Get and print metadata
    if 'metadatos' in data:
        print(f"Fetching metadata from: {data['metadatos']}")
        meta_response = requests.get(data['metadatos'])
        if meta_response.status_code == 200:
            try:
                metadata = meta_response.json()
                print("Metadata:")
                print(json.dumps(metadata, indent=2, ensure_ascii=False))
            except:
                print("Metadata (raw text):")
                print(meta_response.text)
        else:
            print(f"Failed to fetch metadata: {meta_response.status_code}")
    
    # Step 3: Download the actual radar image
    radar_url = data['datos']
    print(f"Downloading Catalunya radar image from: {radar_url}")
    
    img_response = requests.get(radar_url)
    if img_response.status_code == 200:
        # Save with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/radar_catalunya_{timestamp}.gif"
        
        with open(filename, 'wb') as f:
            f.write(img_response.content)
        
        print(f"Catalunya radar image saved: {filename}")
        return True
    else:
        print(f"Failed to download image: {img_response.status_code}")
        return False

if __name__ == "__main__":
    download_catalunya_radar()