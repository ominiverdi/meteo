#!/usr/bin/env python3
import requests
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

def download_radar():
    # Step 1: Get radar data URL
    url = "https://opendata.aemet.es/opendata/api/red/radar/nacional"
    headers = {'cache-control': 'no-cache'}
    params = {'api_key': api_key}
    
    print("Requesting radar data URL...")
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 429:
        print("Rate limit exceeded. Wait 1 minute before trying again.")
        return False
    
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return False
    
    data = response.json()
    print(f"Status: {data['descripcion']}")
    
    # Step 2: Download the actual radar image
    radar_url = data['datos']
    print(f"Downloading radar image from: {radar_url}")
    
    img_response = requests.get(radar_url)
    if img_response.status_code == 200:
        # Save with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/radar_nacional_{timestamp}.gif"
        
        with open(filename, 'wb') as f:
            f.write(img_response.content)
        
        print(f"Radar image saved: {filename}")
        return True
    else:
        print(f"Failed to download image: {img_response.status_code}")
        return False

if __name__ == "__main__":
    download_radar()
    