from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db, Customer, DirectoryLink, FileReference, FileEmailCorrelation, EmailThread
from services.directory_scanner import directory_scanner
from services.background_tasks import background_processor
from services.correlation_engine import correlation_engine
from services.drive_service import get_drive_service
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
                background_processor.add_task(
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
    
    if not drive_id:
        flash('No drive selected', 'error')
        return redirect(url_for('directories.customer_directories', customer_id=customer_id))
    
    # Check if already linked
    existing = DirectoryLink.query.filter_by(
        customer_id=customer_id,
        link_type='drive',
        drive_id=drive_id,
        folder_id=folder_id
    ).first()
    
    if existing:
        flash('Drive directory already linked', 'warning')
    else:
        # Create directory link for Google Drive
        dir_link = DirectoryLink(
            customer_id=customer_id,
            link_type='drive',
            drive_id=drive_id,
            folder_id=folder_id,
            name=folder_name,
            path=None  # No local path for Drive directories
        )
        db.session.add(dir_link)
        db.session.commit()
        
        # Queue background scan for Drive files
        background_processor.add_task(
            'scan_drive_directory',
            drive_id=drive_id,
            folder_id=folder_id,
            customer_id=customer_id,
            directory_link_id=dir_link.id
        )
        
        flash(f'Google Drive directory "{folder_name}" linked successfully. Scanning files in background.', 'success')
    
    return redirect(url_for('directories.customer_directories', customer_id=customer_id))

@bp.route('/scan/<int:directory_id>', methods=['POST'])
def rescan_directory(directory_id):
    """Rescan a directory"""
    dir_link = DirectoryLink.query.get_or_404(directory_id)
    
    # Queue background scan based on type
    if dir_link.link_type == 'drive':
        background_processor.add_task(
            'scan_drive_directory',
            drive_id=dir_link.drive_id,
            folder_id=dir_link.folder_id,
            customer_id=dir_link.customer_id,
            directory_link_id=dir_link.id
        )
    else:
        background_processor.add_task(
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
    background_processor.add_task(
        'recalculate_importance',
        customer_id=customer_id
    )
    
    flash('Importance scores recalculation started', 'success')
    return redirect(request.referrer or url_for('directories.file_analysis', customer_id=customer_id))