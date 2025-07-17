from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db, Customer, DirectoryLink, FileReference, FileEmailCorrelation, EmailThread
from services.directory_scanner import directory_scanner
from services.background_tasks import get_background_processor
from services.correlation_engine import correlation_engine
from services.drive_service import get_drive_service
from services.directory_logging import directory_logger
import os
import json

bp = Blueprint('directories', __name__, url_prefix='/directories')

@bp.route('/customer/<int:customer_id>')
def customer_directories(customer_id):
    """List and manage directories for a customer"""
    customer = Customer.query.get_or_404(customer_id)
    directories = DirectoryLink.query.filter_by(customer_id=customer_id).all()
    
    return render_template('directories/list.html',
                         customer=customer,
                         directories=directories)

@bp.route('/link/<int:customer_id>', methods=['GET', 'POST'])
def link_directory(customer_id):
    """Link a new directory"""
    customer = Customer.query.get_or_404(customer_id)
    
    if request.method == 'POST':
        directory_path = request.form.get('directory_path', '').strip()
        
        # Expand user home directory
        if directory_path.startswith('~'):
            directory_path = os.path.expanduser(directory_path)
        
        # Validate directory
        stats = directory_scanner.get_directory_stats(directory_path)
        
        if not stats['exists']:
            flash('Directory not found', 'error')
        elif not stats['is_directory']:
            flash('Path is not a directory', 'error')
        elif not stats['readable']:
            flash('Directory is not readable', 'error')
        else:
            # Check if already linked
            existing = DirectoryLink.query.filter_by(
                customer_id=customer_id,
                path=directory_path
            ).first()
            
            if existing:
                flash('Directory already linked', 'warning')
            else:
                # Create directory link
                dir_link = DirectoryLink(
                    customer_id=customer_id,
                    path=directory_path,
                    name=os.path.basename(directory_path) or 'Root Directory'
                )
                db.session.add(dir_link)
                db.session.commit()
                
                # Queue background scan
                processor = get_background_processor()
                if processor:
                    processor.add_task(
                        'scan_directory',
                        directory_path=directory_path,
                        customer_id=customer_id,
                        directory_link_id=dir_link.id
                    )
                
                flash(f'Directory linked successfully. Scanning {stats["file_count"]} files in background.', 'success')
                return redirect(url_for('directories.customer_directories', customer_id=customer_id))
    
    return render_template('directories/link.html', customer=customer)

@bp.route('/link-drive/<int:customer_id>', methods=['POST'])
def link_drive_directory(customer_id):
    """Link a Google Drive directory to a customer"""
    customer = Customer.query.get_or_404(customer_id)
    
    drive_id = request.form.get('drive_id')
    folder_id = request.form.get('folder_id')
    folder_name = request.form.get('folder_name', 'Untitled Drive Folder')
    
    # Log the start of directory linking
    directory_logger.log_directory_link_start(
        customer_id=customer_id,
        directory_type='google_drive',
        drive_id=drive_id,
        folder_id=folder_id,
        folder_name=folder_name
    )
    
    if not drive_id:
        error_msg = 'No drive selected'
        directory_logger.log_directory_link_error(
            customer_id=customer_id,
            directory_type='google_drive',
            error=error_msg,
            details={"drive_id": drive_id, "folder_id": folder_id}
        )
        flash(error_msg, 'error')
        return redirect(url_for('directories.customer_directories', customer_id=customer_id))
    
    try:
        # Check if already linked
        existing = DirectoryLink.query.filter_by(
            customer_id=customer_id,
            link_type='drive',
            drive_id=drive_id,
            folder_id=folder_id
        ).first()
        
        if existing:
            warning_msg = 'Drive directory already linked'
            directory_logger.log_directory_link_error(
                customer_id=customer_id,
                directory_type='google_drive',
                error=warning_msg,
                details={"existing_link_id": existing.id}
            )
            flash(warning_msg, 'warning')
        else:
            # Create directory link for Google Drive
            dir_link = DirectoryLink(
                customer_id=customer_id,
                link_type='drive',
                drive_id=drive_id,
                folder_id=folder_id,
                name=folder_name,
                path=None,  # No local path for Drive directories
                scan_status='pending'
            )
            db.session.add(dir_link)
            db.session.commit()
            
            # Log successful directory linking
            directory_logger.log_directory_link_success(
                customer_id=customer_id,
                directory_link_id=dir_link.id,
                directory_type='google_drive',
                details={
                    "drive_id": drive_id,
                    "folder_id": folder_id,
                    "folder_name": folder_name,
                    "directory_link_id": dir_link.id
                }
            )
            
            # Queue background scan for Drive files
            processor = get_background_processor()
            if processor:
                processor.add_task(
                    'scan_drive_directory',
                    drive_id=drive_id,
                    folder_id=folder_id,
                    customer_id=customer_id,
                    directory_link_id=dir_link.id
                )
            
            flash(f'Google Drive directory "{folder_name}" linked successfully. Scanning files in background.', 'success')
        
    except Exception as e:
        error_msg = f'Error linking Google Drive directory: {str(e)}'
        directory_logger.log_directory_link_error(
            customer_id=customer_id,
            directory_type='google_drive',
            error=error_msg,
            details={"drive_id": drive_id, "folder_id": folder_id, "exception": str(e)}
        )
        flash(error_msg, 'error')
        db.session.rollback()
    
    return redirect(url_for('directories.customer_directories', customer_id=customer_id))

