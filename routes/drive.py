from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from services.drive_service import get_drive_service
from models import db, Customer, FileReference
import os

bp = Blueprint('drive', __name__, url_prefix='/drive')

@bp.route('/setup')
def setup():
    """Setup page for Google Drive integration"""
    # Check if credentials file exists
    creds_exists = os.path.exists('credentials.json')
    token_exists = os.path.exists('token.pickle')
    
    return render_template('drive/setup.html', 
                         creds_exists=creds_exists,
                         token_exists=token_exists)

@bp.route('/authenticate')
def authenticate():
    """Initiate Google Drive authentication"""
    try:
        drive = get_drive_service()
        if drive.authenticate():
            flash('Successfully authenticated with Google Drive!', 'success')
            
            # Redirect to next step if came from customer page
            customer_id = request.args.get('customer_id')
            if customer_id:
                return redirect(url_for('drive.browse', customer_id=customer_id))
            
            return redirect(url_for('drive.setup'))
    except FileNotFoundError as e:
        flash(str(e), 'error')
        return redirect(url_for('drive.setup'))
    except Exception as e:
        flash(f'Authentication failed: {str(e)}', 'error')
        return redirect(url_for('drive.setup'))

@bp.route('/browse/<int:customer_id>')
def browse(customer_id):
    """Browse Google Drive for a specific customer"""
    customer = Customer.query.get_or_404(customer_id)
    
    # Ensure authenticated
    drive = get_drive_service()
    if not drive.creds or not drive.creds.valid:
        flash('Please authenticate with Google Drive first', 'warning')
        return redirect(url_for('drive.authenticate', customer_id=customer_id))
    
    # Get shared drives
    shared_drives = drive.list_shared_drives()
    
    # Get current location from query params
    drive_id = request.args.get('drive_id')
    folder_id = request.args.get('folder_id')
    
    files = []
    current_location = {'type': 'root', 'name': 'Shared Drives'}
    
    if drive_id:
        # Find drive name
        drive_name = next((d['name'] for d in shared_drives if d['id'] == drive_id), 'Unknown Drive')
        current_location = {'type': 'drive', 'id': drive_id, 'name': drive_name}
        
        # List files in the drive or folder
        files = drive.list_files_in_drive(drive_id, folder_id)
        
        if folder_id:
            # Get folder metadata to show in breadcrumb
            folder_meta = drive.get_file_metadata(folder_id)
            if folder_meta:
                current_location = {
                    'type': 'folder', 
                    'id': folder_id, 
                    'name': folder_meta['name'],
                    'drive_id': drive_id,
                    'drive_name': drive_name
                }
    
    return render_template('drive/browse.html',
                         customer=customer,
                         shared_drives=shared_drives,
                         files=files,
                         current_location=current_location,
                         drive_id=drive_id,
                         folder_id=folder_id)

@bp.route('/link-file/<int:customer_id>', methods=['POST'])
def link_file(customer_id):
    """Link a Google Drive file to a customer"""
    customer = Customer.query.get_or_404(customer_id)
    
    file_id = request.form.get('file_id')
    if not file_id:
        flash('No file selected', 'error')
        return redirect(request.referrer or url_for('customers.detail', id=customer_id))
    
    drive = get_drive_service()
    file_meta = drive.get_file_metadata(file_id)
    
    if file_meta:
        file_ref = drive.save_file_reference(file_meta, customer_id)
        flash(f'Linked file: {file_meta["name"]}', 'success')
    else:
        flash('Could not retrieve file information', 'error')
    
    return redirect(request.referrer or url_for('customers.detail', id=customer_id))

@bp.route('/unlink-file/<int:file_ref_id>', methods=['POST'])
def unlink_file(file_ref_id):
    """Remove a file reference"""
    file_ref = FileReference.query.get_or_404(file_ref_id)
    customer_id = file_ref.customer_id
    
    db.session.delete(file_ref)
    db.session.commit()
    
    flash(f'Unlinked file: {file_ref.file_name}', 'success')
    return redirect(url_for('customers.detail', id=customer_id))

@bp.route('/api/search')
def search():
    """Search for files in Google Drive"""
    query = request.args.get('q', '')
    drive_id = request.args.get('drive_id')
    
    if not query or not drive_id:
        return jsonify([])
    
    drive = get_drive_service()
    files = drive.list_files_in_drive(drive_id, query=query)
    
    return jsonify(files)