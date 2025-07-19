#!/usr/bin/env python3
import requests
import os
import time
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

import logging
logging.basicConfig(level=logging.WARNING)

load_dotenv()

api_key = os.getenv('opendata_apikey')
if not api_key:
    print("Error: opendata_apikey not found in .env file")
    exit(1)

Path("data").mkdir(exist_ok=True)
Path("animations").mkdir(exist_ok=True)
Path("enhanced").mkdir(exist_ok=True)

def ocr_footer_timestamp(image_path):
    """Extract timestamp from radar footer using OCR"""
    try:
        # Check if tesseract is available
        subprocess.run(['tesseract', '--version'], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Warning: Tesseract OCR not found. Using filename timestamp.")
        return None
    
    try:
        with Image.open(image_path) as img:
            img = img.convert('RGB')
            width, height = img.size
            
            # Extract footer (bottom 50 pixels)
            footer = img.crop((0, height - 50, width, height))
            
            # Extract bottom text area (last 15 pixels of footer)
            bottom_crop_height = 15
            bottom_area = footer.crop((0, footer.height - bottom_crop_height, footer.width, footer.height))
            
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
            enhanced = enhanced.resize((enhanced.width * scale_factor, enhanced.height * scale_factor), Image.NEAREST)
            
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
                    
                    if ocr_text:
                        # Parse the OCR text
                        parsed_timestamp = parse_footer_text(ocr_text)
                        return parsed_timestamp
                    
                    return None
                    
                except subprocess.CalledProcessError:
                    return None
                finally:
                    # Clean up temp file
                    if os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)
                        
    except Exception as e:
        print(f"OCR processing failed: {e}")
        return None

def parse_footer_text(ocr_text):
    """Parse OCR'd footer text to extract timestamp"""
    if not ocr_text:
        return None
    
    parts = ocr_text.split()
    
    try:
        if len(parts) >= 6:
            # Extract components: "10001 RODAR_PPIR 12 JUL 25193932 141000 OF 129M"
            day = int(parts[2])  # 12
            month_str = parts[3]  # JUL
            
            # Parse year+code field: 25193932
            year_field = parts[4]  # 25193932
            if len(year_field) >= 2:
                year = 2000 + int(year_field[:2])  # 25 -> 2025
            else:
                return None
            
            # Parse time: 141000 = 14:10:00 UTC
            time_field = parts[5]  # 141000
            if len(time_field) == 6:
                hour = int(time_field[:2])
                minute = int(time_field[2:4])
                second = int(time_field[4:6])
            else:
                return None
            
            # Month mapping
            month_map = {
                'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
            }
            
            month = month_map.get(month_str)
            if not month:
                return None
            
            # Create UTC datetime
            utc_dt = datetime(year, month, day, hour, minute, second)
            
            # Convert to CET (UTC+1 in winter, UTC+2 in summer)
            # Simple approximation: use UTC+2 for summer months (Apr-Oct)
            if month >= 4 and month <= 10:
                cet_dt = utc_dt + timedelta(hours=2)  # CEST (summer time)
            else:
                cet_dt = utc_dt + timedelta(hours=1)  # CET (winter time)
            
            return {
                'utc_time': utc_dt,
                'cet_time': cet_dt,
                'formatted_cet': cet_dt.strftime('%d %b %H:%M CET'),
                'success': True
            }
        
    except Exception as e:
        print(f"Failed to parse OCR text: {e}")
    
    return None

def get_radar_timestamp(filepath):
    """Extract timestamp from radar image - try OCR first, fallback to filename"""
    # Try OCR first
    ocr_result = ocr_footer_timestamp(filepath)
    if ocr_result and ocr_result['success']:
        print(f"OCR timestamp: {ocr_result['formatted_cet']}")
        return ocr_result['formatted_cet']
    
    # Fallback to filename method
    print("OCR failed, using filename timestamp")
    basename = os.path.basename(filepath)
    timestamp_str = basename.split('_')[2] + basename.split('_')[3].split('.')[0]
    
    try:
        dt = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
        radar_time = dt - timedelta(minutes=10)  # Processing delay adjustment
        return radar_time.strftime('%d %b %H:%M CET')
    except:
        return "Unknown Time"

