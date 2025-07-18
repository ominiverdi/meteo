#!/usr/bin/env python3
"""
AEMET Radar Georeferencing Script - QGIS Method Replication
Uses the exact GCP coordinates and transformation from QGIS georeferencing
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

def interpolate_yellow_pixels(img):
    """
    Replace yellow pixels with average of 8 surrounding non-yellow neighbors
    Creates smoother, more natural-looking radar data
    """
    width, height = img.size
    print(f"    Interpolating yellow pixels using 8-neighbor averaging...")
    
    # Create a copy to avoid modifying while iterating
    result = img.copy()
    yellow_count = 0
    interpolated_count = 0
    
    # DEBUG: Sample some pixels to see actual RGB values
    sample_pixels = []
    for y in range(0, height, 50):  # Sample every 50 pixels
        for x in range(0, width, 50):
            pixel = img.getpixel((x, y))
            if len(pixel) >= 3:
                sample_pixels.append(pixel)
    
    # Find yellow-ish pixels for debugging
    yellowish_pixels = [p for p in sample_pixels if len(p) >= 3 and p[1] > 80 and p[0] > 80 and p[2] < 50]
    if yellowish_pixels:
        print(f"    DEBUG: Found yellowish pixels: {yellowish_pixels[:5]}")
    
    for y in range(height):
        for x in range(width):
            pixel = img.getpixel((x, y))
            
            # More flexible yellow detection - check for yellowish colors
            is_yellow = False
            if len(pixel) >= 3:
                r, g, b = pixel[0], pixel[1], pixel[2]
                # Check for various yellow shades (more flexible)
                if (r > 80 and g > 80 and b < 50 and abs(r-g) < 30):
                    is_yellow = True
                    if yellow_count < 5:  # Show first few for debugging
                        print(f"    DEBUG: Yellow pixel at ({x},{y}): RGB{pixel}")
            
            if is_yellow:
                yellow_count += 1
                
                # Get 8 surrounding pixels
                neighbors = []
                for dy in [-1, 0, 1]:
                    for dx in [-1, 0, 1]:
                        if dx == 0 and dy == 0:  # Skip center pixel
                            continue
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < width and 0 <= ny < height:
                            neighbor = img.getpixel((nx, ny))
                            # Only use non-yellow neighbors
                            if len(neighbor) >= 3:
                                nr, ng, nb = neighbor[0], neighbor[1], neighbor[2]
                                # Skip if neighbor is also yellowish
                                if not (nr > 80 and ng > 80 and nb < 50 and abs(nr-ng) < 30):
                                    neighbors.append(neighbor)
                
                if neighbors:
                    # Calculate average RGB(A)
                    avg_r = sum(p[0] for p in neighbors) // len(neighbors)
                    avg_g = sum(p[1] for p in neighbors) // len(neighbors)
                    avg_b = sum(p[2] for p in neighbors) // len(neighbors)
                    avg_a = sum(p[3] for p in neighbors) // len(neighbors) if len(neighbors[0]) > 3 else 255
                    
                    result.putpixel((x, y), (avg_r, avg_g, avg_b, avg_a))
                    interpolated_count += 1
                else:
                    # No non-yellow neighbors, make transparent
                    result.putpixel((x, y), (0, 0, 0, 0))
    
    print(f"    Found {yellow_count} yellow pixels, interpolated {interpolated_count}")
    return result

def clean_radar_image(input_path, output_dir="georef_data", interpolate_yellow=True):
    """
    Clean radar image: remove footer, header text, logo, and make background transparent
    """
    Path(output_dir).mkdir(exist_ok=True)
    
    filename = os.path.basename(input_path)
    name_without_ext = os.path.splitext(filename)[0]
    
    footer_boundary = analyze_image_structure(input_path)
    
    with Image.open(input_path) as img:
        # Convert to RGBA for transparency support
        img = img.convert('RGBA')
        width, height = img.size
        
        # DEBUG: Check if we have the expected yellow pixels after conversion
        yellow_found = False
        for y in range(100, min(200, height)):  # Sample middle area
            for x in range(100, min(200, width)):
                pixel = img.getpixel((x, y))
                if len(pixel) >= 3 and pixel[0] == 100 and pixel[1] == 100 and pixel[2] == 0:
                    yellow_found = True
                    print(f"    DEBUG: Found RGB(100,100,0) at ({x},{y})")
                    break
            if yellow_found:
                break
        
        if not yellow_found:
            # Sample a few random pixels to see what we actually have
            print("    DEBUG: No RGB(100,100,0) found. Sampling actual colors:")
            for y in range(100, min(150, height), 10):
                for x in range(100, min(150, width), 10):
                    pixel = img.getpixel((x, y))
                    if len(pixel) >= 3 and pixel[0] > 50 and pixel[1] > 50 and pixel[2] < 100:
                        print(f"    DEBUG: Yellowish pixel at ({x},{y}): {pixel}")
        
        print("Cleaning radar image:")
        print(f"  - Removing header text (top 14 pixels)")
        print(f"  - Removing AEMET logo (392,0 to {width},46)")
        print(f"  - Making black/grey background transparent")
        if interpolate_yellow:
            print(f"  - Interpolating yellow boundary lines with surrounding pixels")
        
        # Step 1: Remove header text (top 14 pixels) and logo area
        # Create a copy to modify
        cleaned_img = img.copy()
        
        # Clear header text area (158x14 top-left)
        for x in range(min(158, width)):
            for y in range(min(14, height)):
                cleaned_img.putpixel((x, y), (0, 0, 0, 0))  # Transparent
        
        # Clear AEMET logo area (392,0 to 479,46) - FIXED bounds checking
        for x in range(392, min(480, width)):  # Don't exceed image width
            for y in range(min(46, height)):
                cleaned_img.putpixel((x, y), (0, 0, 0, 0))  # Transparent
        
        # Step 2: Remove footer (bottom 50 pixels)
        radar_data = cleaned_img.crop((0, 0, width, footer_boundary))
        
        # Step 3: Handle yellow boundary lines
        if interpolate_yellow:
            # Use interpolation method - much better for weather data!
            radar_data = interpolate_yellow_pixels(radar_data)
        
        # Step 4: Make background colors transparent
        # Get image data as array for faster processing
        data = list(radar_data.getdata())
        new_data = []
        
        for pixel in data:
            r, g, b, a = pixel
            
            # Make black transparent
            if r == 0 and g == 0 and b == 0:
                new_data.append((0, 0, 0, 0))
            # Make grey transparent (RGB 127,127,127 - closest to 49.8% of 255)
            elif r == 127 and g == 127 and b == 127:
                new_data.append((0, 0, 0, 0))
            # Keep all other colors (precipitation data and interpolated pixels)
            else:
                new_data.append(pixel)
        
        # Apply cleaned data
        radar_data.putdata(new_data)
        
        # Save cleaned radar data
        radar_output = os.path.join(output_dir, f"{name_without_ext}_cleaned.png")
        radar_data.save(radar_output)
        print(f"Cleaned radar data saved: {radar_output}")
        
        # Also save footer for reference
        footer_data = img.crop((0, footer_boundary, width, height))
        footer_output = os.path.join(output_dir, f"{name_without_ext}_footer.gif")
        footer_data.save(footer_output)
        print(f"Footer saved: {footer_output}")
        
        return radar_output, footer_output, (width, footer_boundary)

def separate_radar_footer(input_path, output_dir="georef_data"):
    """
    Legacy function - now calls clean_radar_image with interpolation
    """
    return clean_radar_image(input_path, output_dir, interpolate_yellow=True)

def create_geotiff_qgis_method(radar_image_path):
    """
    Replicate the exact QGIS georeferencing method using the measured GCPs
    Now handles cleaned PNG files with transparency
    """
    print(f"Using QGIS-measured Ground Control Points method")
    
    # EXACT GCPs from your successful QGIS georeferencing
    # Format: pixel_x, pixel_y, web_mercator_x, web_mercator_y
    qgis_gcps = [
        (131.774, 336.906, 65931.872, 4949862.395),
        (137.66, 99.623, 73741.13, 5265877.036),
        (200.377, 223.472, 18555.707, 4973290.169),
        (234.113, 142.189, 204416.047, 5207567.909),
        (262.31, 250.326, 238386.32, 5056979.384),
        (111.776, 240.625, 36386.846, 5073769.289),
        (116.125, 256.682, 42113.635, 5054506.453),
        (100.403, 280.433, 22850.799, 5023790.038),
        (126.161, 340.646, 56170.3, 4942053.137),
        (66.951, 427.955, -21401.663, 4825434.885),
        (407.156, 385.472, 425808.512, 4874372.901),
        (282.046, 441.002, 260772.859, 4808254.517),
        (377.718, 422.938, 384159.136, 4825955.502),
        (345.27, 474.788, 340947.908, 4759837.117),
        (220.829, 264.711, 183200.896, 5042532.257),
        (312.822, 210.519, 307628.407, 5108650.641),
        (355.891, 397.138, 355004.572, 4861357.471),
        (447.716, 411.69, 476828.997, 4839491.549),
        (342.343, 124.547, 349798.4, 5227871.98),
        (354.762, 135.587, 365416.916, 5212253.464),
        (351.5, 145.12, 362293.213, 5197676.183),
        (342.218, 143.364, 349798.4, 5201841.12),
        (348.364, 167.449, 358128.276, 5168521.619),
        (341.339, 190.908, 347715.932, 5138325.822),
        (275.607, 187.019, 258169.773, 5143531.994),
        (14.933, 409.933, -103138.563, 4839491.549),
        (51.312, 324.631, -42746.968, 4959233.505),
        (68.122, 311.083, -20881.046, 4980058.193),
        (35.506, 248.361, -65654.125, 5065439.414),
        (66.867, 221.014, -24004.749, 5103965.087),
        (20.202, 268.432, -84396.344, 5037065.776),
        (9.163, 270.439, -99233.934, 5034202.382),
        (2.263, 270.314, -108865.353, 5034202.382),
        (11.17, 175.478, -98713.317, 5161753.596),
        (28.23, 180.997, -73723.692, 5154985.572),
        (9.665, 145.371, -108344.735, 5193250.936),
        (23.965, 75.248, -82053.567, 5300237.771),
        (38.391, 90.552, -61749.496, 5278892.466),
        (112.529, 96.573, 39770.858, 5270562.591),
    ]
    
    print(f"Using {len(qgis_gcps)} QGIS-measured Ground Control Points")
    
    # Step 1: Create temporary file with GCPs (replicating QGIS gdal_translate)
    temp_dir = Path("/tmp")
    temp_file = temp_dir / f"temp_{os.path.basename(radar_image_path).replace('.png', '.tif')}"
    
    # Build GCP parameters for gdal_translate
    gcp_params = []
    for i, (px, py, mx, my) in enumerate(qgis_gcps):
        gcp_params.extend(['-gcp', str(px), str(py), str(mx), str(my)])
        if i < 5:  # Show first 5 for brevity
            print(f"  GCP {i+1}: pixel({px},{py}) -> mercator({mx:.0f},{my:.0f})")
    
    if len(qgis_gcps) > 5:
        print(f"  ... and {len(qgis_gcps)-5} more GCPs")
    
    # EXACT replication of QGIS gdal_translate command
    # Handle PNG with transparency
    cmd1 = [
        'gdal_translate',
        '-of', 'GTiff',
        '-co', 'COMPRESS=LZW',
        '-co', 'TILED=YES',
        *gcp_params,
        radar_image_path,
        str(temp_file)
    ]
    
    try:
        subprocess.run(cmd1, check=True, capture_output=True, text=True)
        print(f"Created GCP file: {temp_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error in gdal_translate: {e}")
        return None
    
    # Step 2: Apply transformation (replicating QGIS gdalwarp)
    output_file = radar_image_path.replace('_cleaned.png', '_qgis_clean.tif')
    
    # EXACT replication of QGIS gdalwarp command with transparency preservation
    cmd2 = [
        'gdalwarp',
        '-r', 'near',           # Nearest neighbor (preserves radar colors)
        '-order', '3',          # 3rd order polynomial (as used by QGIS)
        '-co', 'COMPRESS=LZW',  # Add compression
        '-co', 'TILED=YES',     # Tiled for better performance
        '-dstalpha',            # Preserve alpha channel (transparency)
        '-overwrite',           # Allow overwriting existing files
        '-t_srs', 'EPSG:3857',  # Target: Web Mercator
        str(temp_file),
        output_file
    ]
    
    try:
        subprocess.run(cmd2, check=True, capture_output=True, text=True)
        print(f"Created georeferenced clean file: {output_file}")
        
        # Clean up temp file
        temp_file.unlink()
        
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"Error in gdalwarp: {e}")
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
    Process radar image using QGIS-replicated method with image cleaning
    """
    print(f"\n{'='*60}")
    print(f"Processing: {os.path.basename(image_path)}")
    print(f"Method: QGIS-Replicated Georeferencing + Image Cleaning")
    print(f"{'='*60}")
    
    if not check_gdal_installation():
        return None
    
    # Clean radar image: remove footer, header, logo, and make background transparent
    radar_output, footer_output, radar_dims = clean_radar_image(image_path)
    
    # Apply QGIS-method georeferencing to cleaned image
    print(f"\nApplying QGIS-method georeferencing to cleaned image...")
    georef_tiff = create_geotiff_qgis_method(radar_output)
    
    if georef_tiff:
        print(f"\n✅ Success!")
        print(f"📁 Output: {os.path.basename(georef_tiff)}")
        print(f"🎯 Method: QGIS replication + Image cleaning")
        print(f"📍 Coordinate System: EPSG:3857 (Web Mercator)")
        print(f"🔧 Transformation: 3rd order polynomial with 39 GCPs")
        print(f"🧹 Cleaned: Header text, logo, background, and boundaries interpolated")
        print(f"🌈 Transparency: Black/grey background → transparent")
        print(f"🎨 Interpolation: Yellow boundary lines → averaged surrounding pixels")
        print(f"\n🗺️  Ready for web mapping with transparent background!")
    
    return georef_tiff

