from flask import Blueprint, render_template, request, jsonify
from models import db, Customer, EmailThread, Person
from sqlalchemy import func, extract
from datetime import datetime, timedelta
import json

bp = Blueprint('analytics', __name__, url_prefix='/analytics')

@bp.route('/customer/<int:customer_id>')
def customer_analytics(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    
    # Email volume by month
    monthly_emails = db.session.query(
        extract('year', EmailThread.date).label('year'),
        extract('month', EmailThread.date).label('month'),
        func.count(EmailThread.id).label('count')
    ).filter(
        EmailThread.customer_id == customer_id
    ).group_by('year', 'month').all()
    
    # Email volume by sender
    sender_stats = db.session.query(
        EmailThread.sender_name,
        func.count(EmailThread.id).label('count')
    ).filter(
        EmailThread.customer_id == customer_id
    ).group_by(EmailThread.sender_name).all()
    
    # Recent activity summary
    recent_cutoff = datetime.utcnow() - timedelta(days=30)
    recent_emails = EmailThread.query.filter(
        EmailThread.customer_id == customer_id,
        EmailThread.date >= recent_cutoff
    ).count()
    
    return render_template('analytics/customer.html',
                         customer=customer,
                         monthly_emails=monthly_emails,
                         sender_stats=sender_stats,
                         recent_emails=recent_emails)

@bp.route('/api/timeline/<int:customer_id>')
def timeline_data(customer_id):
    # Get filter parameters
    person_filter = request.args.get('person')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Build query
    query = EmailThread.query.filter(EmailThread.customer_id == customer_id)
    
    if person_filter:
        query = query.filter(
            (EmailThread.sender_name == person_filter) | 
            (EmailThread.recipient_name == person_filter)
        )
    
    if start_date:
        query = query.filter(EmailThread.date >= datetime.fromisoformat(start_date))
    
    if end_date:
        query = query.filter(EmailThread.date <= datetime.fromisoformat(end_date))
    
    emails = query.order_by(EmailThread.date).all()
    
    if not emails:
        return jsonify({
            'time_bins': [],
            'customer_volume': {},
            'us_individuals': {}
        })
    
    # Determine time range and appropriate binning
    min_date = min(email.date for email in emails)
    max_date = max(email.date for email in emails)
    date_range = (max_date - min_date).days
    
    # Choose appropriate time granularity for ~100 divisions
    if date_range <= 100:  # Less than 100 days: use days
        bin_type = 'day'
        bin_format = '%Y-%m-%d'
    elif date_range <= 700:  # Less than 100 weeks: use weeks
        bin_type = 'week'
        bin_format = '%Y-W%U'
    elif date_range <= 3000:  # Less than 100 months: use months
        bin_type = 'month'
        bin_format = '%Y-%m'
    else:  # Use quarters
        bin_type = 'quarter'
        bin_format = '%Y-Q'
    
    # Group emails by time bin and sender
    volume_data = {}
    individual_emails = []
    
    for email in emails:
        # Determine time bin
        if bin_type == 'day':
            time_bin = email.date.strftime('%Y-%m-%d')
        elif bin_type == 'week':
            time_bin = email.date.strftime('%Y-W%U')
        elif bin_type == 'month':
            time_bin = email.date.strftime('%Y-%m')
        else:  # quarter
            quarter = (email.date.month - 1) // 3 + 1
            time_bin = f"{email.date.year}-Q{quarter}"
        
        # Initialize bin if needed
        if time_bin not in volume_data:
            volume_data[time_bin] = {
                'customer': {},
                'us': {},
                'total_customer': 0,
                'total_us': 0
            }
        
        # Count volume by sender
        if email.sender_side == 'customer':
            sender_key = email.sender_name
            if sender_key not in volume_data[time_bin]['customer']:
                volume_data[time_bin]['customer'][sender_key] = 0
            volume_data[time_bin]['customer'][sender_key] += 1
            volume_data[time_bin]['total_customer'] += 1
        else:  # us
            sender_key = email.sender_name
            if sender_key not in volume_data[time_bin]['us']:
                volume_data[time_bin]['us'][sender_key] = 0
            volume_data[time_bin]['us'][sender_key] += 1
            volume_data[time_bin]['total_us'] += 1
            
            # Store individual email for scatter points
            individual_emails.append({
                'date': email.date.isoformat(),
                'sender': email.sender_name,
                'subject': email.subject,
                'preview': email.body_preview[:100] + '...' if len(email.body_preview) > 100 else email.body_preview,
                'time_bin': time_bin
            })
    
    # Get unique senders for consistent colors
    customer_senders = sorted(set(
        sender for bin_data in volume_data.values() 
        for sender in bin_data['customer'].keys()
    ))
    us_senders = sorted(set(
        sender for bin_data in volume_data.values() 
        for sender in bin_data['us'].keys()
    ))
    
    return jsonify({
        'time_bins': sorted(volume_data.keys()),
        'bin_type': bin_type,
        'volume_data': volume_data,
        'customer_senders': customer_senders,
        'us_senders': us_senders,
        'individual_emails': individual_emails
    })

@bp.route('/search')
def search():
    query = request.args.get('q', '')
    customer_id = request.args.get('customer_id')
    
    if not query:
        return jsonify([])
    
    # Search in email subjects and bodies
    email_query = EmailThread.query.filter(
        (EmailThread.subject.contains(query)) | 
        (EmailThread.body_preview.contains(query))
    )
    
    if customer_id:
        email_query = email_query.filter(EmailThread.customer_id == customer_id)
    
    results = email_query.limit(20).all()
    
    return jsonify([{
        'id': email.id,
        'type': 'email',
        'title': email.subject,
        'date': email.date.isoformat(),
        'preview': email.body_preview[:200],
        'customer_id': email.customer_id
    } for email in results])