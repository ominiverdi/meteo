# Barcelona Weather Radar Web App

Real-time weather radar monitoring system for Barcelona area using AEMET data with a modern web interface.

## Features

- **Live Radar Display**: Current Barcelona area radar with auto-refresh
- **Recent Activity**: 5-hour animated radar loops 
- **Daily Archives**: Full day animations with hourly breakdown
- **Historical Data**: Browse past weather events
- **Mobile Friendly**: Responsive design with touch gestures
- **Auto Downloads**: Generates GIF and MP4 animations
- **WhatsApp Ready**: MP4 format for easy sharing

## Quick Start

### 1. Prerequisites
```bash
sudo apt install ffmpeg python3-venv
```

### 2. Installation
```bash
git clone <your-repo-url> meteo
cd meteo
python3 -m venv .venv_meteo
source .venv_meteo/bin/activate
pip install -r requirements.txt
```

### 3. Configuration
Create `.env` file:
```
opendata_apikey=your_aemet_api_key_here
```

Get API key from: https://opendata.aemet.es/centrodedescargas/obtencionAPIKey

### 4. Set Timezone (for Spain deployment)
```bash
sudo timedatectl set-timezone Europe/Madrid
```

### 5. Production Deployment (systemd services)
```bash
# Create listener service
sudo tee /etc/systemd/system/meteo-listener.service > /dev/null << EOF
[Unit]
Description=Meteo Radar Listener
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/meteo
Environment=PATH=/root/meteo/.venv_meteo/bin
ExecStart=/root/meteo/.venv_meteo/bin/python scripts/3_radar_listener.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Create web service
sudo tee /etc/systemd/system/meteo-webapp.service > /dev/null << EOF
[Unit]
Description=Meteo Web App
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/meteo
Environment=PATH=/root/meteo/.venv_meteo/bin
ExecStart=/root/meteo/.venv_meteo/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable meteo-listener meteo-webapp
sudo systemctl start meteo-listener meteo-webapp
```

### 6. Access Web Interface
Open browser to: `http://your-server-ip:5000`

## File Structure
```
meteo/
├── app.py                 # Flask web application
├── scripts/
│   └── 3_radar_listener.py   # Background data collector
├── templates/             # HTML templates
├── static/               # CSS and JavaScript
├── data/                 # Raw radar images
├── enhanced/             # Images with timestamps
└── animations/           # Daily GIF/MP4 files
```

## API Endpoints

- `/` - Current radar and recent activity
- `/today` - Today's full day view
- `/history` - Available dates
- `/history/YYYYMMDD` - Specific date
- `/api/status` - JSON status info

## Production Deployment

### Service Management
```bash
# Check status
systemctl status meteo-listener meteo-webapp

# View logs
journalctl -u meteo-listener -f
journalctl -u meteo-webapp -f

# Restart services
systemctl restart meteo-listener meteo-webapp

# Stop services
systemctl stop meteo-listener meteo-webapp
```

## Data Management

- **Retention**: Current year kept, older data auto-deleted
- **Storage**: ~50MB per month, ~600MB per year
- **Cleanup**: Automatic via listener script
- **Backup**: Download important events before expiration

## Development

### Adding Features
- Storm detection algorithms
- Precipitation intensity analysis  
- Weather alerts system
- Leaflet.js map integration

### Customization
- Modify update intervals in `3_radar_listener.py`
- Adjust retention policy in cleanup functions
- Change styling in `static/style.css`

## Troubleshooting

**No data appearing:**
- Check API key in `.env`
- Verify listener script is running
- Check rate limits (max 1 request/minute)

**Missing animations:**
- Ensure ffmpeg is installed
- Check file permissions in directories
- Verify 2+ images exist for animation

**Web interface errors:**
- Check Flask app is running on port 5000
- Verify file paths are correct
- Check browser console for JavaScript errors

## License

MIT License - Feel free to use and modify for your projects.

## Credits

- Weather data: AEMET (Spanish Meteorological Agency)
- Built with Flask, vanilla JavaScript, and modern CSS