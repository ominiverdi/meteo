#!/usr/bin/env python3
"""
Extract and process water vapor channels from Meteosat SEVIRI data
Optimized: subset first, then process
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime
import subprocess
import tempfile

try:
    from osgeo import gdal, osr
except ImportError:
    print("Error: GDAL Python bindings not found")
    print("Install: sudo apt install python3-gdal")
    sys.exit(1)

def get_radar_extent_for_geostationary(nat_file):
    """Get radar extent transformed to geostationary projection for subsetting"""
    radar_tiff = "georef_data/radar_ba_20250712_161417_qgis_clean.tif"
    
    if not os.path.exists(radar_tiff):
        print(f"Error: Radar GeoTIFF not found: {radar_tiff}")
        return None
    
    print(f"Reading radar extent from: {radar_tiff}")
    
    # Open radar file
    radar_ds = gdal.Open(radar_tiff)
    if not radar_ds:
        print("Error: Could not open radar GeoTIFF")
        return None
    
    # Open .nat file to get its projection
    nat_ds = gdal.Open(nat_file)
    if not nat_ds:
        print(f"Error: Could not open {nat_file}")
        return None
    
    # Get radar bounds in EPSG:3857
    gt = radar_ds.GetGeoTransform()
    cols = radar_ds.RasterXSize
    rows = radar_ds.RasterYSize
    
    min_x = gt[0]
    max_y = gt[3]
    max_x = min_x + (gt[1] * cols)
    min_y = max_y + (gt[5] * rows)
    
    print(f"Radar bounds (EPSG:3857): {min_x:.0f}, {min_y:.0f}, {max_x:.0f}, {max_y:.0f}")
    
    # Get spatial reference systems
    radar_srs = osr.SpatialReference()
    radar_srs.ImportFromWkt(radar_ds.GetProjection())
    
    nat_srs = osr.SpatialReference()
    nat_srs.ImportFromWkt(nat_ds.GetProjection())
    
    # Transform radar bounds to geostationary projection
    transform = osr.CoordinateTransformation(radar_srs, nat_srs)
    
    # Transform corners
    corner1_x, corner1_y, _ = transform.TransformPoint(min_x, min_y)
    corner2_x, corner2_y, _ = transform.TransformPoint(max_x, max_y)
    
    # Ensure proper min/max order
    geo_min_x = min(corner1_x, corner2_x)
    geo_max_x = max(corner1_x, corner2_x)
    geo_min_y = min(corner1_y, corner2_y)
    geo_max_y = max(corner1_y, corner2_y)
    
    extent = {
        'min_x': geo_min_x,
        'max_x': geo_max_x,
        'min_y': geo_min_y,
        'max_y': geo_max_y
    }
    
    print(f"Radar extent (geostationary): {geo_min_x:.0f}, {geo_min_y:.0f}, {geo_max_x:.0f}, {geo_max_y:.0f}")
    
    radar_ds = None
    nat_ds = None
    return extent

def subset_meteosat_data(nat_file, extent, output_dir):
    """Subset Meteosat .nat file using geostationary coordinates"""
    
    print(f"Subsetting {os.path.basename(nat_file)} to Barcelona area...")
    
    # Add buffer around radar extent (in geostationary coordinates)
    buffer = 50000  # 50km in meters
    min_x = extent['min_x'] - buffer
    max_x = extent['max_x'] + buffer  
    min_y = extent['min_y'] - buffer
    max_y = extent['max_y'] + buffer
    
    print(f"Subset bounds (geostationary): {min_x:.0f}, {min_y:.0f}, {max_x:.0f}, {max_y:.0f}")
    
    # Output file
    subset_file = Path(output_dir) / f"{Path(nat_file).stem}_subset.tif"
    
    # Use gdal.Translate to subset by geostationary bounds
    translate_options = gdal.TranslateOptions(
        projWin=[min_x, max_y, max_x, min_y],  # [ulx, uly, lrx, lry] in source projection
        format='GTiff',
        creationOptions=['COMPRESS=LZW', 'TILED=YES']
    )
    
    ds = gdal.Translate(str(subset_file), nat_file, options=translate_options)
    if not ds:
        print(f"Error: Failed to subset {nat_file}")
        return None
    
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    bands = ds.RasterCount
    
    print(f"Subset created: {cols}x{rows} pixels, {bands} bands")
    
    ds = None
    return str(subset_file)

def extract_water_vapor_bands(subset_file, output_dir, timestamp_str):
    """Extract and calibrate water vapor bands from subset"""
    
    print("Extracting water vapor bands...")
    
    # Open subset file
    ds = gdal.Open(subset_file)
    if not ds:
        print(f"Error: Could not open {subset_file}")
        return []
    
    # Get calibration parameters from metadata
    metadata = ds.GetMetadata()
    
    # Water vapor bands: 5 (WV 6.2μm) and 6 (WV 7.3μm)
    wv_bands = {
        5: {'name': 'wv_6.2um', 'cal_key': 'ch05_cal'},
        6: {'name': 'wv_7.3um', 'cal_key': 'ch06_cal'}
    }
    
    output_files = []
    
    for band_num, info in wv_bands.items():
        print(f"Processing Band {band_num}: {info['name']}")
        
        # Get calibration parameters
        cal_params = metadata.get(info['cal_key'], '')
        if not cal_params:
            print(f"Warning: No calibration data for band {band_num}")
            continue
        
        # Parse calibration: "offset slope"
        try:
            offset, slope = map(float, cal_params.split())
            print(f"  Calibration: offset={offset:.6f}, slope={slope:.6f}")
        except:
            print(f"Error: Could not parse calibration for band {band_num}")
            continue
        
        # Extract band to temporary file
        temp_file = Path(output_dir) / f"temp_band_{band_num}.tif"
        
        translate_options = gdal.TranslateOptions(
            bandList=[band_num],
            format='GTiff',
            outputType=gdal.GDT_Float32,
            scaleParams=[[0, 1023, offset, offset + slope * 1023]],  # Convert raw to brightness temp
            creationOptions=['COMPRESS=LZW']
        )
        
        band_ds = gdal.Translate(str(temp_file), ds, options=translate_options)
        if not band_ds:
            print(f"Error: Failed to extract band {band_num}")
            continue
        
        band_ds = None
        
        # Reproject to Web Mercator (EPSG:3857) to match radar
        output_file = Path(output_dir) / f"{info['name']}_barcelona_{timestamp_str}.tif"
        
        warp_options = gdal.WarpOptions(
            dstSRS='EPSG:3857',
            format='GTiff',
            resampleAlg=gdal.GRA_Bilinear,
            creationOptions=['COMPRESS=LZW', 'TILED=YES']
        )
        
        final_ds = gdal.Warp(str(output_file), str(temp_file), options=warp_options)
        if final_ds:
            print(f"  Saved: {output_file}")
            output_files.append(str(output_file))
            final_ds = None
        
        # Clean up temp file
        if temp_file.exists():
            temp_file.unlink()
    
    ds = None
    return output_files

def create_metadata(nat_file, output_files, output_dir):
    """Create metadata file for processed water vapor data"""
    
    # Extract timestamp from filename
    filename = os.path.basename(nat_file)
    timestamp_part = filename.split('-')[5]  # 20250712144243.017000000Z
    timestamp_clean = timestamp_part.split('.')[0] + 'Z'  # 20250712144243Z
    
    try:
        dt = datetime.strptime(timestamp_clean, '%Y%m%d%H%M%SZ')
        iso_time = dt.isoformat() + 'Z'
    except:
        iso_time = timestamp_clean
    
    metadata = {
        'source_file': os.path.basename(nat_file),
        'processing_time': datetime.now().isoformat(),
        'observation_time': iso_time,
        'satellite': 'MSG3',
        'instrument': 'SEVIRI',
        'projection': 'EPSG:3857',
        'bands': {
            'wv_6.2um': {
                'description': 'Water vapor 6.2 micrometers (upper troposphere)',
                'units': 'Brightness temperature (K)',
                'file': os.path.basename(output_files[0]) if len(output_files) > 0 else None
            },
            'wv_7.3um': {
                'description': 'Water vapor 7.3 micrometers (mid-level troposphere)', 
                'units': 'Brightness temperature (K)',
                'file': os.path.basename(output_files[1]) if len(output_files) > 1 else None
            }
        }
    }
    
    metadata_file = Path(output_dir) / 'water_vapor_metadata.json'
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Metadata saved: {metadata_file}")
    return str(metadata_file)

def main():
    print("Water Vapor Extraction from Meteosat SEVIRI")
    print("=" * 50)
    
    # Input and output directories
    meteosat_dir = Path("meteosat_data")
    output_dir = meteosat_dir / "processed" 
    output_dir.mkdir(exist_ok=True)
    
    # Find .nat files
    nat_files = list(meteosat_dir.glob("*.nat"))
    if not nat_files:
        print("Error: No .nat files found in meteosat_data/")
        sys.exit(1)
    
    print(f"Found {len(nat_files)} .nat file(s)")
    
    # Process each .nat file
    for nat_file in nat_files:
        print(f"\nProcessing: {nat_file.name}")
        
        # Get radar extent in geostationary projection for this .nat file
        extent = get_radar_extent_for_geostationary(str(nat_file))
        if not extent:
            continue
        
        # Extract timestamp for filename
        filename = nat_file.name
        timestamp_part = filename.split('-')[5]  # 20250712144243.017000000Z
        timestamp_clean = timestamp_part.split('.')[0]  # 20250712144243
        
        # Step 1: Subset to Barcelona area
        subset_file = subset_meteosat_data(str(nat_file), extent, output_dir)
        if not subset_file:
            continue
        
        # Step 2: Extract and calibrate water vapor bands
        output_files = extract_water_vapor_bands(subset_file, output_dir, timestamp_clean)
        
        # Step 3: Create metadata
        if output_files:
            metadata_file = create_metadata(str(nat_file), output_files, output_dir)
            
            print(f"\nSuccess! Created {len(output_files)} water vapor files:")
            for file in output_files:
                print(f"  {os.path.basename(file)}")
        
        # Clean up subset file
        if os.path.exists(subset_file):
            os.unlink(subset_file)
    
    print(f"\nWater vapor data ready in: {output_dir}/")

if __name__ == "__main__":
    main()