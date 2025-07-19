#!/usr/bin/env python3
"""
Enhanced Weather Listener Service
Monitors radar data and creates enhanced radar+satellite visualizations
"""

import os
import json
import glob
import time
import psutil
import subprocess
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

import requests
try:
    import eumdac
except ImportError:
    print("❌ EUMDAC not installed. Run: pip install eumdac")
    exit(1)

try:
    from osgeo import gdal, osr
except ImportError:
    print("❌ GDAL not installed. Run: sudo apt install python3-gdal")
    exit(1)

import warnings
warnings.filterwarnings('ignore')

# Load environment variables
load_dotenv()

# Configuration
POLL_INTERVAL_MINUTES = 3
SATELLITE_TIME_TOLERANCE_MINUTES = 7
LOCK_FILE = Path("enhanced_weather.lock")
OUTPUT_DIR = Path("enhanced_weather")
TEMP_DIR = Path("temp_enhanced")

def setup_logging():
    """Setup basic logging"""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('enhanced_weather_listener.log')
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def check_and_create_lock():
    """Check for existing lock and create new one if safe"""
    if LOCK_FILE.exists():
        try:
            with open(LOCK_FILE, 'r') as f:
                lock_data = json.load(f)
            
            pid = lock_data.get('pid')
            if pid and psutil.pid_exists(pid):
                logger.info(f"Service already running (PID: {pid})")
                return False
            else:
                logger.info("Removing stale lock file")
                LOCK_FILE.unlink()
        except Exception as e:
            logger.warning(f"Error reading lock file: {e}")
            LOCK_FILE.unlink()
    
    # Create new lock
    lock_data = {
        'pid': os.getpid(),
        'start_time': datetime.now().isoformat(),
        'service': 'enhanced_weather_listener'
    }
    
    with open(LOCK_FILE, 'w') as f:
        json.dump(lock_data, f, indent=2)
    
    logger.info(f"Lock created (PID: {os.getpid()})")
    return True

def remove_lock():
    """Remove lock file"""
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()
        logger.info("Lock removed")

def extract_timestamp_from_radar(radar_file):
    """Extract timestamp from radar filename"""
    basename = os.path.basename(radar_file)
    # Format: radar_ba_20250719_143000.gif
    parts = basename.split('_')
    if len(parts) >= 4:
        date_part = parts[2]  # 20250719
        time_part = parts[3].split('.')[0]  # 143000
        return f"{date_part}_{time_part}"
    return None

def get_unprocessed_files():
    """Get list of radar files that don't have enhanced versions"""
    today = datetime.now().strftime('%Y%m%d')
    radar_files = sorted(glob.glob(f'data/radar_ba_{today}_*.gif'))
    
    unprocessed = []
    for radar_file in radar_files:
        timestamp = extract_timestamp_from_radar(radar_file)
        if timestamp:
            enhanced_file = OUTPUT_DIR / f"enhanced_weather_{timestamp}.png"
            if not enhanced_file.exists():
                unprocessed.append(radar_file)
    
    return unprocessed

def georeference_radar(radar_file, temp_dir):
    """Georeference radar image using QGIS method"""
    logger.info(f"Georeferencing: {os.path.basename(radar_file)}")
    
    # QGIS-measured Ground Control Points (all 39)
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
    
    # Clean and georeference radar image
    timestamp = extract_timestamp_from_radar(radar_file)
    cleaned_file = temp_dir / f"radar_cleaned_{timestamp}.png"
    georef_file = temp_dir / f"radar_georef_{timestamp}.tif"
    
    try:
        # Clean radar image (remove footer, make transparent)
        clean_radar_image(radar_file, cleaned_file)
        
        # Create temporary GCP file
        temp_gcp_file = temp_dir / f"temp_gcp_{timestamp}.tif"
        
        # Build GCP parameters
        gcp_params = []
        for px, py, mx, my in qgis_gcps:
            gcp_params.extend(['-gcp', str(px), str(py), str(mx), str(my)])
        
        # Step 1: Add GCPs
        cmd1 = [
            'gdal_translate', '-of', 'GTiff', '-co', 'COMPRESS=LZW',
            *gcp_params, str(cleaned_file), str(temp_gcp_file)
        ]
        subprocess.run(cmd1, check=True, capture_output=True)
        
        # Step 2: Warp to final projection
        cmd2 = [
            'gdalwarp', '-r', 'near', '-order', '3',
            '-co', 'COMPRESS=LZW', '-dstalpha', '-overwrite',
            '-t_srs', 'EPSG:3857', str(temp_gcp_file), str(georef_file)
        ]
        subprocess.run(cmd2, check=True, capture_output=True)
        
        logger.info(f"Georeferencing completed: {georef_file}")
        return str(georef_file)
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Georeferencing failed: {e}")
        return None

