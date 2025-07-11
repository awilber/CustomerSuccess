import logging
from datetime import datetime
from collections import deque
from threading import Lock
import json

class ConsoleLogHandler(logging.Handler):
    """Custom logging handler that stores logs in memory for the console panel"""
    
    def __init__(self, max_logs=1000):
        super().__init__()
        self.logs = deque(maxlen=max_logs)
        self.lock = Lock()
        self.subscribers = []
        
    def emit(self, record):
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'message': self.format(record),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        with self.lock:
            self.logs.append(log_entry)
            # Notify subscribers
            for subscriber in self.subscribers:
                try:
                    subscriber(log_entry)
                except:
                    pass
    
    def get_logs(self, level=None, limit=100):
        """Get recent logs, optionally filtered by level"""
        with self.lock:
            logs = list(self.logs)
            
        if level:
            logs = [log for log in logs if log['level'] == level]
            
        return logs[-limit:]
    
    def subscribe(self, callback):
        """Subscribe to new log events"""
        self.subscribers.append(callback)
        
    def unsubscribe(self, callback):
        """Unsubscribe from log events"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
    
    def clear(self):
        """Clear all logs"""
        with self.lock:
            self.logs.clear()

# Global console handler instance
console_handler = ConsoleLogHandler()

def setup_logging(app):
    """Configure logging for the Flask app"""
    # Configure console handler
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    # Get Flask app logger
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.DEBUG)
    
    # Also add to root logger for all modules
    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.INFO)
    
    # Log startup
    app.logger.info(f"CustomerSuccess application started on port {app.config.get('PORT', 5000)}")
    
    return console_handler

def log_event(level, message, **kwargs):
    """Utility function to log events with extra context"""
    logger = logging.getLogger('app')
    extra = {
        'event_data': kwargs
    }
    
    if level == 'debug':
        logger.debug(message, extra=extra)
    elif level == 'info':
        logger.info(message, extra=extra)
    elif level == 'warning':
        logger.warning(message, extra=extra)
    elif level == 'error':
        logger.error(message, extra=extra)
    else:
        logger.info(message, extra=extra)