def enhance_radar_image(input_path, output_path):
    """Add timestamp header to radar image using OCR-extracted time"""
    timestamp = get_radar_timestamp(input_path)
    
    with Image.open(input_path) as img:
        width, height = img.size
        new_height = height + 60
        enhanced = Image.new('RGB', (width, new_height), 'black')
        enhanced.paste(img, (0, 60))
        
        draw = ImageDraw.Draw(enhanced)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        text_bbox = draw.textbbox((0, 0), timestamp, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        x = (width - text_width) // 2
        
        draw.text((x, 20), timestamp, fill='white', font=font)
        enhanced.save(output_path)
        return True

def create_animation():
    """Create animation from enhanced images"""
    today = datetime.now().strftime('%Y%m%d')
    enhanced_dir = Path("enhanced")
    
    images = sorted(enhanced_dir.glob(f"radar_ba_{today}_*.gif"))
    
    print(f"Found {len(images)} enhanced images for animation")
    
    if len(images) < 2:
        print("Need at least 2 images for animation")
        return False
    
    print(f"Creating animation with {len(images)} frames...")
    
    frames = []
    for img_path in images:
        with Image.open(img_path) as img:
            frames.append(img.copy())
    
    # Create animated GIF
    gif_file = f"animations/radar_animation_{today}.gif"
    frames[0].save(
        gif_file,
        save_all=True,
        append_images=frames[1:],
        duration=800,
        loop=0
    )
    
    # Create MP4 for WhatsApp
    mp4_file = f"animations/radar_animation_{today}.mp4"
    try:
        os.system(f'ffmpeg -y -i {gif_file} -vf "fps=1.25,scale=512:512" -c:v libx264 -pix_fmt yuv420p {mp4_file} 2>/dev/null')
        print(f"Created: {gif_file} and {mp4_file}")
    except:
        print(f"Created: {gif_file} (install ffmpeg for MP4)")
    
    return True

def download_radar():
    """Download Barcelona regional radar with OCR timestamp processing"""
    url = "https://opendata.aemet.es/opendata/api/red/radar/regional/ba"
    headers = {'cache-control': 'no-cache'}
    params = {'api_key': api_key}
    
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] Downloading radar...")
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 429:
            print("Rate limited. Skipping this cycle.")
            return False
        
        if response.status_code != 200:
            print(f"API error: {response.status_code}")
            return False
        
        data = response.json()
        radar_url = data['datos']
        
        img_response = requests.get(radar_url, timeout=30)
        if img_response.status_code == 200:
            filename = f"data/radar_ba_{datetime.now().strftime('%Y%m%d_%H%M%S')}.gif"
            with open(filename, 'wb') as f:
                f.write(img_response.content)
            print(f"Saved: {filename}")
            
            # Enhance image with OCR-extracted timestamp
            enhanced_filename = filename.replace('data/', 'enhanced/')
            enhance_radar_image(filename, enhanced_filename)
            print(f"Enhanced with OCR timestamp: {enhanced_filename}")
            
            return True
        
    except Exception as e:
        print(f"Error: {e}")
    
    return False

def calculate_wait_time():
    """Calculate time to wait based on last download"""
    data_dir = Path("data")
    today = datetime.now().strftime('%Y%m%d')
    images = sorted(data_dir.glob(f"radar_ba_{today}_*.gif"))
    
    if not images:
        return 0  # Download immediately
    
    # Get last image timestamp
    last_file = images[-1]
    basename = last_file.name
    timestamp_str = basename.split('_')[2] + basename.split('_')[3].split('.')[0]
    last_time = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
    
    # Calculate next download time (15 min interval)
    next_time = last_time + timedelta(minutes=15)
    wait_seconds = (next_time - datetime.now()).total_seconds()
    
    return max(0, wait_seconds)

def enhance_existing_images():
    """Enhance any existing raw images with OCR timestamps"""
    data_dir = Path("data")
    enhanced_dir = Path("enhanced")
    today = datetime.now().strftime('%Y%m%d')
    
    raw_images = sorted(data_dir.glob(f"radar_ba_{today}_*.gif"))
    enhanced_images = {f.name for f in enhanced_dir.glob(f"radar_ba_{today}_*.gif")}
    
    count = 0
    for raw_image in raw_images:
        if raw_image.name not in enhanced_images:
            enhanced_path = enhanced_dir / raw_image.name
            enhance_radar_image(str(raw_image), str(enhanced_path))
            print(f"Enhanced with OCR: {enhanced_path}")
            count += 1
    
    return count

def cleanup_old_files():
    """Clean up files older than 365 days"""
    cutoff_date = datetime.now() - timedelta(days=365)
    cutoff_str = cutoff_date.strftime('%Y%m%d')
    
    # Clean data files
    for file in Path("data").glob('radar_ba_*.gif'):
        try:
            date_part = file.name.split('_')[2]
            if date_part < cutoff_str:
                file.unlink()
                print(f"Cleaned old file: {file.name}")
        except:
            pass
    
    # Clean enhanced files
    for file in Path("enhanced").glob('radar_ba_*.gif'):
        try:
            date_part = file.name.split('_')[2]
            if date_part < cutoff_str:
                file.unlink()
                print(f"Cleaned old enhanced file: {file.name}")
        except:
            pass

def main():
    """Main service loop with OCR timestamp extraction"""
    interval = 15  # minutes
    print(f"Starting radar listener with OCR timestamps (every {interval} minutes)")
    print("OCR will extract accurate observation times from radar footer")
    
    print("Checking for existing images...")
    enhanced_count = enhance_existing_images()
    if enhanced_count > 0:
        print(f"Enhanced {enhanced_count} existing images with OCR timestamps")
    
    create_animation()
    
    try:
        while True:
            wait_time = calculate_wait_time()
            if wait_time > 0:
                wait_minutes = wait_time / 60
                print(f"Waiting {wait_minutes:.1f} minutes until next download...")
                time.sleep(wait_time)
            
            if download_radar():
                create_animation()
            
            # Cleanup old files periodically
            cleanup_old_files()
            
    except KeyboardInterrupt:
        print("\nStopped by user")

if __name__ == "__main__":
    main()