def clean_radar_image(input_path, output_path):
    """Clean radar image: remove footer, header text, logo, and make background transparent"""
    from PIL import Image, ImageDraw
    
    with Image.open(input_path) as img:
        img = img.convert('RGBA')
        width, height = img.size
        
        # Create a copy to modify
        cleaned_img = img.copy()
        
        # Step 1: Clear header text area (158x14 top-left)
        for x in range(min(158, width)):
            for y in range(min(14, height)):
                cleaned_img.putpixel((x, y), (0, 0, 0, 0))  # Transparent
        
        # Step 2: Clear AEMET logo area (392,0 to 480,46)
        for x in range(392, min(480, width)):
            for y in range(min(46, height)):
                cleaned_img.putpixel((x, y), (0, 0, 0, 0))  # Transparent
        
        # Step 3: Remove footer (bottom 50 pixels)
        radar_data = cleaned_img.crop((0, 0, width, height - 50))
        
        # Step 4: Interpolate yellow boundary lines (8-neighbor averaging)
        radar_data = interpolate_yellow_pixels(radar_data)
        
        # Step 5: Make background colors transparent
        data = list(radar_data.getdata())
        new_data = []
        
        for pixel in data:
            r, g, b, a = pixel
            
            # Make black transparent
            if r == 0 and g == 0 and b == 0:
                new_data.append((0, 0, 0, 0))
            # Make grey transparent (RGB 127,127,127)
            elif r == 127 and g == 127 and b == 127:
                new_data.append((0, 0, 0, 0))
            # Keep all other colors (precipitation data)
            else:
                new_data.append(pixel)
        
        radar_data.putdata(new_data)
        radar_data.save(output_path)

def interpolate_yellow_pixels(img):
    """Replace yellow pixels with average of 8 surrounding non-yellow neighbors"""
    width, height = img.size
    result = img.copy()
    
    for y in range(height):
        for x in range(width):
            pixel = img.getpixel((x, y))
            
            # Check for yellowish colors
            is_yellow = False
            if len(pixel) >= 3:
                r, g, b = pixel[0], pixel[1], pixel[2]
                if (r > 80 and g > 80 and b < 50 and abs(r-g) < 30):
                    is_yellow = True
            
            if is_yellow:
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
                                if not (nr > 80 and ng > 80 and nb < 50 and abs(nr-ng) < 30):
                                    neighbors.append(neighbor)
                
                if neighbors:
                    # Calculate average RGB(A)
                    avg_r = sum(p[0] for p in neighbors) // len(neighbors)
                    avg_g = sum(p[1] for p in neighbors) // len(neighbors)
                    avg_b = sum(p[2] for p in neighbors) // len(neighbors)
                    avg_a = sum(p[3] for p in neighbors) // len(neighbors) if len(neighbors[0]) > 3 else 255
                    
                    result.putpixel((x, y), (avg_r, avg_g, avg_b, avg_a))
                else:
                    # No non-yellow neighbors, make transparent
                    result.putpixel((x, y), (0, 0, 0, 0))
    
    return result

def setup_eumdac():
    """Setup EUMDAC authentication"""
    consumer_key = os.getenv('eumetsat_consumer_key')
    consumer_secret = os.getenv('eumetsat_consumer_secret')
    
    if not consumer_key or not consumer_secret:
        raise Exception("Missing EUMETSAT credentials in .env file")
    
    credentials = (consumer_key, consumer_secret)
    token = eumdac.AccessToken(credentials)
    return eumdac.DataStore(token)

