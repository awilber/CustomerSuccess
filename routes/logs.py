from flask import Blueprint, jsonify, request, render_template, Response
from datetime import datetime
import json
import os

bp = Blueprint('logs', __name__, url_prefix='/logs')

def get_logger():
    """Get the logger instance from the app"""
    from flask import current_app
    return getattr(current_app, 'activity_logger', None)

@bp.route('/view')
def view():
    """Display logs in a web interface"""
    logger = get_logger()
    if not logger:
        return "Logging not configured", 500
    
    logs = logger.get_recent_logs(limit=500)
    return render_template('logs/view.html', logs=logs)

@bp.route('/api/recent')
def api_recent_logs():
    """API endpoint to get recent logs"""
    logger = get_logger()
    if not logger:
        return jsonify({'error': 'Logging not configured'}), 500
    
    limit = request.args.get('limit', 100, type=int)
    logs = logger.get_recent_logs(limit=limit)
    
    return jsonify(logs)

@bp.route('/api/clear', methods=['POST'])
def api_clear_logs():
    """API endpoint to clear logs"""
    logger = get_logger()
    if not logger:
        return jsonify({'error': 'Logging not configured'}), 500
    
    success = logger.clear_logs()
    if success:
        logger.log_action('LOGS_CLEARED', {'cleared_by': 'user'})
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to clear logs'}), 500

@bp.route('/stream')
def stream_logs():
    """Server-sent events stream for real-time logs"""
    def generate():
        # Send initial connection event
        yield f"data: {json.dumps({'type': 'connected', 'timestamp': datetime.now().isoformat()})}\n\n"
        
        # This is a simple implementation - in production you'd want a proper SSE solution
        # For now, we'll just send periodic updates
        import time
        while True:
            time.sleep(5)  # Send updates every 5 seconds
            logger = get_logger()
            if logger:
                recent_logs = logger.get_recent_logs(limit=10)
                for log in recent_logs:
                    yield f"data: {json.dumps(log)}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@bp.route('/export')
def export_logs():
    """Export logs as JSON file"""
    logger = get_logger()
    if not logger:
        return "Logging not configured", 500
    
    logs = logger.get_recent_logs(limit=1000)
    
    response = Response(
        json.dumps(logs, indent=2),
        mimetype='application/json',
        headers={
            'Content-Disposition': f'attachment; filename=activity_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        }
    )
    
    logger.log_action('LOGS_EXPORTED', {'export_count': len(logs)})
    return response