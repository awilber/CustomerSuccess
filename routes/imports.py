from flask import Blueprint, request, redirect, url_for, flash, jsonify
from models import db
from services.email_parser import parse_mbox_file, parse_google_takeout
from services.logger import log_event
import os
import zipfile

bp = Blueprint('imports', __name__, url_prefix='/imports')

@bp.route('/local-file/<int:customer_id>', methods=['POST'])
def import_local_file(customer_id):
    """Import emails from a local file path (MBOX or ZIP)"""
    filepath = request.form.get('filepath', '').strip()
    
    if not filepath:
        flash('No file path provided', 'error')
        return redirect(url_for('customers.detail', id=customer_id))
    
    # Expand user home directory
    if filepath.startswith('~'):
        filepath = os.path.expanduser(filepath)
    
    # Check if file exists
    if not os.path.exists(filepath):
        flash(f'File not found: {filepath}', 'error')
        log_event('error', f'Import failed - file not found: {filepath}')
        return redirect(url_for('customers.detail', id=customer_id))
    
    # Check if it's a file (not directory)
    if not os.path.isfile(filepath):
        flash(f'Path is not a file: {filepath}', 'error')
        log_event('error', f'Import failed - not a file: {filepath}')
        return redirect(url_for('customers.detail', id=customer_id))
    
    try:
        file_extension = filepath.rsplit('.', 1)[-1].lower()
        log_event('info', f'Starting import from local file: {filepath} (type: {file_extension})')
        
        if file_extension == 'mbox':
            # Parse MBOX file directly
            email_count = parse_mbox_file(filepath, customer_id)
            log_event('info', f'Successfully imported {email_count} emails from MBOX file')
            
        elif file_extension == 'zip':
            # Extract and parse ZIP file
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                log_event('debug', f'Extracting ZIP to temporary directory: {temp_dir}')
                
                with zipfile.ZipFile(filepath, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                email_count = parse_google_takeout(temp_dir, customer_id)
                log_event('info', f'Successfully imported {email_count} emails from ZIP file')
        
        else:
            raise ValueError(f"Unsupported file type: {file_extension}. Please use .mbox or .zip files.")
        
        flash(f'Successfully imported {email_count} emails from {os.path.basename(filepath)}', 'success')
        
    except Exception as e:
        error_msg = f'Error processing file: {str(e)}'
        flash(error_msg, 'error')
        log_event('error', error_msg, filepath=filepath, customer_id=customer_id)
    
    return redirect(url_for('customers.detail', id=customer_id))

@bp.route('/check-file', methods=['POST'])
def check_file():
    """AJAX endpoint to check if a file exists and get its info"""
    filepath = request.json.get('filepath', '').strip()
    
    if filepath.startswith('~'):
        filepath = os.path.expanduser(filepath)
    
    if not os.path.exists(filepath):
        return jsonify({
            'exists': False,
            'message': 'File not found'
        })
    
    if not os.path.isfile(filepath):
        return jsonify({
            'exists': False,
            'message': 'Path is a directory, not a file'
        })
    
    # Get file info
    file_stats = os.stat(filepath)
    file_size_mb = file_stats.st_size / (1024 * 1024)
    
    return jsonify({
        'exists': True,
        'size_mb': round(file_size_mb, 2),
        'extension': filepath.rsplit('.', 1)[-1].lower() if '.' in filepath else 'unknown',
        'readable': os.access(filepath, os.R_OK)
    })