def download_satellite_data(radar_timestamp, temp_dir):
    """Download Meteosat data matching radar timing"""
    logger.info(f"Downloading satellite data for: {radar_timestamp}")
    
    try:
        # Parse radar timestamp
        dt = datetime.strptime(radar_timestamp, '%Y%m%d_%H%M%S')
        
        # Search window
        tolerance = timedelta(minutes=SATELLITE_TIME_TOLERANCE_MINUTES)
        search_start = dt - tolerance
        search_end = dt + tolerance
        
        # Setup EUMDAC
        datastore = setup_eumdac()
        collection = datastore.get_collection('EO:EUM:DAT:MSG:HRSEVIRI')
        
        # Search for products
        products = collection.search(
            dtstart=search_start,
            dtend=search_end,
            bbox='0.7, 38.6, 4.5, 42.9'  # Catalunya + Balears only
        )
        
        product_list = list(products)
        if not product_list:
            logger.warning(f"No satellite data found for {radar_timestamp}")
            return None
        
        # Download first matching product
        product = product_list[0]
        logger.info(f"Downloading: {product}")
        
        with product.open() as fsrc:
            zip_file = temp_dir / fsrc.name
            with open(zip_file, 'wb') as fdst:
                shutil.copyfileobj(fsrc, fdst)
        
        logger.info(f"Satellite data downloaded: {zip_file}")
        
        # Extract ZIP file to find .nat file
        import zipfile
        nat_file = None
        
        try:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                # List contents
                zip_contents = zip_ref.namelist()
                logger.info(f"ZIP contents: {len(zip_contents)} files")
                
                # Find .nat file
                nat_files = [f for f in zip_contents if f.endswith('.nat')]
                if nat_files:
                    nat_filename = nat_files[0]
                    # Extract to temp directory
                    zip_ref.extract(nat_filename, temp_dir)
                    nat_file = temp_dir / nat_filename
                    logger.info(f"Extracted .nat file: {nat_file}")
                else:
                    logger.warning("No .nat file found in ZIP")
                    
        except zipfile.BadZipFile:
            logger.error(f"Invalid ZIP file: {zip_file}")
        
        # Cleanup ZIP file
        if zip_file.exists():
            zip_file.unlink()
            
        return str(nat_file) if nat_file and nat_file.exists() else None
        
    except Exception as e:
        logger.error(f"Satellite download failed: {e}")
        return None

def extract_water_vapor(nat_file, radar_georef_file, temp_dir):
    """Extract water vapor channels from Meteosat data"""
    logger.info("Extracting water vapor channels")
    
    try:
        # Get radar extent for subsetting
        extent = get_radar_extent_for_geostationary(nat_file, radar_georef_file)
        if not extent:
            return []
        
        # Subset Meteosat data
        subset_file = temp_dir / f"meteosat_subset.tif"
        if not subset_meteosat_data(nat_file, extent, subset_file):
            return []
        
        # Extract water vapor bands
        timestamp = extract_timestamp_from_radar(radar_georef_file)
        output_files = extract_wv_bands(subset_file, temp_dir, timestamp)
        
        logger.info(f"Water vapor extraction completed: {len(output_files)} files")
        return output_files
        
    except Exception as e:
        logger.error(f"Water vapor extraction failed: {e}")
        return []

def get_radar_extent_for_geostationary(nat_file, radar_file):
    """Get radar extent in geostationary projection"""
    try:
        radar_ds = gdal.Open(radar_file)
        nat_ds = gdal.Open(nat_file)
        
        if not radar_ds or not nat_ds:
            return None
        
        # Get radar bounds
        gt = radar_ds.GetGeoTransform()
        cols, rows = radar_ds.RasterXSize, radar_ds.RasterYSize
        
        min_x = gt[0]
        max_y = gt[3]
        max_x = min_x + (gt[1] * cols)
        min_y = max_y + (gt[5] * rows)
        
        # Transform to geostationary
        radar_srs = osr.SpatialReference()
        radar_srs.ImportFromWkt(radar_ds.GetProjection())
        
        nat_srs = osr.SpatialReference()
        nat_srs.ImportFromWkt(nat_ds.GetProjection())
        
        transform = osr.CoordinateTransformation(radar_srs, nat_srs)
        
        corner1_x, corner1_y, _ = transform.TransformPoint(min_x, min_y)
        corner2_x, corner2_y, _ = transform.TransformPoint(max_x, max_y)
        
        return {
            'min_x': min(corner1_x, corner2_x),
            'max_x': max(corner1_x, corner2_x),
            'min_y': min(corner1_y, corner2_y),
            'max_y': max(corner1_y, corner2_y)
        }
        
    except Exception as e:
        logger.error(f"Extent calculation failed: {e}")
        return None
    finally:
        if 'radar_ds' in locals():
            radar_ds = None
        if 'nat_ds' in locals():
            nat_ds = None

