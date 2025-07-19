#!/usr/bin/env python3
"""
Create enhanced meteorological images combining radar and water vapor data
"""

import os
import json
import glob
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LinearSegmentedColormap
import geopandas as gpd
from rasterio import open as rasterio_open
from rasterio.plot import show
from rasterio.warp import transform_bounds
import warnings
warnings.filterwarnings('ignore')

def load_radar_data():
    """Load the latest radar GeoTIFF"""
    radar_files = glob.glob('georef_data/radar_ba_*_qgis_clean.tif')
    if not radar_files:
        print("No radar files found")
        return None, None
    
    latest_radar = sorted(radar_files)[-1]
    print(f"Loading radar: {os.path.basename(latest_radar)}")
    
    with rasterio_open(latest_radar) as src:
        radar_data = src.read(1)
        radar_transform = src.transform
        radar_crs = src.crs
        radar_bounds = src.bounds
        
    return radar_data, {
        'transform': radar_transform,
        'crs': radar_crs,
        'bounds': radar_bounds,
        'file': latest_radar
    }

def load_water_vapor_data():
    """Load water vapor GeoTIFFs"""
    wv_files = glob.glob('meteosat_data/processed/wv_*.tif')
    if not wv_files:
        print("No water vapor files found")
        return None
    
    water_vapor = {}
    for wv_file in wv_files:
        filename = os.path.basename(wv_file)
        if '6.2um' in filename:
            band = 'wv_6.2'
        elif '7.3um' in filename:
            band = 'wv_7.3'
        else:
            continue
            
        print(f"Loading water vapor: {filename}")
        with rasterio_open(wv_file) as src:
            water_vapor[band] = {
                'data': src.read(1),
                'transform': src.transform,
                'crs': src.crs,
                'bounds': src.bounds
            }
    
    return water_vapor

def load_vector_data():
    """Load province borders and cities"""
    vectors = {}
    
    # Province borders
    province_file = '../naturalearthdata/ne_10m_admin_1_states_provinces.shp'
    if os.path.exists(province_file):
        provinces = gpd.read_file(province_file)
        # Filter Catalunya provinces
        catalunya_provinces = provinces[provinces['name'].isin(['Barcelona', 'Tarragona'])]
        if not catalunya_provinces.empty:
            vectors['provinces'] = catalunya_provinces
            print(f"Loaded {len(catalunya_provinces)} province boundaries")
    
    # Cities
    cities_file = '../osm/catalunya_large_cities.geojson'
    if os.path.exists(cities_file):
        cities = gpd.read_file(cities_file)
        # Filter out non-Catalunya cities
        catalunya_cities = cities[~cities['name'].isin(['Perpignan'])]
        vectors['cities'] = catalunya_cities.head(8)  # Top 8 cities
        print(f"Loaded {len(vectors['cities'])} cities")
    
    return vectors

def create_enhanced_image(radar_data, radar_info, water_vapor, vectors):
    """Create combined radar + water vapor visualization"""
    
    # Create figure
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    
    # Get radar bounds for extent
    bounds = radar_info['bounds']
    extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]
    
    # 1. Background: Water vapor (if available)
    if water_vapor and 'wv_6.2' in water_vapor:
        wv_data = water_vapor['wv_6.2']['data']
        # Normalize and show with low opacity
        wv_normalized = (wv_data - np.nanmin(wv_data)) / (np.nanmax(wv_data) - np.nanmin(wv_data))
        ax.imshow(wv_normalized, extent=extent, cmap='gray', alpha=0.5, origin='upper')
    
    # 2. Foreground: Radar data
    # Create radar colormap (blue for precipitation)
    radar_colors = ['#000000', '#0000ff', '#00ffff', '#00ff00', '#ffff00', '#ff8000', '#ff0000', '#c8005a']
    radar_cmap = LinearSegmentedColormap.from_list('radar', radar_colors)
    
    # Mask transparent pixels
    radar_masked = np.ma.masked_where(radar_data == 0, radar_data)
    
    if radar_masked.count() > 0:
        ax.imshow(radar_masked, extent=extent, cmap=radar_cmap, alpha=0.8, origin='upper')
    
    # 3. Vector overlays
    if vectors:
        # Province boundaries
        if 'provinces' in vectors:
            vectors['provinces'].to_crs('EPSG:3857').plot(
                ax=ax, facecolor='none', edgecolor='yellow', linewidth=2
            )
        
        # City labels
        if 'cities' in vectors:
            cities_3857 = vectors['cities'].to_crs('EPSG:3857')
            for idx, city in cities_3857.iterrows():
                x, y = city.geometry.x, city.geometry.y
                name = city['name']
                
                # Add city point and label
                ax.plot(x, y, 'o', color='white', markersize=4, markeredgecolor='black')
                ax.text(x + 2000, y + 2000, name, fontsize=8, color='white', 
                       weight='bold', ha='left', va='bottom',
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='black', alpha=0.7))
    
    # Styling
    ax.set_xlim(bounds.left, bounds.right)
    ax.set_ylim(bounds.bottom, bounds.top)
    ax.set_title('Catalunya Weather: Radar + Water Vapor', fontsize=14, pad=20)
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    
    # Remove axis ticks for cleaner look
    ax.set_xticks([])
    ax.set_yticks([])
    
    return fig

def main():
    print("Enhanced Meteosat Visualization")
    print("=" * 40)
    
    # Create output directory
    output_dir = Path("meteosat_data/enhanced")
    output_dir.mkdir(exist_ok=True)
    
    # Load data
    print("\nLoading data...")
    radar_data, radar_info = load_radar_data()
    if radar_data is None:
        print("No radar data found")
        return
    
    water_vapor = load_water_vapor_data()
    vectors = load_vector_data()
    
    # Create visualization
    print("\nCreating enhanced visualization...")
    fig = create_enhanced_image(radar_data, radar_info, water_vapor, vectors)
    
    # Save image
    timestamp = radar_info['file'].split('_')[3].split('.')[0]  # Extract timestamp
    output_file = output_dir / f"enhanced_weather_{timestamp}.png"
    
    fig.savefig(output_file, dpi=300, bbox_inches='tight', 
                facecolor='black', edgecolor='none')
    plt.close(fig)
    
    print(f"Enhanced image saved: {output_file}")
    print(f"Size: {os.path.getsize(output_file) / 1024:.1f} KB")

if __name__ == "__main__":
    main()