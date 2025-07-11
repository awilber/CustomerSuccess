from flask import Blueprint, Response, request, jsonify
from services.logger import console_handler, log_event
import json
import time
from queue import Queue

bp = Blueprint('logs', __name__, url_prefix='/logs')

@bp.route('/stream')
def log_stream():
    """Server-Sent Events endpoint for real-time log streaming"""
    def generate():
        # Create a queue for this client
        q = Queue()
        
        def add_log(log_entry):
            q.put(log_entry)
        
        # Subscribe to new logs
        console_handler.subscribe(add_log)
        
        try:
            # Send initial logs
            recent_logs = console_handler.get_logs(limit=50)
            for log in recent_logs:
                yield f"data: {json.dumps(log)}\n\n"
            
            # Stream new logs
            while True:
                try:
                    # Wait for new log with timeout
                    log_entry = q.get(timeout=30)
                    yield f"data: {json.dumps(log_entry)}\n\n"
                except:
                    # Send heartbeat
                    yield f": heartbeat\n\n"
                    
        finally:
            console_handler.unsubscribe(add_log)
    
    return Response(generate(), mimetype='text/event-stream')

@bp.route('/history')
def log_history():
    """Get historical logs"""
    level = request.args.get('level')
    limit = int(request.args.get('limit', 100))
    
    logs = console_handler.get_logs(level=level, limit=limit)
    return jsonify(logs)

@bp.route('/clear', methods=['POST'])
def clear_logs():
    """Clear all logs"""
    console_handler.clear()
    log_event('info', 'Console logs cleared')
    return jsonify({'status': 'cleared'})

@bp.route('/test', methods=['POST'])
def test_logs():
    """Generate test log entries"""
    log_event('info', 'Test INFO message - Everything is working normally')
    log_event('warning', 'Test WARNING message - Something needs attention')
    log_event('error', 'Test ERROR message - Something went wrong')
    log_event('debug', 'Test DEBUG message - Detailed debugging information')
    
    return jsonify({'status': 'test logs generated'})