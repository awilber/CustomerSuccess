import os
import json
import logging
from datetime import datetime
from flask import request, session
from threading import Lock
import requests
from functools import wraps

class ActivityLogger:
    def __init__(self, app=None, log_directory='logs'):
        self.app = app
        self.log_directory = log_directory
        self.lock = Lock()
        self.setup_directories()
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        self.app = app
        
        # Set up before and after request handlers
        app.before_request(self.log_request)
        app.after_request(self.log_response)
    
    def setup_directories(self):
        """Create logs directory if it doesn't exist"""
        os.makedirs(self.log_directory, exist_ok=True)
        
        # Create daily log file
        today = datetime.now().strftime('%Y-%m-%d')
        self.daily_log_file = os.path.join(self.log_directory, f'activity_{today}.json')
    
    def get_client_ip(self):
        """Get the real client IP address"""
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        elif request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        else:
            return request.remote_addr
    
    def get_geolocation(self, ip_address):
        """Get geolocation for IP address using ipapi.co"""
        if ip_address in ['127.0.0.1', 'localhost', '::1']:
            return {
                'city': 'Local',
                'region': 'Local',
                'country': 'Local',
                'country_code': 'LC'
            }
        
        try:
            # Free tier of ipapi.co
            response = requests.get(f'https://ipapi.co/{ip_address}/json/', timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    'city': data.get('city', 'Unknown'),
                    'region': data.get('region', 'Unknown'),
                    'country': data.get('country_name', 'Unknown'),
                    'country_code': data.get('country_code', 'XX')
                }
        except Exception as e:
            print(f"Geolocation lookup failed for {ip_address}: {e}")
        
        return {
            'city': 'Unknown',
            'region': 'Unknown', 
            'country': 'Unknown',
            'country_code': 'XX'
        }
    
    def log_request(self):
        """Log incoming request details"""
        if not request or request.endpoint in ['static', 'logs.stream']:
            return
        
        request.start_time = datetime.now()
        request.client_ip = self.get_client_ip()
    
    def log_response(self, response):
        """Log response details and complete activity log"""
        if not hasattr(request, 'start_time') or request.endpoint in ['static', 'logs.stream']:
            return response
        
        end_time = datetime.now()
        duration_ms = int((end_time - request.start_time).total_seconds() * 1000)
        
        # Get geolocation (cache this to avoid repeated calls)
        geolocation = self.get_geolocation(request.client_ip)
        
        log_entry = {
            'timestamp': end_time.isoformat(),
            'ip_address': request.client_ip,
            'geolocation': geolocation,
            'method': request.method,
            'endpoint': request.endpoint,
            'url': request.url,
            'user_agent': request.headers.get('User-Agent', ''),
            'status_code': response.status_code,
            'duration_ms': duration_ms,
            'authenticated': session.get('authenticated', False),
            'session_id': session.get('_id', None)
        }
        
        # Add POST data if present (but mask sensitive data)
        if request.method == 'POST' and request.form:
            form_data = dict(request.form)
            if 'password' in form_data:
                form_data['password'] = '***masked***'
            log_entry['form_data'] = form_data
        
        self.write_log_entry(log_entry)
        return response
    
    def log_action(self, action, details=None):
        """Log a specific user action with details"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'ip_address': self.get_client_ip() if request else 'system',
            'action': action,
            'details': details or {},
            'authenticated': session.get('authenticated', False) if request else False,
            'session_id': session.get('_id', None) if request else None
        }
        
        if request:
            log_entry['geolocation'] = self.get_geolocation(log_entry['ip_address'])
        
        self.write_log_entry(log_entry)
    
    def write_log_entry(self, log_entry):
        """Write log entry to file"""
        with self.lock:
            try:
                # Append to daily log file
                with open(self.daily_log_file, 'a') as f:
                    f.write(json.dumps(log_entry) + '\n')
            except Exception as e:
                print(f"Failed to write log entry: {e}")
    
    def get_recent_logs(self, limit=100):
        """Get recent log entries"""
        logs = []
        
        try:
            if os.path.exists(self.daily_log_file):
                with open(self.daily_log_file, 'r') as f:
                    lines = f.readlines()
                    
                # Get last N lines
                for line in lines[-limit:]:
                    try:
                        logs.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Failed to read logs: {e}")
        
        return logs
    
    def clear_logs(self):
        """Clear today's logs"""
        try:
            if os.path.exists(self.daily_log_file):
                open(self.daily_log_file, 'w').close()
            return True
        except Exception as e:
            print(f"Failed to clear logs: {e}")
            return False

def log_action(action, details=None):
    """Decorator to log specific actions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            result = f(*args, **kwargs)
            # Log after successful execution
            if hasattr(f, '__self__') and hasattr(f.__self__, 'logger'):
                f.__self__.logger.log_action(action, details)
            return result
        return decorated_function
    return decorator