def subset_meteosat_data(nat_file, extent, output_file):
    """Subset Meteosat data to radar area"""
    try:
        buffer = 50000  # 50km buffer
        min_x = extent['min_x'] - buffer
        max_x = extent['max_x'] + buffer
        min_y = extent['min_y'] - buffer
        max_y = extent['max_y'] + buffer
        
        translate_options = gdal.TranslateOptions(
            projWin=[min_x, max_y, max_x, min_y],
            format='GTiff',
            creationOptions=['COMPRESS=LZW']
        )
        
        ds = gdal.Translate(str(output_file), nat_file, options=translate_options)
        if ds:
            ds = None
            return True
        return False
        
    except Exception as e:
        logger.error(f"Meteosat subset failed: {e}")
        return False

def extract_wv_bands(subset_file, temp_dir, timestamp):
    """Extract water vapor bands"""
    try:
        ds = gdal.Open(str(subset_file))
        if not ds:
            return []
        
        # Water vapor bands: 5 (6.2μm) and 6 (7.3μm)
        wv_bands = {5: 'wv_6.2um', 6: 'wv_7.3um'}
        output_files = []
        
        for band_num, band_name in wv_bands.items():
            # Extract band
            temp_band_file = temp_dir / f"temp_band_{band_num}.tif"
            
            translate_options = gdal.TranslateOptions(
                bandList=[band_num],
                format='GTiff',
                outputType=gdal.GDT_Float32,
                creationOptions=['COMPRESS=LZW']
            )
            
            band_ds = gdal.Translate(str(temp_band_file), ds, options=translate_options)
            if not band_ds:
                continue
            band_ds = None
            
            # Reproject to Web Mercator
            output_file = temp_dir / f"{band_name}_{timestamp}.tif"
            
            warp_options = gdal.WarpOptions(
                dstSRS='EPSG:3857',
                format='GTiff',
                resampleAlg=gdal.GRA_Bilinear,
                creationOptions=['COMPRESS=LZW']
            )
            
            final_ds = gdal.Warp(str(output_file), str(temp_band_file), options=warp_options)
            if final_ds:
                output_files.append(str(output_file))
                final_ds = None
            
            # Cleanup
            if temp_band_file.exists():
                temp_band_file.unlink()
        
        ds = None
        return output_files
        
    except Exception as e:
        logger.error(f"Band extraction failed: {e}")
        return []

