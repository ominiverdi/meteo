#!/usr/bin/env python3
"""
Download Meteosat water vapor data matching radar timing
"""
import os
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import shutil

try:
    import eumdac
except ImportError:
    print("❌ EUMDAC not installed. Run: pip install eumdac")
    sys.exit(1)

def load_radar_metadata(json_path):
    """Load timing from radar JSON"""
    print(f"📡 Loading radar metadata from: {json_path}")
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # Parse UTC datetime
    radar_time = datetime.fromisoformat(data['datetime_utc'].replace('Z', '+00:00'))
    
    print(f"🕐 Radar observation time: {radar_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    return {
        'datetime': radar_time,
        'date': data['date'],
        'time_utc': data['time_utc'],
        'radar_id': data.get('radar_id', 'unknown')
    }

def setup_eumdac():
    """Setup EUMDAC authentication"""
    print("🔑 Setting up EUMDAC authentication...")
    
    load_dotenv()
    
    consumer_key = os.getenv('eumetsat_consumer_key')
    consumer_secret = os.getenv('eumetsat_consumer_secret')
    
    if not consumer_key or not consumer_secret:
        print("❌ Missing EUMETSAT credentials in .env file")
        sys.exit(1)
    
    try:
        credentials = (consumer_key, consumer_secret)
        token = eumdac.AccessToken(credentials)
        datastore = eumdac.DataStore(token)
        
        print(f"✓ Token expires: {token.expiration}")
        return datastore
        
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        sys.exit(1)

def find_meteosat_collections(datastore):
    """Find Meteosat collections available"""
    print("\n🛰️ Searching for Meteosat collections...")
    
    meteosat_collections = []
    
    # Look for MSG/SEVIRI collections
    target_collections = [
        'EO:EUM:DAT:MSG:HRSEVIRI',  # High Rate SEVIRI - main target
        'EO:EUM:DAT:MSG:MSG15-RSS', # Rapid Scan SEVIRI
        'EO:EUM:DAT:MSG:CLM',       # Cloud Mask
    ]
    
    for collection_id in target_collections:
        try:
            collection = datastore.get_collection(collection_id)
            meteosat_collections.append(collection)
            print(f"✓ Found: {collection_id}")
        except Exception as e:
            print(f"❌ Not available: {collection_id}")
    
    if not meteosat_collections:
        print("❌ No Meteosat collections found. Check your license.")
        sys.exit(1)
    
    return meteosat_collections

def search_matching_data(collection, radar_metadata):
    """Search for Meteosat data matching radar timing"""
    radar_time = radar_metadata['datetime']
    
    # Search window: ±30 minutes around radar time
    search_start = radar_time - timedelta(minutes=30)
    search_end = radar_time + timedelta(minutes=30)
    
    print(f"\n🔍 Searching {collection} for water vapor data:")
    print(f"   Time window: {search_start.strftime('%H:%M')} - {search_end.strftime('%H:%M')} UTC")
    print(f"   Geographic area: Spain/Barcelona region")
    
    try:
        # Search with geographic filter for Spain area
        products = collection.search(
            dtstart=search_start,
            dtend=search_end,
            bbox='-10, 35, 15, 50'  # Spain area (West, South, East, North)
        )
        
        print(f"✓ Found {products.total_results} matching products")
        
        # Show details of found products
        product_list = list(products)
        for i, product in enumerate(product_list[:3]):  # Show first 3
            print(f"   {i+1}. {product}")
        
        if len(product_list) > 3:
            print(f"   ... and {len(product_list)-3} more products")
        
        return product_list
        
    except Exception as e:
        print(f"❌ Search failed: {e}")
        return []

def download_meteosat_data(products, output_dir="meteosat_data"):
    """Download the matching Meteosat products"""
    if not products:
        print("❌ No products to download")
        return []
    
    Path(output_dir).mkdir(exist_ok=True)
    
    print(f"\n⬇️ Downloading {len(products)} Meteosat products to {output_dir}/...")
    
    downloaded_files = []
    
    for i, product in enumerate(products[:2]):  # Limit to 2 for testing
        try:
            print(f"   📦 Downloading {i+1}/{min(len(products), 2)}: {product}")
            
            with product.open() as fsrc:
                output_file = Path(output_dir) / fsrc.name
                
                with open(output_file, 'wb') as fdst:
                    shutil.copyfileobj(fsrc, fdst)
                
                print(f"   ✓ Saved: {output_file.name}")
                downloaded_files.append(str(output_file))
                
        except Exception as e:
            print(f"   ❌ Download failed: {e}")
    
    return downloaded_files

def main():
    print("🌧️ Meteosat Water Vapor Data Download")
    print("="*50)
    
    # Path to radar metadata
    radar_json = "georef_data/radar_ba_20250712_161417_color_scale.json"
    
    if not os.path.exists(radar_json):
        print(f"❌ Radar JSON not found: {radar_json}")
        print("Expected: scripts/georef_data/radar_ba_20250712_161417_color_scale.json")
        sys.exit(1)
    
    # Load radar timing
    radar_metadata = load_radar_metadata(radar_json)
    
    # Setup EUMDAC
    datastore = setup_eumdac()
    
    # Find available Meteosat collections
    collections = find_meteosat_collections(datastore)
    
    # Search each collection for matching data
    all_products = []
    for collection in collections:
        products = search_matching_data(collection, radar_metadata)
        all_products.extend(products)
    
    if all_products:
        print(f"\n📊 Total products found: {len(all_products)}")
        
        # Download the data
        downloaded_files = download_meteosat_data(all_products)
        
        if downloaded_files:
            print(f"\n🎉 Success! Downloaded {len(downloaded_files)} files:")
            for file in downloaded_files:
                print(f"   📁 {os.path.basename(file)}")
            
            print(f"\n📍 Radar time: {radar_metadata['datetime'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"📍 Meteosat data: within ±30 minutes")
            print(f"📍 Geographic coverage: Spain/Barcelona region")
        
    else:
        print("\n❌ No matching Meteosat data found")
        print("   Try expanding the time window or check data availability")

if __name__ == "__main__":
    main()