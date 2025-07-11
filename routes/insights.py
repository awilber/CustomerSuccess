from flask import Blueprint, render_template, request, jsonify
from models import Customer, EmailThread
from services.insights_service import insights_service
from datetime import datetime

bp = Blueprint('insights', __name__, url_prefix='/insights')

@bp.route('/customer/<int:customer_id>')
def customer_insights(customer_id):
    """Main insights page for a customer"""
    customer = Customer.query.get_or_404(customer_id)
    
    # Get some common queries as suggestions
    suggestions = [
        "contract negotiations",
        "technical issues",
        "payment status",
        "project timeline",
        "feature requests",
        "meeting notes"
    ]
    
    return render_template('insights/customer.html',
                         customer=customer,
                         suggestions=suggestions)

@bp.route('/api/query/<int:customer_id>', methods=['POST'])
def query_insights(customer_id):
    """Process an insights query"""
    customer = Customer.query.get_or_404(customer_id)
    
    query = request.json.get('query', '').strip()
    search_mode = request.json.get('search_mode', 'strict')  # Default to strict matching
    
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    
    # Search for relevant emails with specified mode
    matching_emails = insights_service.search_context(customer_id, query, search_mode)
    
    # Generate narrative
    narrative = insights_service.generate_narrative(customer_id, query, matching_emails)
    
    # Extract key messages
    key_messages = insights_service.extract_key_messages(matching_emails, limit=20)
    
    # Get tags for matched emails
    from models import db, Tag, EmailTag
    email_ids = [msg['id'] for msg in key_messages]
    tags_data = db.session.query(
        EmailTag.email_id,
        Tag.id,
        Tag.name,
        Tag.color,
        Tag.category
    ).join(Tag).filter(EmailTag.email_id.in_(email_ids)).all() if email_ids else []
    
    # Group tags by email
    email_tags = {}
    for email_id, tag_id, tag_name, tag_color, tag_category in tags_data:
        if email_id not in email_tags:
            email_tags[email_id] = []
        email_tags[email_id].append({
            'id': tag_id,
            'name': tag_name,
            'color': tag_color,
            'category': tag_category
        })
    
    # Add tags to key messages
    for msg in key_messages:
        msg['tags'] = email_tags.get(msg['id'], [])
    
    # Format response
    response = {
        'query': query,
        'search_mode': search_mode,
        'narrative': narrative,
        'total_matches': len(matching_emails),
        'direct_matches': sum(1 for m in matching_emails if m.get('direct_match', False)),
        'key_messages': key_messages,
        'timeline': _build_timeline(key_messages)
    }
    
    return jsonify(response)

def _build_timeline(messages):
    """Build timeline data for visualization"""
    timeline = []
    
    for msg in messages:
        timeline.append({
            'date': msg['date'].isoformat(),
            'sender': msg['sender'],
            'sender_side': msg['sender_side'],
            'subject': msg['subject'],
            'excerpt': msg['excerpt'],
            'id': msg['id']
        })
    
    return timeline

@bp.route('/api/suggestions/<int:customer_id>')
def get_suggestions(customer_id):
    """Get query suggestions based on email content"""
    # Get recent emails
    recent_emails = EmailThread.query.filter_by(customer_id=customer_id)\
                                   .order_by(EmailThread.date.desc())\
                                   .limit(50).all()
    
    # Extract common topics
    topic_counts = {}
    for email in recent_emails:
        text = (email.subject + ' ' + (email.body_preview or '')).lower()
        
        # Check for topic keywords
        for topic, keywords in insights_service.topic_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    topic_counts[topic] = topic_counts.get(topic, 0) + 1
    
    # Generate suggestions based on top topics
    suggestions = []
    for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
        if topic == 'technical':
            suggestions.append("technical issues and bugs")
        elif topic == 'contract':
            suggestions.append("contract status")
        elif topic == 'feature':
            suggestions.append("feature requests")
        elif topic == 'meeting':
            suggestions.append("recent meetings")
        elif topic == 'delivery':
            suggestions.append("project timeline")
        elif topic == 'payment':
            suggestions.append("payment and invoicing")
    
    return jsonify(suggestions)