// Animation Controller
class RadarAnimation {
    constructor() {
        this.frames = document.querySelectorAll('.animation-frame');
        this.currentFrame = 0;
        this.isPlaying = false;
        this.interval = null;
        
        this.playBtn = document.getElementById('playBtn');
        this.pauseBtn = document.getElementById('pauseBtn');
        this.currentFrameSpan = document.getElementById('currentFrame');
        this.totalFramesSpan = document.getElementById('totalFrames');
        
        this.init();
    }
    
    init() {
        if (this.frames.length === 0) return;
        
        // Set total frames
        if (this.totalFramesSpan) {
            this.totalFramesSpan.textContent = this.frames.length;
        }
        
        // Bind events
        if (this.playBtn) {
            this.playBtn.addEventListener('click', () => this.play());
        }
        
        if (this.pauseBtn) {
            this.pauseBtn.addEventListener('click', () => this.pause());
        }
        
        // Auto-start animation
        setTimeout(() => this.play(), 1000);
    }
    
    play() {
        if (this.isPlaying) return;
        
        this.isPlaying = true;
        this.showControls('pause');
        
        this.interval = setInterval(() => {
            this.nextFrame();
        }, 800); // 0.8 seconds per frame
    }
    
    pause() {
        this.isPlaying = false;
        this.showControls('play');
        
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
    }
    
    showControls(state) {
        if (state === 'play') {
            if (this.playBtn) this.playBtn.style.display = 'inline-block';
            if (this.pauseBtn) this.pauseBtn.style.display = 'none';
        } else {
            if (this.playBtn) this.playBtn.style.display = 'none';
            if (this.pauseBtn) this.pauseBtn.style.display = 'inline-block';
        }
    }
    
    nextFrame() {
        // Hide current frame
        this.frames[this.currentFrame].classList.remove('active');
        
        // Move to next frame
        this.currentFrame = (this.currentFrame + 1) % this.frames.length;
        
        // Show new frame
        this.frames[this.currentFrame].classList.add('active');
        
        // Update counter
        if (this.currentFrameSpan) {
            this.currentFrameSpan.textContent = this.currentFrame + 1;
        }
    }
}

// Smart Polling System - 5 minute intervals + Page Visibility API
class SmartPolling {
    constructor() {
        this.pollInterval = 5 * 60 * 1000; // 5 minutes
        this.minUpdateInterval = 5 * 60 * 1000; // Don't check more than once per 5 minutes
        this.currentData = null;
        this.pollTimer = null;
        this.lastUpdateCheck = 0; // Global tracking of last update request
        
        this.init();
    }
    
    // Helper to add timestamps to logs
    log(message) {
        const timestamp = new Date().toLocaleTimeString();
        console.log(`[${timestamp}] ${message}`);
    }
    
    init() {
        // Only run on current page
        if (window.location.pathname !== '/') return;
        
        this.log('🔄 Pure AJAX polling initialized (5min intervals, no page reloads)');
        
        // Start regular polling
        this.startPolling();
        
        // Setup page visibility detection
        this.setupVisibilityHandling();
    }
    
    startPolling() {
        this.log('⏰ Starting polling - first check in 30 seconds, then every 5 minutes');
        
        // Initial check after 30 seconds
        setTimeout(() => this.checkForUpdates(), 30000);
        
        // Then check every 5 minutes
        this.pollTimer = setInterval(() => {
            this.log('🕒 Regular 5-minute polling triggered');
            this.checkForUpdates();
        }, this.pollInterval);
    }
    
