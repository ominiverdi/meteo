#!/usr/bin/env python3
from flask import Flask, render_template, send_file, jsonify
from pathlib import Path
from datetime import datetime, timedelta
import glob
import os

app = Flask(__name__)

def get_latest_radar():
    """Get the most recent enhanced radar image"""
    images = sorted(glob.glob('enhanced/radar_ba_*.gif'))
    return images[-1] if images else None

def get_recent_animation():
    """Get recent hours animation (last 3-5 hours of images)"""
    today = datetime.now().strftime('%Y%m%d')
    
    # Get images from last 5 hours
    cutoff = datetime.now() - timedelta(hours=5)
    recent_images = []
    
    for img_path in sorted(glob.glob(f'enhanced/radar_ba_{today}_*.gif')):
        # Extract timestamp from filename
        basename = os.path.basename(img_path)
        timestamp_str = basename.split('_')[2] + basename.split('_')[3].split('.')[0]
        img_time = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
        
        if img_time >= cutoff:
            recent_images.append(img_path)
    
    return recent_images

def get_daily_animation(date_str=None):
    """Get full day animation for specified date"""
    if not date_str:
        date_str = datetime.now().strftime('%Y%m%d')
    
    gif_file = f'animations/radar_animation_{date_str}.gif'
    mp4_file = f'animations/radar_animation_{date_str}.mp4'
    
    return {
        'gif': gif_file if os.path.exists(gif_file) else None,
        'mp4': mp4_file if os.path.exists(mp4_file) else None,
        'date': date_str
    }

def get_weather_stats():
    """Get basic weather statistics"""
    latest = get_latest_radar()
    if not latest:
        return {'last_update': 'No data', 'total_images': 0}
    
    # Get file timestamp
    basename = os.path.basename(latest)
    timestamp_str = basename.split('_')[2] + basename.split('_')[3].split('.')[0]
    last_update = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
    
    today = datetime.now().strftime('%Y%m%d')
    today_images = len(glob.glob(f'enhanced/radar_ba_{today}_*.gif'))
    
    return {
        'last_update': last_update.strftime('%H:%M CET'),
        'total_images': today_images,
        'last_update_ago': (datetime.now() - last_update).total_seconds() // 60
    }

def get_available_dates():
    """Get list of available dates for history"""
    dates = set()
    for file in glob.glob('animations/radar_animation_*.gif'):
        basename = os.path.basename(file)
        date_str = basename.split('_')[2].split('.')[0]
        dates.add(date_str)
    
    return sorted(dates, reverse=True)

@app.route('/')
def index():
    """Homepage with current radar and recent animation"""
    latest_radar = get_latest_radar()
    recent_images = get_recent_animation()
    stats = get_weather_stats()
    
    return render_template('index.html', 
                         latest_radar=latest_radar,
                         recent_images=recent_images,
                         stats=stats)

@app.route('/today')
def today():
    """Today's full animation and hourly images"""
    today_str = datetime.now().strftime('%Y%m%d')
    animation = get_daily_animation(today_str)
    
    # Get all today's images
    hourly_images = sorted(glob.glob(f'enhanced/radar_ba_{today_str}_*.gif'))
    
    return render_template('today.html',
                         animation=animation,
                         hourly_images=hourly_images,
                         date=today_str)

@app.route('/history')
def history():
    """History overview with available dates"""
    dates = get_available_dates()
    return render_template('history.html', dates=dates)

@app.route('/history/<date_str>')
def history_date(date_str):
    """Specific date history"""
    animation = get_daily_animation(date_str)
    
    # Get images for this date
    images = sorted(glob.glob(f'enhanced/radar_ba_{date_str}_*.gif'))
    
    return render_template('date.html',
                         animation=animation,
                         images=images,
                         date=date_str)

@app.route('/radar/<path:filename>')
def serve_radar(filename):
    """Serve radar images"""
    return send_file(filename)

@app.route('/animation/<path:filename>')
def serve_animation(filename):
    """Serve animation files"""
    return send_file(filename)

@app.route('/enhanced')
def enhanced_view():
    """Enhanced radar+satellite view"""
    today_str = datetime.now().strftime('%Y%m%d')
    
    # Get all enhanced images (today + recent days)
    enhanced_files = sorted(glob.glob('enhanced_weather/enhanced_weather_*.png'))
    
    # Get today's enhanced images
    today_enhanced = [f for f in enhanced_files if today_str in f]
    
    # Latest enhanced image
    latest_enhanced = enhanced_files[-1] if enhanced_files else None
    
    return render_template('enhanced.html',
                         latest_enhanced=latest_enhanced,
                         today_enhanced=today_enhanced,
                         enhanced_files=enhanced_files[-20:])  # Last 20

@app.route('/enhanced_weather/<path:filename>')
def serve_enhanced_weather(filename):
    """Serve enhanced weather images"""
    return send_file(f'enhanced_weather/{filename}')
    
@app.route('/api/status')
def api_status():
    """API endpoint for current status"""
    return jsonify({
        'status': 'online',
        'stats': get_weather_stats(),
        'latest_radar': get_latest_radar(),
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)