#!/usr/bin/env python3
"""
AEMET Radar Georeferencing Script
Separates footer from radar data and creates georeferenced GeoTIFFs
"""

import os
import glob
import subprocess
from pathlib import Path
from PIL import Image
import argparse
from datetime import datetime

def analyze_image_structure(image_path):
    """
    Analyze the radar image structure
    AEMET radar images have exactly 50px footer
    """
    print(f"Analyzing image structure: {os.path.basename(image_path)}")
    
    with Image.open(image_path) as img:
        width, height = img.size
        
        print(f"Image dimensions: {width}x{height}")
        
        # AEMET radar images have exactly 50px footer
        footer_height = 50
        footer_start = height - footer_height
        radar_height = footer_start
        
        print(f"Radar data area: {width}x{radar_height}")
        print(f"Footer area: {width}x{footer_height}")
        print(f"Footer starts at row: {footer_start}")
        
        return footer_start

def separate_radar_footer(input_path, output_dir="georef_data"):
    """
    Separate radar image into data and footer parts
    """
    Path(output_dir).mkdir(exist_ok=True)
    
    filename = os.path.basename(input_path)
    name_without_ext = os.path.splitext(filename)[0]
    
    footer_boundary = analyze_image_structure(input_path)
    
    with Image.open(input_path) as img:
        width, height = img.size
        
        # Extract radar data (remove footer)
        radar_data = img.crop((0, 0, width, footer_boundary))
        radar_output = os.path.join(output_dir, f"{name_without_ext}_data.gif")
        radar_data.save(radar_output)
        print(f"Radar data saved: {radar_output}")
        
        # Extract footer
        footer_data = img.crop((0, footer_boundary, width, height))
        footer_output = os.path.join(output_dir, f"{name_without_ext}_footer.gif")
        footer_data.save(footer_output)
        print(f"Footer saved: {footer_output}")
        
        return radar_output, footer_output, (width, footer_boundary)