    setupVisibilityHandling() {
        // Page Visibility API - check when tab becomes visible
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.log('👁️ Tab became visible - attempting update check (respects 5min cooldown)...');
                this.checkForUpdates(); // Global debouncing will handle rate limiting
            }
        });
    }
    
    setupFallbackRefresh() {
        // NO MORE FALLBACK REFRESH - pure AJAX only
        console.log('📡 Pure AJAX mode - no fallback refresh');
    }
    
    async checkForUpdates() {
        const now = Date.now();
        
        // Global debouncing: Don't check more than once per 5 minutes
        if (now - this.lastUpdateCheck < this.minUpdateInterval) {
            const timeLeft = Math.ceil((this.minUpdateInterval - (now - this.lastUpdateCheck)) / 1000 / 60);
            this.log(`⏳ Update check BLOCKED - ${timeLeft} minutes remaining in cooldown`);
            return;
        }
        
        this.lastUpdateCheck = now;
        
        try {
            this.log('📡 Checking for radar updates... [ALLOWED]');
            
            const response = await fetch('/api/status', {
                method: 'GET',
                headers: {
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            // Check if we have new data
            if (this.hasNewData(data)) {
                this.log('✨ New radar data detected - updating interface...');
                this.updateInterface(data);
            } else {
                this.log('📡 No new data available');
            }
            
            // Always update currentData for comparison
            this.currentData = data;
            
        } catch (error) {
            this.log(`❌ Failed to check for updates: ${error.message}`);
        }
    }
    
    hasNewData(newData) {
        if (!this.currentData) {
            // First time - initialize but don't update interface
            this.log('🔄 First data load - initializing baseline');
            return false; // Don't trigger update on first load
        }
        
        const hasChanges = this.currentData.latest_radar !== newData.latest_radar;
        this.log(`🔍 Data comparison: old="${this.currentData.latest_radar}" vs new="${newData.latest_radar}" → ${hasChanges ? 'CHANGED' : 'SAME'}`);
        
        return hasChanges;
    }
    
    updateInterface(data) {
        // Update current radar image
        this.updateCurrentRadar(data.latest_radar);
        
        // Update stats
        this.updateStats(data.stats);
        
        // NO MORE FULL PAGE REFRESH - just pure AJAX updates
        this.log('✅ Interface updated via AJAX');
    }
    
    updateCurrentRadar(latestRadarPath) {
        const radarImg = document.querySelector('.radar-image');
        if (radarImg && latestRadarPath) {
            const newSrc = `/radar/${latestRadarPath}`;
            this.log(`🖼️ Updating radar image: ${newSrc}`);
            
            // Smooth transition
            radarImg.style.opacity = '0.7';
            radarImg.src = newSrc;
            radarImg.onload = () => {
                radarImg.style.opacity = '1';
            };
        }
    }
    
    updateStats(stats) {
        // Update last update time
        const lastUpdateEl = document.querySelector('.stats-bar .stat .value');
        if (lastUpdateEl && stats.last_update) {
            lastUpdateEl.textContent = stats.last_update;
        }
        
        // Update total images count
        const totalImagesEl = document.querySelectorAll('.stats-bar .stat .value')[1];
        if (totalImagesEl && stats.total_images) {
            totalImagesEl.textContent = stats.total_images;
        }
        
        // Update status indicator
        const statusEl = document.querySelectorAll('.stats-bar .stat .value')[2];
        if (statusEl && stats.last_update_ago !== undefined) {
            if (stats.last_update_ago < 30) {
                statusEl.textContent = 'Live';
                statusEl.className = 'value status-online';
            } else {
                statusEl.textContent = `${Math.floor(stats.last_update_ago)}min ago`;
                statusEl.className = 'value status-warning';
            }
        }
    }
    
    destroy() {
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
            this.pollTimer = null;
        }
        this.log('🛑 Smart polling destroyed');
    }
}

// Image Modal Controller
class ImageModal {
    constructor() {
        this.modal = document.getElementById('imageModal');
        this.modalImage = document.getElementById('modalImage');
        this.closeBtn = document.querySelector('.close');
        
        this.init();
    }
    
    init() {
        if (!this.modal) return;
        
        // Handle clickable images
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('clickable-image') || 
                e.target.classList.contains('hourly-radar')) {
                const src = e.target.dataset.src || e.target.src;
                this.open(src);
            }
        });
        
        // Close modal events
        if (this.modal) {
            this.modal.addEventListener('click', (e) => {
                if (e.target === this.modal) {
                    this.close();
                }
            });
        }
        
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.close());
        }
        
        // Keyboard events
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.close();
            }
        });
    }
    
    open(src) {
        if (this.modal && this.modalImage) {
            this.modalImage.src = src;
            this.modal.style.display = 'block';
            document.body.style.overflow = 'hidden';
        }
    }
    
    close() {
        if (this.modal) {
            this.modal.style.display = 'none';
            document.body.style.overflow = 'auto';
        }
    }
}

// Status indicator
class StatusIndicator {
    constructor() {
        this.statusElement = document.querySelector('.status-online, .status-warning');
        this.init();
    }
    
    init() {
        if (!this.statusElement) return;
        
        // Check if status shows warning and add blinking effect
        if (this.statusElement.classList.contains('status-warning')) {
            this.statusElement.style.animation = 'blink 10s infinite';
        }
    }
}

// Smooth scrolling for anchor links
function smoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// Loading states for images
function handleImageLoading() {
    const images = document.querySelectorAll('img');
    
    images.forEach(img => {
        if (!img.complete) {
            img.style.opacity = '0.5';
            img.addEventListener('load', () => {
                img.style.opacity = '1';
            });
            
            img.addEventListener('error', () => {
                img.style.opacity = '0.3';
                img.alt = 'Failed to load image';
            });
        }
    });
}

// Touch gestures for mobile
function handleTouchGestures() {
    let startX = 0;
    let startY = 0;
    
    document.addEventListener('touchstart', (e) => {
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
    });
    
    document.addEventListener('touchend', (e) => {
        if (!startX || !startY) return;
        
        const endX = e.changedTouches[0].clientX;
        const endY = e.changedTouches[0].clientY;
        
        const diffX = startX - endX;
        const diffY = startY - endY;
        
        // Horizontal swipe detection
        if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 50) {
            if (diffX > 0) {
                // Swipe left - could navigate forward
                console.log('Swipe left detected');
            } else {
                // Swipe right - could navigate back
                console.log('Swipe right detected');
            }
        }
        
        startX = 0;
        startY = 0;
    });
}

// Global instances
let radarAnimation = null;
let smartPolling = null;

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Catalunya Radar Web App initializing...');
    
    // Initialize components
    radarAnimation = new RadarAnimation();
    window.radarAnimation = radarAnimation; // Make globally accessible
    
    smartPolling = new SmartPolling();
    new ImageModal();
    new StatusIndicator();
    
    // Initialize utility functions
    smoothScroll();
    handleImageLoading();
    handleTouchGestures();
    
    console.log('✅ Catalunya Radar Web App ready');
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (smartPolling) {
        smartPolling.destroy();
    }
});

// Add CSS for blinking animation and smooth transitions
const style = document.createElement('style');
style.textContent = `
    @keyframes blink {
        0%, 50% { opacity: 1; }
        51%, 100% { opacity: 0.5; }
    }
    
    .radar-image {
        transition: opacity 0.3s ease;
    }
`;
document.head.appendChild(style);

// Global functions for legacy compatibility
function openModal(src) {
    const modal = new ImageModal();
    modal.open(src);
}

function closeModal() {
    const modal = new ImageModal();
    modal.close();
}