def create_enhanced_image(radar_georef_file, water_vapor_files, output_file):
    """Create enhanced radar+satellite visualization with city labels"""
    logger.info("Creating enhanced visualization")
    
    try:
        import numpy as np
        import matplotlib.pyplot as plt
        from matplotlib.colors import LinearSegmentedColormap
        from rasterio import open as rasterio_open
        import geopandas as gpd
        
        # Load radar data
        with rasterio_open(radar_georef_file) as src:
            radar_data = src.read(1)
            radar_bounds = src.bounds
        
        # Create figure
        fig, ax = plt.subplots(1, 1, figsize=(12, 10))
        extent = [radar_bounds.left, radar_bounds.right, radar_bounds.bottom, radar_bounds.top]
        
        # Background: Water vapor (if available)
        if water_vapor_files:
            wv_file = next((f for f in water_vapor_files if '6.2um' in f), water_vapor_files[0])
            with rasterio_open(wv_file) as src:
                wv_data = src.read(1)
                wv_normalized = (wv_data - np.nanmin(wv_data)) / (np.nanmax(wv_data) - np.nanmin(wv_data))
                ax.imshow(wv_normalized, extent=extent, cmap='gray', alpha=0.5, origin='upper')
        
        # Foreground: Radar data
        radar_colors = ['#000000', '#0000ff', '#00ffff', '#00ff00', '#ffff00', '#ff8000', '#ff0000', '#c8005a']
        radar_cmap = LinearSegmentedColormap.from_list('radar', radar_colors)
        
        radar_masked = np.ma.masked_where(radar_data == 0, radar_data)
        if radar_masked.count() > 0:
            ax.imshow(radar_masked, extent=extent, cmap=radar_cmap, alpha=0.8, origin='upper')
        
        # Load and add vector overlays
        vectors = load_vector_data()
        
        # Province boundaries
        if vectors and 'provinces' in vectors:
            try:
                vectors['provinces'].to_crs('EPSG:3857').plot(
                    ax=ax, facecolor='none', edgecolor='yellow', linewidth=2
                )
                logger.info("Added province boundaries")
            except Exception as e:
                logger.warning(f"Failed to add provinces: {e}")
        
        # City labels
        if vectors and 'cities' in vectors:
            try:
                cities_3857 = vectors['cities'].to_crs('EPSG:3857')
                for idx, city in cities_3857.iterrows():
                    x, y = city.geometry.x, city.geometry.y
                    name = city['name']
                    
                    # Add city point and label
                    ax.plot(x, y, 'o', color='white', markersize=6, markeredgecolor='black', markeredgewidth=1)
                    ax.text(x + 3000, y + 3000, name, fontsize=10, color='white', 
                           weight='bold', ha='left', va='bottom',
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))
                
                logger.info(f"Added {len(cities_3857)} city labels")
            except Exception as e:
                logger.warning(f"Failed to add cities: {e}")
        
        # Styling
        ax.set_xlim(radar_bounds.left, radar_bounds.right)
        ax.set_ylim(radar_bounds.bottom, radar_bounds.top)
        
        # Extract timestamp for title
        timestamp = extract_timestamp_from_radar(radar_georef_file)
        if timestamp:
            dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
            title_time = dt.strftime('%d %b %Y %H:%M CET')
            ax.set_title(f'Catalunya Weather: Radar + Satellite - {title_time}', fontsize=14, pad=20)
        
        ax.set_xticks([])
        ax.set_yticks([])
        
        # Save
        fig.savefig(output_file, dpi=300, bbox_inches='tight', 
                   facecolor='black', edgecolor='none')
        plt.close(fig)
        
        logger.info(f"Enhanced image saved: {output_file}")
        return True
        
    except Exception as e:
        logger.error(f"Enhanced image creation failed: {e}")
        return False

def load_vector_data():
    """Load province borders and cities"""
    vectors = {}
    
    try:
        import geopandas as gpd  # Import here
        
        # Province borders
        province_file = 'naturalearthdata/ne_10m_admin_1_states_provinces.shp'
        if os.path.exists(province_file):
            provinces = gpd.read_file(province_file)
            # Filter Catalunya provinces
            catalunya_provinces = provinces[provinces['name'].isin(['Barcelona', 'Tarragona', 'Girona', 'Lleida'])]
            if not catalunya_provinces.empty:
                vectors['provinces'] = catalunya_provinces
                logger.info(f"Loaded {len(catalunya_provinces)} province boundaries")
        else:
            logger.warning(f"Province file not found: {province_file}")
        
        # Cities
        cities_file = 'osm/catalunya_large_cities.geojson'
        if os.path.exists(cities_file):
            cities = gpd.read_file(cities_file)
            # Filter out non-Catalunya cities and take top cities
            catalunya_cities = cities[~cities['name'].isin(['Perpignan'])]
            vectors['cities'] = catalunya_cities.head(8)  # Top 8 cities
            logger.info(f"Loaded {len(vectors['cities'])} cities")
        else:
            logger.warning(f"Cities file not found: {cities_file}")
            
    except Exception as e:
        logger.error(f"Failed to load vector data: {e}")
    
    return vectors