def main():
    parser = argparse.ArgumentParser(description='AEMET Radar Georeferencing - QGIS Method Replication')
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
        images = sorted(glob.glob(f'../data/radar_ba_{today}_*.gif'))
        if images:
            process_image(images[-1])
        else:
            print("No radar images found for today")
            return 1
    
    elif args.batch:
        images = sorted(glob.glob('../data/radar_ba_*.gif'))
        if not images:
            print("No radar images found")
            return 1
        
        for image_path in images:
            try:
                process_image(image_path)
            except Exception as e:
                print(f"Error: {image_path}: {e}")
    
    else:
        print("AEMET Radar Georeferencing - QGIS Method + Image Cleaning")
        print("Uses the exact same GCPs and transformation as your successful QGIS georeferencing")
        print("Plus automatic removal of headers, logos, and background for clean web overlays")
        print("\nUsage:")
        print("  python 4_georeference.py --latest")
        print("  python 4_georeference.py --input radar.gif")
        print("\nOutput:")
        print("  *_qgis_clean.tif (EPSG:3857 - Web Mercator with transparency)")
        print("\nMethod:")
        print("  ✓ 39 measured Ground Control Points from QGIS")
        print("  ✓ 3rd order polynomial transformation")
        print("  ✓ Nearest neighbor resampling (preserves radar colors)")
        print("  ✓ Header text removal (top 14 pixels)")
        print("  ✓ AEMET logo removal (392,0 to right edge, top 46 pixels)")
        print("  ✓ Background transparency (black, grey)")
        print("  ✓ Yellow boundary interpolation (8-neighbor averaging)")
        print("  ✓ Perfect for web mapping overlays with natural weather patterns")
    
    return 0

if __name__ == "__main__":
    exit(main())