#!/usr/bin/env python3
"""
AEMET Radar Footer Color Bar Parser
Extracts color-to-dBZ mapping from radar footer images
"""

import os
from PIL import Image
import json
from pathlib import Path
import subprocess
import tempfile

def ocr_bottom_line(footer_path):
    """
    Use OCR to extract text from the bottom line
    """
    print(f"\nUsing OCR to read bottom line text...")
    
    try:
        # Check if tesseract is available
        subprocess.run(['tesseract', '--version'], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Tesseract OCR not found! Install: sudo apt install tesseract-ocr")
        return None
    
    try:
        with Image.open(footer_path) as img:
            img = img.convert('RGB')
            width, height = img.size
            
            # Extract just the bottom text area
            bottom_crop_height = 15  # Bottom 15 pixels should contain the text
            bottom_area = img.crop((0, height - bottom_crop_height, width, height))
            
            # Enhance for OCR: make text white on black background
            enhanced = Image.new('RGB', bottom_area.size, 'black')
            
            for y in range(bottom_area.height):
                for x in range(bottom_area.width):
                    r, g, b = bottom_area.getpixel((x, y))
                    
                    # If pixel is not black, make it white (text)
                    if not (r == 0 and g == 0 and b == 0):
                        enhanced.putpixel((x, y), (255, 255, 255))
            
            # Scale up for better OCR
            scale_factor = 4
            enhanced = enhanced.resize((width * scale_factor, bottom_crop_height * scale_factor), Image.NEAREST)
            
            # Save to temporary file for tesseract
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                enhanced.save(temp_file.name)
                
                try:
                    # Run tesseract OCR
                    result = subprocess.run([
                        'tesseract', temp_file.name, 'stdout',
                        '-c', 'tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ _'
                    ], capture_output=True, text=True, check=True)
                    
                    ocr_text = result.stdout.strip()
                    print(f"OCR Result: '{ocr_text}'")
                    
                    return ocr_text
                    
                except subprocess.CalledProcessError as e:
                    print(f"OCR failed: {e}")
                    return None
                finally:
                    # Clean up temp file
                    if os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)
                        
    except Exception as e:
        print(f"OCR processing failed: {e}")
        return None

def ocr_dbz_values(footer_path):
    """
    OCR the dBZ values from the specific area above color bar
    """
    print(f"\nOCR'ing dBZ values...")
    
    try:
        subprocess.run(['tesseract', '--version'], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Tesseract OCR not found!")
        return None
    
    try:
        with Image.open(footer_path) as img:
            img = img.convert('RGB')
            
            # Extract the dBZ values area: x=142 to 480, y=16 to 26
            dbz_area = img.crop((142, 16, 480, 26))
            
            # Enhance for OCR: make text white on black background
            enhanced = Image.new('RGB', dbz_area.size, 'black')
            
            for y in range(dbz_area.height):
                for x in range(dbz_area.width):
                    r, g, b = dbz_area.getpixel((x, y))
                    
                    # If pixel is not black, make it white (text)
                    if not (r == 0 and g == 0 and b == 0):
                        enhanced.putpixel((x, y), (255, 255, 255))
            
            # Scale up for better OCR
            scale_factor = 4
            enhanced = enhanced.resize((dbz_area.width * scale_factor, dbz_area.height * scale_factor), Image.NEAREST)
            
            # Save to temporary file for tesseract
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                enhanced.save(temp_file.name)
                
                try:
                    # Run tesseract OCR with numbers only
                    result = subprocess.run([
                        'tesseract', temp_file.name, 'stdout',
                        '-c', 'tessedit_char_whitelist=0123456789 '
                    ], capture_output=True, text=True, check=True)
                    
                    ocr_text = result.stdout.strip()
                    print(f"dBZ OCR Result: '{ocr_text}'")
                    
                    # Parse the numbers
                    if ocr_text:
                        numbers = [int(x) for x in ocr_text.split() if x.isdigit()]
                        print(f"Extracted dBZ values: {numbers}")
                        return numbers
                    
                    return None
                    
                except subprocess.CalledProcessError as e:
                    print(f"dBZ OCR failed: {e}")
                    return None
                finally:
                    if os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)
                        
    except Exception as e:
        print(f"dBZ OCR processing failed: {e}")
        return None