def process_radar_file(radar_file):
    """Process single radar file through complete pipeline"""
    logger.info(f"Processing: {os.path.basename(radar_file)}")
    
    timestamp = extract_timestamp_from_radar(radar_file)
    if not timestamp:
        logger.error(f"Could not extract timestamp from: {radar_file}")
        return False
    
    # Create temp directory
    TEMP_DIR.mkdir(exist_ok=True)
    temp_session_dir = TEMP_DIR / f"session_{timestamp}"
    temp_session_dir.mkdir(exist_ok=True)
    
    try:
        # Step 1: Georeference radar
        radar_georef_file = georeference_radar(radar_file, temp_session_dir)
        if not radar_georef_file:
            logger.error("Georeferencing failed")
            return False
        
        # Step 2: Download satellite data
        satellite_file = download_satellite_data(timestamp, temp_session_dir)
        if not satellite_file:
            logger.warning("No satellite data available, skipping")
            return False
        
        # Step 3: Extract water vapor
        water_vapor_files = extract_water_vapor(satellite_file, radar_georef_file, temp_session_dir)
        
        # Step 4: Create enhanced image
        output_file = OUTPUT_DIR / f"enhanced_weather_{timestamp}.png"
        OUTPUT_DIR.mkdir(exist_ok=True)
        
        success = create_enhanced_image(radar_georef_file, water_vapor_files, output_file)
        
        if success:
            logger.info(f"Successfully processed: {os.path.basename(radar_file)}")
        
        return success
        
    except Exception as e:
        logger.error(f"Processing failed for {radar_file}: {e}")
        return False
    
    finally:
        # Cleanup temp directory
        if temp_session_dir.exists():
            shutil.rmtree(temp_session_dir, ignore_errors=True)

def cleanup_old_files():
    """Clean up files older than 365 days"""
    cutoff_date = datetime.now() - timedelta(days=365)
    cutoff_str = cutoff_date.strftime('%Y%m%d')
    
    # Clean enhanced images
    for file in OUTPUT_DIR.glob('enhanced_weather_*.png'):
        try:
            # Extract date from filename
            filename = file.name
            date_part = filename.split('_')[2]  # enhanced_weather_YYYYMMDD_HHMMSS.png
            if date_part < cutoff_str:
                file.unlink()
                logger.info(f"Cleaned old file: {filename}")
        except Exception as e:
            logger.warning(f"Could not clean file {file}: {e}")

def main():
    """Main service loop"""
    logger.info("Enhanced Weather Listener starting...")
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    # Create lock
    if not check_and_create_lock():
        return 1
    
    try:
        logger.info(f"Service started, polling every {POLL_INTERVAL_MINUTES} minutes")
        
        while True:
            try:
                # Get unprocessed files
                unprocessed_files = get_unprocessed_files()
                
                if unprocessed_files:
                    logger.info(f"Found {len(unprocessed_files)} unprocessed files")
                    
                    for radar_file in unprocessed_files:
                        process_radar_file(radar_file)
                else:
                    logger.debug("No unprocessed files found")
                
                # Cleanup old files (once per day at startup)
                cleanup_old_files()
                
                # Wait for next cycle
                time.sleep(POLL_INTERVAL_MINUTES * 60)
                
            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
                
    finally:
        remove_lock()
        # Cleanup temp directory
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
    
    logger.info("Enhanced Weather Listener stopped")
    return 0

def check_dependencies():
    """Check required dependencies and tools"""
    try:
        # Check GDAL tools
        subprocess.run(['gdal_translate', '--version'], check=True, capture_output=True)
        subprocess.run(['gdalwarp', '--version'], check=True, capture_output=True)
        
        # Check API credentials
        if not os.getenv('eumetsat_consumer_key') or not os.getenv('eumetsat_consumer_secret'):
            logger.error("Missing EUMETSAT credentials in .env file")
            return False
        
        return True
        
    except subprocess.CalledProcessError:
        logger.error("GDAL tools not found. Install: sudo apt install gdal-bin")
        return False
    except Exception as e:
        logger.error(f"Dependency check failed: {e}")
        return False

if __name__ == "__main__":
    exit(main())