@bp.route('/scan/<int:directory_id>', methods=['POST'])
def rescan_directory(directory_id):
    """Rescan a directory"""
    dir_link = DirectoryLink.query.get_or_404(directory_id)
    
    # Queue background scan based on type
    processor = get_background_processor()
    if processor:
        if dir_link.link_type == 'drive':
            processor.add_task(
                'scan_drive_directory',
                drive_id=dir_link.drive_id,
                folder_id=dir_link.folder_id,
                customer_id=dir_link.customer_id,
                directory_link_id=dir_link.id
            )
        else:
            processor.add_task(
                'scan_directory',
                directory_path=dir_link.path,
                customer_id=dir_link.customer_id,
                directory_link_id=dir_link.id
            )
    
    flash('Directory scan started in background', 'success')
    return redirect(url_for('directories.customer_directories', customer_id=dir_link.customer_id))

@bp.route('/unlink/<int:directory_id>', methods=['POST'])
def unlink_directory(directory_id):
    """Unlink a directory"""
    dir_link = DirectoryLink.query.get_or_404(directory_id)
    customer_id = dir_link.customer_id
    
    # Remove directory link (files remain for historical reference)
    db.session.delete(dir_link)
    db.session.commit()
    
    flash('Directory unlinked', 'success')
    return redirect(url_for('directories.customer_directories', customer_id=customer_id))

@bp.route('/files/<int:customer_id>')
def file_analysis(customer_id):
    """File analysis and heatmap view"""
    customer = Customer.query.get_or_404(customer_id)
    
    # Get file statistics
    total_files = FileReference.query.filter_by(customer_id=customer_id).count()
    processed_files = FileReference.query.filter_by(
        customer_id=customer_id,
        processing_status='completed'
    ).count()
    
    # Get topics
    topics = db.session.query(
        FileReference.topic,
        db.func.count(FileReference.id).label('count')
    ).filter_by(
        customer_id=customer_id
    ).group_by(FileReference.topic).all()
    
    # Get email threads for filtering
    email_threads = db.session.query(
        EmailThread.subject,
        db.func.count(EmailThread.id).label('count')
    ).filter_by(
        customer_id=customer_id
    ).group_by(EmailThread.subject).order_by(
        db.func.count(EmailThread.id).desc()
    ).limit(20).all()
    
    return render_template('directories/file_analysis.html',
                         customer=customer,
                         total_files=total_files,
                         processed_files=processed_files,
                         topics=topics,
                         email_threads=email_threads)

