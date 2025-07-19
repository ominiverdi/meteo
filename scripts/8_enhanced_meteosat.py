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
import pandas as pd
from shapely.geometry import Point
import warnings
warnings.filterwarnings('ignore')

def load_radar_data():
    """Load the latest radar GeoTIFF as RGB"""
    radar_files = glob.glob('georef_data/radar_ba_*_qgis_clean.tif')
    if not radar_files:
        print("No radar files found")
        return None, None
    
    latest_radar = sorted(radar_files)[-1]
    print(f"Loading radar: {os.path.basename(latest_radar)}")
    
    with rasterio_open(latest_radar) as src:
        print(f"Radar file has {src.count} bands (RGB+Alpha)")
        
        # Read RGB bands (1=Red, 2=Green, 3=Blue)
        red = src.read(1)
        green = src.read(2) 
        blue = src.read(3)
        
        # Stack into RGB array (H, W, 3)
        radar_rgb = np.stack([red, green, blue], axis=-1)
        
        # Check if we have alpha channel
        if src.count >= 4:
            alpha = src.read(4)
            print(f"Alpha channel range: {np.min(alpha)} to {np.max(alpha)}")
            # Create RGBA array (H, W, 4)
            radar_data = np.stack([red, green, blue, alpha], axis=-1)
        else:
            radar_data = radar_rgb
        
        print(f"Radar RGB shape: {radar_data.shape}")
        print(f"RGB value range: R({np.min(red)}-{np.max(red)}), G({np.min(green)}-{np.max(green)}), B({np.min(blue)}-{np.max(blue)})")
        
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
    """Load province borders and cities from actual data files"""
    vectors = {}
    
    # Debug what fields exist in provinces shapefile
    province_file = '../naturalearthdata/ne_10m_admin_1_states_provinces.shp'
    if os.path.exists(province_file):
        provinces = gpd.read_file(province_file)
        
        # Debug: Show available fields
        print(f"Available fields in provinces shapefile: {list(provinces.columns)}")
        
        # Filter for Spain first
        spain_provinces = provinces[provinces['admin'] == 'Spain']
        
        # Check if woe_name field exists
        if 'woe_name' in provinces.columns:
            print("Available woe_name values:")
            for woe in sorted(spain_provinces['woe_name'].unique()):
                print(f"  - {woe}")
            
            # Try filtering by woe_name
            catalunya_provinces = provinces[provinces['woe_name'].isin(['Cataluña', 'Islas Baleares'])]
        else:
            print("woe_name field not found, using name field")
            # Fallback to name field
            catalunya_provinces = provinces[provinces['name'].isin([
                'Barcelona', 'Tarragona', 'Girona', 'Lleida', 'Gerona', 'Lérida', 'Baleares'
            ])]
        
        if not catalunya_provinces.empty:
            vectors['provinces'] = catalunya_provinces
            print(f"Loaded {len(catalunya_provinces)} province boundaries")
            for province in catalunya_provinces['name']:
                print(f"  - {province}")
        else:
            print("No Catalunya + Balears provinces found")
    else:
        print(f"Province file not found: {province_file}")
    
    # Load cities from OSM file
    cities_file = '../osm/catalunya_large_cities.geojson'
    if os.path.exists(cities_file):
        cities = gpd.read_file(cities_file)
        
        # Debug: Show available fields and sample data
        print(f"Available fields in cities file: {list(cities.columns)}")
        print(f"Total cities in file: {len(cities)}")
        
        # Check capital field values
        if 'capital' in cities.columns:
            print("Available capital values:")
            # Filter out None values before sorting
            capital_values = cities['capital'].dropna().unique()
            for cap in sorted(capital_values):
                print(f"  - {cap}")
            
            # Filter by capital levels 4, 6, 7
            capital_cities = cities[cities['capital'].isin(['4', '6', '7'])]
            
            if not capital_cities.empty:
                vectors['cities'] = capital_cities
                print(f"Loaded {len(capital_cities)} capital cities (levels 4,6,7)")
                for city in capital_cities['name']:
                    print(f"  - {city}")
            else:
                print("No cities with capital levels 4,6,7 found")
        else:
            print("capital field not found in cities file")
    else:
        print(f"Cities file not found: {cities_file}")
    
    return vectors

