from flask import Blueprint, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from models import db, EmailThread
from services.email_parser import parse_google_takeout
import os
import zipfile

bp = Blueprint('uploads', __name__, url_prefix='/uploads')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@bp.route('/google-takeout/<int:customer_id>', methods=['POST'])
def google_takeout(customer_id):
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('customers.detail', id=customer_id))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('customers.detail', id=customer_id))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], 'google_takeout', filename)
        file.save(filepath)
        
        try:
            file_extension = filename.rsplit('.', 1)[1].lower()
            
            if file_extension == 'zip':
                # Extract and parse the zip file
                extract_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'google_takeout', f'extract_{customer_id}')
                os.makedirs(extract_path, exist_ok=True)
                
                with zipfile.ZipFile(filepath, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                
                # Parse emails from the extracted files
                email_count = parse_google_takeout(extract_path, customer_id)
                
            elif file_extension == 'mbox':
                # Parse MBOX file directly
                from services.email_parser import parse_mbox_file
                email_count = parse_mbox_file(filepath, customer_id)
            
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")
            
            flash(f'Successfully imported {email_count} emails from Google Takeout', 'success')
            
        except Exception as e:
            flash(f'Error processing file: {str(e)}', 'error')
            
        finally:
            # Clean up uploaded file
            if os.path.exists(filepath):
                os.remove(filepath)
        
        return redirect(url_for('customers.detail', id=customer_id))
    
    flash('Invalid file type. Please upload a ZIP or MBOX file.', 'error')
    return redirect(url_for('customers.detail', id=customer_id))