def extract_color_sequence(footer_path):
    """
    Extract colors by scanning horizontally across the color bar
    """
    print(f"Analyzing footer: {os.path.basename(footer_path)}")
    
    with Image.open(footer_path) as img:
        # Convert to RGB to ensure we get RGB tuples
        img = img.convert('RGB')
        width, height = img.size
        print(f"Footer dimensions: {width}x{height}")
        
        # Use your exact starting coordinates
        start_x = 144
        start_y = 26
        end_x = 478  # Scan to almost the end of the footer
        
        print(f"Scanning horizontally from ({start_x},{start_y}) to ({end_x},{start_y})")
        
        # Scan horizontally from starting point
        all_colors = []
        for x in range(start_x, end_x):
            rgb = img.getpixel((x, start_y))
            r, g, b = rgb
            all_colors.append((x, r, g, b))
            
        print(f"Sampled {len(all_colors)} pixels")
        
        # Extract unique colors in sequence (keeping order)
        unique_colors = []
        seen_colors = set()
        
        for x, r, g, b in all_colors:
            color_tuple = (r, g, b)
            if color_tuple not in seen_colors:
                unique_colors.append((x, r, g, b))
                seen_colors.add(color_tuple)
        
        print(f"Found {len(unique_colors)} unique colors:")
        for i, (x, r, g, b) in enumerate(unique_colors):
            print(f"  {i+1}: RGB({r:3d},{g:3d},{b:3d}) at x={x} = #{r:02x}{g:02x}{b:02x}")
        
        return unique_colors

def map_colors_to_dbz(unique_colors, dbz_values=None):
    """
    Map the unique colors to dBZ values - slim JSON format
    """
    # Use OCR'd values if available, otherwise fall back to known values
    if not dbz_values:
        dbz_values = [12, 18, 24, 30, 36, 42, 48, 54, 60, 66, 72]
    
    print(f"\nMapping {len(unique_colors)} colors to {len(dbz_values)} dBZ values:")
    
    color_mapping = []
    
    # Map each unique color to corresponding dBZ value
    for i, (x, r, g, b) in enumerate(unique_colors):
        if i < len(dbz_values):
            dbz_value = dbz_values[i]
            
            color_entry = {
                "dbz": dbz_value,
                "rgb": [r, g, b],
                "hex": f"#{r:02x}{g:02x}{b:02x}"
            }
            
            color_mapping.append(color_entry)
            print(f"  dBZ {dbz_value:2d}: RGB({r:3d},{g:3d},{b:3d}) = {color_entry['hex']}")
    
    return color_mapping

def extract_bottom_line_metadata(footer_path):
    """
    Extract metadata from the bottom line using OCR
    """
    print(f"\nExtracting bottom line metadata with OCR...")
    
    # Use OCR to read the actual text
    ocr_text = ocr_bottom_line(footer_path)
    
    if ocr_text:
        print(f"Raw OCR text: '{ocr_text}'")
        
        # Parse the OCR text for date/time and other info
        metadata = {
            "ocr_text": ocr_text,
            "parsed_data": parse_footer_text(ocr_text)
        }
    else:
        print("OCR failed - using fallback analysis")
        metadata = {
            "ocr_text": None,
            "parsed_data": None
        }
    
    return metadata