def create_enhanced_image(radar_data, radar_info, water_vapor, vectors):
    """Create combined radar + water vapor visualization with proper layering"""
    
    # Create figure with dark background
    fig, ax = plt.subplots(1, 1, figsize=(12, 10), facecolor='black')
    ax.set_facecolor('black')
    
    # Calculate extent from provinces (Catalunya + Balears) with buffer
    if vectors and 'provinces' in vectors:
        # Get province bounds in EPSG:3857
        provinces_3857 = vectors['provinces'].to_crs('EPSG:3857')
        prov_bounds = provinces_3857.total_bounds  # [minx, miny, maxx, maxy]
        
        # Add buffer (30km)
        buffer_km = 30000  # 30km in meters
        extent_bounds = {
            'left': prov_bounds[0] - buffer_km,
            'right': prov_bounds[2] + buffer_km,
            'bottom': prov_bounds[1] - buffer_km,
            'top': prov_bounds[3] + buffer_km
        }
        
        print(f"Province extent with {buffer_km/1000}km buffer: {extent_bounds}")
    else:
        # Fallback to radar bounds if no provinces
        radar_bounds = radar_info['bounds']
        extent_bounds = {
            'left': radar_bounds.left,
            'right': radar_bounds.right,
            'bottom': radar_bounds.bottom,
            'top': radar_bounds.top
        }
        print(f"Using radar extent as fallback: {extent_bounds}")
    
    # Convert to matplotlib extent format
    extent = [extent_bounds['left'], extent_bounds['right'], extent_bounds['bottom'], extent_bounds['top']]
    
    # Layer 1: Water vapor background
    if water_vapor and 'wv_6.2' in water_vapor:
        wv_data = water_vapor['wv_6.2']['data']
        wv_bounds = water_vapor['wv_6.2']['bounds']
        wv_extent = [wv_bounds.left, wv_bounds.right, wv_bounds.bottom, wv_bounds.top]
        
        print(f"Water vapor extent: {wv_bounds}")
        
        # Normalize water vapor data (brightness temperature)
        wv_valid = wv_data[~np.isnan(wv_data)]
        if len(wv_valid) > 0:
            wv_min, wv_max = np.percentile(wv_valid, [5, 95])
            wv_normalized = np.clip((wv_data - wv_min) / (wv_max - wv_min), 0, 1)
            
            ax.imshow(wv_normalized, extent=wv_extent, cmap='gray', 
                     alpha=0.6, origin='upper', interpolation='bilinear')
            print("Water vapor layer added")
    
    # Layer 2: Vector overlays
    if vectors:
        # Province boundaries
        if 'provinces' in vectors:
            vectors['provinces'].to_crs('EPSG:3857').plot(
                ax=ax, facecolor='none', edgecolor='yellow', linewidth=1.5, alpha=0.8
            )
            print("Province boundaries added")
        
        # City labels and icons
        if 'cities' in vectors:
            cities_3857 = vectors['cities'].to_crs('EPSG:3857')
            
            # Cities to show labels for (removed Sabadell)
            label_cities = ['Girona', 'Barcelona', 'Terrassa', 'Manresa', 'Tarragona', 'Olot', 'Lleida','Palma','Perpinyà']
            
            for idx, city in cities_3857.iterrows():
                x, y = city.geometry.x, city.geometry.y
                name = city['name:ca']
                
                # Check if city is within province extent + buffer
                if (extent_bounds['left'] <= x <= extent_bounds['right'] and 
                    extent_bounds['bottom'] <= y <= extent_bounds['top']):
                    
                    # Add city point (icon for all capital cities)
                    ax.plot(x, y, 'o', color='white', markersize=6, 
                           markeredgecolor='black', markeredgewidth=1)
                    
                    # Add city label only for specific cities
                    if name in label_cities:
                        ax.text(x + 3000, y + 3000, name, fontsize=10, color='white', 
                               weight='bold', ha='left', va='bottom',
                               bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.2))
            
            print("Cities added")
    
    # Layer 3: Radar data (RGB) - Display as-is with AEMET colors
    radar_bounds = radar_info['bounds']
    radar_extent = [radar_bounds.left, radar_bounds.right, radar_bounds.bottom, radar_bounds.top]
    
    print(f"Radar RGB data shape: {radar_data.shape}")
    
    if radar_data.shape[-1] == 4:  # RGBA
        # For RGBA, make transparent where alpha is 0 or RGB is black
        alpha = radar_data[:, :, 3]
        rgb = radar_data[:, :, :3]
        
        # Create transparency mask - transparent where alpha=0 OR all RGB channels are 0 (black)
        is_transparent = (alpha == 0) | ((rgb[:,:,0] == 0) & (rgb[:,:,1] == 0) & (rgb[:,:,2] == 0))
        
        # Convert to 0-1 range for matplotlib
        radar_display = radar_data.astype(np.float32) / 255.0
        
        # Set transparent pixels to alpha=0
        radar_display[is_transparent, 3] = 0.0
        
        # Display RGB image with original AEMET colors
        im = ax.imshow(radar_display, extent=radar_extent, origin='upper', interpolation='nearest')
        
        non_transparent_pixels = np.sum(~is_transparent)
        print(f"Radar layer added - {non_transparent_pixels} precipitation pixels (RGB+Alpha)")
        
    elif radar_data.shape[-1] == 3:  # RGB only
        # For RGB, make transparent where all channels are 0 (black)
        is_black = (radar_data[:,:,0] == 0) & (radar_data[:,:,1] == 0) & (radar_data[:,:,2] == 0)
        
        # Convert to 0-1 range for matplotlib
        radar_display = radar_data.astype(np.float32) / 255.0
        
        # Create RGBA array with alpha channel
        rgba_display = np.zeros((*radar_data.shape[:2], 4), dtype=np.float32)
        rgba_display[:,:,:3] = radar_display
        rgba_display[:,:,3] = 1.0  # Full opacity
        rgba_display[is_black, 3] = 0.0  # Transparent for black pixels
        
        # Display RGB image
        im = ax.imshow(rgba_display, extent=radar_extent, origin='upper', interpolation='nearest')
        
        non_black_pixels = np.sum(~is_black)
        print(f"Radar layer added - {non_black_pixels} precipitation pixels (RGB)")
    
    else:
        print(f"Warning: Unexpected radar data shape: {radar_data.shape}")
    
    # Styling - Trim to province extent + buffer
    ax.set_xlim(extent_bounds['left'], extent_bounds['right'])
    ax.set_ylim(extent_bounds['bottom'], extent_bounds['top'])
    
    # Title with date and time
    radar_filename = os.path.basename(radar_info['file'])
    parts = radar_filename.split('_')
    date_part = parts[2]  # 20250712
    time_part = parts[3]  # 161417
    
    # Format date: 20250712 -> 12 Jul 2025
    year = date_part[:4]
    month = date_part[4:6]
    day = date_part[6:8]
    months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    date_str = f"{int(day)} {months[int(month)]} {year}"
    
    # Format time: 161417 -> 16:14 CET
    time_str = f"{time_part[:2]}:{time_part[2:4]} CET"
    
    ax.set_title(f'radar + meteosat: #{date_str} {time_str}', 
                fontsize=16, pad=20, color='white', weight='bold')
    
    # Remove ticks for clean appearance
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
    
    if fig is None:
        print("Failed to create visualization")
        return
    
    # Save image with full datetime in filename
    radar_filename = os.path.basename(radar_info['file'])
    # Extract full datetime: radar_ba_20250712_161417_qgis_clean.tif
    parts = radar_filename.split('_')
    date_part = parts[2]  # 20250712
    time_part = parts[3]  # 161417
    full_datetime = f"{date_part}_{time_part}"  # 20250712_161417
    
    output_file = output_dir / f"enhanced_weather_{full_datetime}.png"
    
    fig.savefig(output_file, dpi=300, bbox_inches='tight', 
                facecolor='black', edgecolor='none')
    plt.close(fig)
    
    print(f"Enhanced image saved: {output_file}")
    print(f"Size: {os.path.getsize(output_file) / 1024:.1f} KB")

if __name__ == "__main__":
    main()