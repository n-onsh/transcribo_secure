import time
from collections import defaultdict
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiter implementation using sliding window"""
    def __init__(self, window_size: int = 60, max_requests: int = 100):
        self.window_size = window_size  # Window size in seconds
        self.max_requests = max_requests  # Maximum requests per window
        self.requests: Dict[str, list] = defaultdict(list)  # IP -> list of timestamps
        
    def is_allowed(self, ip: str) -> Tuple[bool, int]:
        """Check if request is allowed"""
        try:
            current_time = time.time()
            
            # Remove old timestamps
            self.requests[ip] = [
                ts for ts in self.requests[ip]
                if current_time - ts < self.window_size
            ]
            
            # Check rate limit
            if len(self.requests[ip]) >= self.max_requests:
                wait_time = int(self.requests[ip][0] + self.window_size - current_time)
                return False, wait_time
            
            # Add new request
            self.requests[ip].append(current_time)
            return True, 0
            
        except Exception as e:
            logger.error(f"Rate limiter error: {str(e)}")
            return True, 0  # Allow request on error
            
    def cleanup(self):
        """Remove old entries"""
        try:
            current_time = time.time()
            cutoff = current_time - self.window_size
            
            # Remove old timestamps from all IPs
            for ip in list(self.requests.keys()):
                self.requests[ip] = [
                    ts for ts in self.requests[ip]
                    if ts > cutoff
                ]
                
                # Remove empty entries
                if not self.requests[ip]:
                    del self.requests[ip]
                    
        except Exception as e:
            logger.error(f"Rate limiter cleanup error: {str(e)}")
