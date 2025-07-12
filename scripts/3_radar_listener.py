#!/usr/bin/env python3
import requests
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

api_key = os.getenv('opendata_apikey')
if not api_key:
    print("Error: opendata_apikey not found in .env file")
    exit(1)

Path("data").mkdir(exist_ok=True)
Path("animations").mkdir(exist_ok=True)
Path("enhanced").mkdir(exist_ok=True)

def get_radar_timestamp(filepath):
    """Extract and adjust timestamp from filename"""
    basename = os.path.basename(filepath)
    timestamp_str = basename.split('_')[2] + basename.split('_')[3].split('.')[0]
    
    dt = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
    radar_time = dt - timedelta(minutes=10)  # Processing delay
    
    return radar_time.strftime('%d %b %H:%M CET')

def enhance_radar_image(input_path, output_path):
    """Add large timestamp to top of radar image"""
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
    today = datetime.now().strftime('%Y%m%d')
    enhanced_dir = Path("enhanced")
    
    images = sorted(enhanced_dir.glob(f"radar_ba_{today}_*.gif"))
    
    print(f"Found {len(images)} enhanced images:")
    for img in images:
        print(f"  {img.name}")
    
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
            
            # Enhance image with timestamp
            enhanced_filename = filename.replace('data/', 'enhanced/')
            enhance_radar_image(filename, enhanced_filename)
            print(f"Enhanced: {enhanced_filename}")
            
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
    """Enhance any existing raw images that haven't been enhanced yet"""
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
            print(f"Enhanced existing: {enhanced_path}")
            count += 1
    
    return count

def main():
    interval = 15  # minutes
    print(f"Starting radar listener (every {interval} minutes). Press Ctrl+C to stop.")
    
    print("Checking for existing images...")
    enhanced_count = enhance_existing_images()
    if enhanced_count > 0:
        print(f"Enhanced {enhanced_count} existing images")
    
    create_animation()
    
    try:
        while True:
            wait_time = calculate_wait_time()
            if wait_time > 0:
                wait_minutes = wait_time / 60
                print(f"Waiting {wait_minutes:.1f} minutes until next download...")
                time.sleep(wait_time)
            
            download_radar()
            create_animation()
    except KeyboardInterrupt:
        print("\nStopped by user")

if __name__ == "__main__":
    main()