@bp.route('/api/check-directory', methods=['POST'])
def check_directory():
    """AJAX endpoint to check directory stats"""
    directory_path = request.json.get('path', '').strip()
    
    if directory_path.startswith('~'):
        directory_path = os.path.expanduser(directory_path)
    
    stats = directory_scanner.get_directory_stats(directory_path)
    return jsonify(stats)

@bp.route('/api/heatmap/<int:customer_id>')
def heatmap_data(customer_id):
    """Get heatmap data for file importance"""
    email_filter = request.args.get('email_filter')
    
    data = correlation_engine.get_file_timeline_data(customer_id, email_filter)
    return jsonify(data)

@bp.route('/api/file-details/<int:file_id>')
def file_details(file_id):
    """Get detailed file information"""
    file_ref = FileReference.query.get_or_404(file_id)
    
    # Get correlated emails
    correlations = db.session.query(
        EmailThread.subject,
        EmailThread.date,
        EmailThread.sender_name,
        FileEmailCorrelation.correlation_score,
        FileEmailCorrelation.correlation_type
    ).join(
        FileEmailCorrelation,
        EmailThread.id == FileEmailCorrelation.email_id
    ).filter(
        FileEmailCorrelation.file_id == file_id
    ).order_by(
        FileEmailCorrelation.correlation_score.desc()
    ).limit(10).all()
    
    return jsonify({
        'file_name': file_ref.file_name,
        'summary': file_ref.summary,
        'topic': file_ref.topic,
        'keywords': json.loads(file_ref.keywords) if file_ref.keywords else [],
        'importance_score': file_ref.importance_score,
        'size': file_ref.size_bytes,
        'last_modified': file_ref.last_modified.isoformat() if file_ref.last_modified else None,
        'correlations': [
            {
                'subject': c.subject,
                'date': c.date.isoformat(),
                'sender': c.sender_name,
                'score': c.correlation_score,
                'type': c.correlation_type
            } for c in correlations
        ]
    })

@bp.route('/recalculate/<int:customer_id>', methods=['POST'])
def recalculate_importance(customer_id):
    """Trigger importance score recalculation"""
    processor = get_background_processor()
    if processor:
        processor.add_task(
            'recalculate_importance',
            customer_id=customer_id
        )
    
    flash('Importance scores recalculation started', 'success')
    return redirect(request.referrer or url_for('directories.file_analysis', customer_id=customer_id))

@bp.route('/api/scan-progress/<int:directory_link_id>')
def get_scan_progress(directory_link_id):
    """Get real-time scan progress for a directory"""
    try:
        # Get progress from directory logger
        progress = directory_logger.get_progress(f"scan_{directory_link_id}")
        
        # Get directory link info
        dir_link = DirectoryLink.query.get_or_404(directory_link_id)
        
        # Combine database status with progress tracking
        response_data = {
            'directory_link_id': directory_link_id,
            'directory_name': dir_link.name,
            'directory_type': dir_link.link_type,
            'database_status': dir_link.scan_status,
            'file_count': dir_link.file_count or 0,
            'total_size': dir_link.total_size or 0,
            'last_scanned': dir_link.last_scanned.isoformat() if dir_link.last_scanned else None,
            'progress': progress
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/scan-progress/customer/<int:customer_id>')
def get_customer_scan_progress(customer_id):
    """Get scan progress for all directories for a customer"""
    try:
        # Get all directory links for customer
        dir_links = DirectoryLink.query.filter_by(customer_id=customer_id).all()
        
        progress_data = []
        for dir_link in dir_links:
            progress = directory_logger.get_progress(f"scan_{dir_link.id}")
            
            progress_data.append({
                'directory_link_id': dir_link.id,
                'directory_name': dir_link.name,
                'directory_type': dir_link.link_type,
                'database_status': dir_link.scan_status,
                'file_count': dir_link.file_count or 0,
                'total_size': dir_link.total_size or 0,
                'last_scanned': dir_link.last_scanned.isoformat() if dir_link.last_scanned else None,
                'progress': progress
            })
        
        return jsonify({
            'customer_id': customer_id,
            'directories': progress_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500