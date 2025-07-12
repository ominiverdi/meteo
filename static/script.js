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

// Modal Image Viewer
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

// Auto-refresh functionality
class AutoRefresh {
    constructor(interval = 15) { // minutes
        this.interval = interval * 60 * 1000; // convert to milliseconds
        this.init();
    }
    
    init() {
        // Only auto-refresh on current page
        if (window.location.pathname === '/') {
            setTimeout(() => {
                console.log('Auto-refreshing page...');
                window.location.reload();
            }, this.interval);
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
            this.statusElement.style.animation = 'blink 2s infinite';
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

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize components
    new RadarAnimation();
    new ImageModal();
    new AutoRefresh(15); // 15 minutes
    new StatusIndicator();
    
    // Initialize utility functions
    smoothScroll();
    handleImageLoading();
    handleTouchGestures();
    
    console.log('Catalunya Radar Web App initialized');
});

// Add CSS for blinking animation
const style = document.createElement('style');
style.textContent = `
    @keyframes blink {
        0%, 50% { opacity: 1; }
        51%, 100% { opacity: 0.5; }
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