def parse_footer_text(ocr_text):
    """
    Parse the OCR'd footer text to extract structured data
    Expected format: "10001 RODAR_PPIR 12 JUL 25193932 141000 OF 129M"
    """
    if not ocr_text:
        return None
    
    parts = ocr_text.split()
    parsed = {}
    
    try:
        if len(parts) >= 6:
            parsed['radar_id'] = parts[0]  # 10001
            parsed['radar_type'] = parts[1]  # RODAR_PPIR
            parsed['day'] = int(parts[2])  # 12
            parsed['month'] = parts[3]  # JUL
            
            # Parse the year+code field: 25193932
            year_field = parts[4]  # 25193932
            if len(year_field) >= 2:
                parsed['year'] = 2000 + int(year_field[:2])  # 25 -> 2025
                parsed['year_code'] = year_field[2:]  # 193932 (Julian day + other data?)
            
            # Parse time: 141000 = 14:10:00 UTC
            time_field = parts[5]  # 141000
            if len(time_field) == 6:
                hour = int(time_field[:2])
                minute = int(time_field[2:4])
                second = int(time_field[4:6])
                parsed['time_utc'] = f"{hour:02d}:{minute:02d}:{second:02d}"
                
                # Convert UTC to CET (UTC+1 in winter, UTC+2 in summer)
                # For July, use UTC+2 (CEST)
                cet_hour = (hour + 2) % 24
                parsed['time_cet'] = f"{cet_hour:02d}:{minute:02d}:{second:02d}"
            
            # Parse additional fields
            if len(parts) > 6:
                parsed['additional'] = ' '.join(parts[6:])  # "OF 129M"
        
        # Format as standard date
        month_map = {
            'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
        }
        
        if 'month' in parsed and 'day' in parsed and 'year' in parsed:
            month_num = month_map.get(parsed['month'])
            if month_num:
                parsed['date'] = f"{parsed['year']}-{month_num:02d}-{parsed['day']:02d}"
        
        # Combine date and time into both UTC and CET datetime
        if 'date' in parsed and 'time_utc' in parsed:
            parsed['datetime_utc'] = f"{parsed['date']}T{parsed['time_utc']}Z"
        
        if 'date' in parsed and 'time_cet' in parsed:
            parsed['datetime_cet'] = f"{parsed['date']}T{parsed['time_cet']}+02:00"
        
        print(f"Parsed data: {parsed}")
        
    except Exception as e:
        print(f"Failed to parse OCR text: {e}")
        parsed = {"error": str(e), "raw_text": ocr_text}
    
    return parsed

def create_color_scale_json(color_mapping, footer_path, metadata, dbz_values):
    """
    Create clean JSON output with color scale and metadata
    """
    # Extract essential metadata from parsed data
    parsed = metadata.get('parsed_data', {})
    
    output_data = {
        "source": os.path.basename(footer_path),
        "type": "reflectivity_dbz",
        "units": "dBZ",
        "scale": color_mapping,
        "radar_id": parsed.get('radar_id'),
        "radar_type": parsed.get('radar_type'),
        "date": parsed.get('date'),
        "time_utc": parsed.get('time_utc'),
        "time_cet": parsed.get('time_cet'),
        "datetime_utc": parsed.get('datetime_utc'),
        "datetime_cet": parsed.get('datetime_cet')
    }
    
    # Remove None values
    output_data = {k: v for k, v in output_data.items() if v is not None}
    
    # Save JSON file
    output_path = footer_path.replace('_footer.gif', '_color_scale.json')
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\nColor scale JSON saved: {os.path.basename(output_path)}")
    return output_path

def main():
    # Target the specific footer file (relative to scripts directory)
    footer_path = "georef_data/radar_ba_20250712_161417_footer.gif"
    
    if not os.path.exists(footer_path):
        print(f"Footer file not found: {footer_path}")
        print("Expected location: georef_data/radar_ba_20250712_161417_footer.gif")
        print(f"Current directory: {os.getcwd()}")
        print("Available files in georef_data:")
        georef_dir = Path("georef_data")
        if georef_dir.exists():
            for file in georef_dir.glob("*"):
                print(f"  {file.name}")
        return 1
    
    print("AEMET Radar Footer Color Bar Parser")
    print("=" * 50)
    
    # Extract unique colors in sequence
    unique_colors = extract_color_sequence(footer_path)
    
    # Use known dBZ values - OCR is unreliable for the number area
    dbz_values = [12, 18, 24, 30, 36, 42, 48, 54, 60, 66, 72]
    print(f"Using known dBZ values: {dbz_values}")
    
    # Map to dBZ values
    color_mapping = map_colors_to_dbz(unique_colors, dbz_values)
    
    # Extract bottom line metadata
    metadata = extract_bottom_line_metadata(footer_path)
    
    # Create JSON output
    json_path = create_color_scale_json(color_mapping, footer_path, metadata, dbz_values)
    
    print(f"\n✅ Color extraction complete!")
    print(f"📊 Found {len(unique_colors)} unique colors")
    print(f"📋 Mapped {len(color_mapping)} to dBZ values")
    print(f"📁 Output: {os.path.basename(json_path)}")
    
    return 0

if __name__ == "__main__":
    exit(main())