def create_geotiff_with_gcps(radar_image_path, radar_dimensions):
    """
    Create georeferenced GeoTIFF using Ground Control Points
    Based on visible geographic features in the radar image
    """
    width, height = radar_dimensions
    
    print(f"Using Ground Control Points method")
    print(f"Image size: {width}x{height}")
    
    # Define Ground Control Points based on recognizable features
    # Format: pixel_x, pixel_y, geo_lon, geo_lat, elevation
    # Center of 480x480 image = pixel (240,240)
    
    gcps = [
        # RADAR CENTER - Most important GCP!
        (240, 240, 2.9972504844063232, 41.88895376301367, 0),  # Puig d'Arques radar
        
        # Barcelona coastline - southeast of radar
        (300, 280, 2.1734, 41.3851, 0),  # Barcelona city coast
        
        # Menorca - far southeast
        (380, 350, 4.0, 39.9, 0),  # Menorca center
        
        # Catalunya northern border - north of radar  
        (240, 120, 2.5, 42.5, 0),  # Northern Catalunya
        
        # Valencia coastline - south of radar
        (220, 380, -0.3, 39.5, 0),  # Valencia area
        
        # Pyrenees - northwest of radar
        (180, 100, 1.0, 42.8, 0),  # Pyrenees area
        
        # Mallorca - south of radar
        (300, 380, 2.9, 39.6, 0),  # Mallorca center
        
        # French coast - northeast of radar
        (320, 80, 3.5, 43.0, 0),  # Southern France coast
    ]
    
    print(f"Using {len(gcps)} Ground Control Points")
    
    # Create GCP parameters for gdal_translate
    gcp_params = []
    for i, (px, py, lon, lat, elev) in enumerate(gcps):
        gcp_params.extend(['-gcp', str(px), str(py), str(lon), str(lat), str(elev)])
        print(f"  GCP {i+1}: pixel({px},{py}) -> {lat:.3f}°N, {lon:.3f}°E")
    
    # Output file
    output_tiff = radar_image_path.replace('_data.gif', '_gcp.tif')
    
    # Create GeoTIFF with GCPs (no specific projection yet)
    cmd = [
        'gdal_translate',
        '-of', 'GTiff',
        *gcp_params,  # Add all GCP parameters
        '-co', 'COMPRESS=LZW',
        '-co', 'PHOTOMETRIC=PALETTE',
        radar_image_path,
        output_tiff
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Created GCP GeoTIFF: {output_tiff}")
        return output_tiff
    except subprocess.CalledProcessError as e:
        print(f"Error creating GCP GeoTIFF: {e}")
        return None

def create_geotiff_webmercator(gcp_tiff_path):
    """
    Create Web Mercator version from GCP-based GeoTIFF using gdalwarp transformation
    """
    if not gcp_tiff_path or not os.path.exists(gcp_tiff_path):
        return None
    
    output_webmercator = gcp_tiff_path.replace('_gcp.tif', '_epsg3857.tif')
    
    # Use gdalwarp to transform GCPs to Web Mercator with polynomial transformation
    cmd = [
        'gdalwarp',
        '-t_srs', 'EPSG:3857',  # Web Mercator
        '-r', 'near',  # Preserve colors
        '-order', '2',  # 2nd order polynomial (good for radar distortion)
        '-co', 'COMPRESS=LZW',
        '-overwrite',
        gcp_tiff_path,
        output_webmercator
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Created Web Mercator from GCPs: {output_webmercator}")
        return output_webmercator
    except subprocess.CalledProcessError as e:
        print(f"Error creating Web Mercator: {e}")
        print(f"GDAL stderr: {e.stderr}")
        return None

def check_gdal_installation():
    """
    Check if GDAL tools are available
    """
    try:
        subprocess.run(['gdal_translate', '--version'], check=True, capture_output=True)
        subprocess.run(['gdalwarp', '--version'], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: GDAL tools not found!")
        print("Install: sudo apt install gdal-bin")
        return False

def process_image(image_path):
    """
    Process radar image using Ground Control Points method
    """
    print(f"\n{'='*60}")
    print(f"Processing: {os.path.basename(image_path)}")
    print(f"Method: Ground Control Points (empirical georeferencing)")
    print(f"{'='*60}")
    
    if not check_gdal_installation():
        return None
    
    # Separate radar data and footer
    radar_output, footer_output, radar_dims = separate_radar_footer(image_path)
    
    # Create GCP-based GeoTIFF
    print(f"\nCreating GCP-based GeoTIFF...")
    gcp_tiff = create_geotiff_with_gcps(radar_output, radar_dims)
    
    # Create Web Mercator version using GCP transformation
    print(f"Transforming to Web Mercator using GCPs...")
    webmercator_tiff = create_geotiff_webmercator(gcp_tiff)
    
    print(f"\n✅ Complete!")
    print(f"📁 Files: georef_data/")
    if gcp_tiff:
        print(f"🎯 GCP-based: {os.path.basename(gcp_tiff)}")
    if webmercator_tiff:
        print(f"🗺️  Test: {os.path.basename(webmercator_tiff)} (Web Mercator)")
        print(f"\n📍 GCP method uses known geographic features!")
        print(f"   If alignment is off, we can adjust the GCP coordinates.")
    
    return radar_output

def main():
    parser = argparse.ArgumentParser(description='AEMET Radar Georeferencing - User GCPs EPSG:4326')
    parser.add_argument('--input', '-i', help='Input radar image file')
    parser.add_argument('--batch', '-b', action='store_true', help='Process all images')
    parser.add_argument('--latest', '-l', action='store_true', help='Process latest image')
    
    args = parser.parse_args()
    
    if args.input:
        if os.path.exists(args.input):
            process_image(args.input)
        else:
            print(f"File not found: {args.input}")
            return 1
    
    elif args.latest:
        today = datetime.now().strftime('%Y%m%d')
        images = sorted(glob.glob(f'data/radar_ba_{today}_*.gif'))
        if images:
            process_image(images[-1])
        else:
            print("No radar images found for today")
            return 1
    
    elif args.batch:
        images = sorted(glob.glob('data/radar_ba_*.gif'))
        if not images:
            print("No radar images found")
            return 1
        
        for image_path in images:
            try:
                process_image(image_path)
            except Exception as e:
                print(f"Error: {image_path}: {e}")
    
    else:
        print("AEMET Radar Georeferencing")
        print("Method: User-measured Ground Control Points")
        print("Usage:")
        print("  python 4_georeference.py --latest")
        print("  python 4_georeference.py --input radar.gif")
        print("Output:")
        print("  *_user_gcp.tif (EPSG:4326 - WGS84)")
        print("  *_epsg3857.tif (EPSG:3857 - Web Mercator)")
        print("Features:")
        print("  ✓ Uses your exact pixel/lat-lon measurements")
        print("  ✓ WGS84 intermediate + Web Mercator output")
        print("  ✓ Ready for QGIS with OSM basemap")
    
    return 0

if __name__ == "__main__":
    exit(main())