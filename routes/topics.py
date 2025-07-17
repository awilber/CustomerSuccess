from flask import Blueprint, request, jsonify, render_template
from services.topic_service import get_topic_service
from services.topic_classifier import get_topic_classifier
from models import db, Customer, Topic, EmailTopic, EmailThread
import logging

bp = Blueprint('topics', __name__, url_prefix='/topics')
logger = logging.getLogger(__name__)

@bp.route('/customer/<int:customer_id>')
def customer_topics(customer_id):
    """Main topic management interface for a customer"""
    customer = Customer.query.get_or_404(customer_id)
    return render_template('topics/customer.html', customer=customer)

# API Endpoints

@bp.route('/api/customer/<int:customer_id>/hierarchy')
def get_customer_hierarchy(customer_id):
    """Get the complete topic hierarchy for a customer"""
    try:
        service = get_topic_service()
        hierarchy = service.get_topic_hierarchy(customer_id=customer_id)
        return jsonify(hierarchy)
    except Exception as e:
        logger.error(f"Error getting hierarchy for customer {customer_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/customer/<int:customer_id>/topics')
def get_customer_topics(customer_id):
    """Get topics for a customer with statistics"""
    try:
        service = get_topic_service()
        
        # Get topics by level
        main_topics = service.get_topics_by_level(level=0, customer_id=customer_id)
        sub_topics = service.get_topics_by_level(level=1, customer_id=customer_id)
        micro_topics = service.get_topics_by_level(level=2, customer_id=customer_id)
        
        return jsonify({
            'main_topics': [topic.to_dict() for topic in main_topics],
            'sub_topics': [topic.to_dict() for topic in sub_topics],
            'micro_topics': [topic.to_dict() for topic in micro_topics],
            'total_topics': len(main_topics) + len(sub_topics) + len(micro_topics)
        })
    except Exception as e:
        logger.error(f"Error getting topics for customer {customer_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/topic/<int:topic_id>')
def get_topic_details(topic_id):
    """Get detailed information about a specific topic"""
    try:
        service = get_topic_service()
        topic = Topic.query.get_or_404(topic_id)
        
        # Get topic emails
        emails = service.get_topic_emails(topic_id, limit=20)
        
        # Get similar topics
        similar_topics = service.get_similar_topics(topic_id, threshold=0.3)
        
        return jsonify({
            'topic': topic.to_dict(),
            'emails': emails,
            'similar_topics': similar_topics
        })
    except Exception as e:
        logger.error(f"Error getting topic details for {topic_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/customer/<int:customer_id>/create', methods=['POST'])
def create_topic(customer_id):
    """Create a new topic for a customer"""
    try:
        data = request.get_json()
        service = get_topic_service()
        
        topic = service.create_topic(
            name=data['name'],
            description=data.get('description'),
            parent_id=data.get('parent_id'),
            level=data.get('level'),
            color=data.get('color'),
            created_by=data.get('created_by', 'user'),
            keywords=data.get('keywords', [])
        )
        
        # Associate topic with customer
        from models import customer_topic
        db.session.execute(
            customer_topic.insert().values(
                customer_id=customer_id,
                topic_id=topic.id
            )
        )
        db.session.commit()
        
        return jsonify({
            'topic': topic.to_dict(),
            'message': 'Topic created successfully'
        })
    except Exception as e:
        logger.error(f"Error creating topic: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/topic/create', methods=['POST'])
def create_topic_legacy():
    """Create a new topic (legacy endpoint)"""
    try:
        data = request.get_json()
        service = get_topic_service()
        
        topic = service.create_topic(
            name=data['name'],
            description=data.get('description'),
            parent_id=data.get('parent_id'),
            level=data.get('level'),
            color=data.get('color'),
            created_by=data.get('created_by', 'user'),
            keywords=data.get('keywords', [])
        )
        
        return jsonify({
            'topic': topic.to_dict(),
            'message': 'Topic created successfully'
        })
    except Exception as e:
        logger.error(f"Error creating topic: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/topic/<int:topic_id>/update', methods=['POST'])
def update_topic(topic_id):
    """Update a topic"""
    try:
        data = request.get_json()
        topic = Topic.query.get_or_404(topic_id)
        
        # Update fields
        if 'name' in data:
            topic.name = data['name']
        if 'description' in data:
            topic.description = data['description']
        if 'color' in data:
            topic.color = data['color']
        if 'is_active' in data:
            topic.is_active = data['is_active']
        
        topic.updated_at = db.func.current_timestamp()
        db.session.commit()
        
        return jsonify({
            'topic': topic.to_dict(),
            'message': 'Topic updated successfully'
        })
    except Exception as e:
        logger.error(f"Error updating topic {topic_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/topic/<int:topic_id>/delete', methods=['POST'])
def delete_topic(topic_id):
    """Delete a topic"""
    try:
        data = request.get_json()
        force = data.get('force', False)
        
        service = get_topic_service()
        success = service.delete_topic(topic_id, force=force)
        
        if success:
            return jsonify({'message': 'Topic deleted successfully'})
        else:
            return jsonify({'error': 'Topic not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting topic {topic_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/topic/<int:source_id>/merge/<int:target_id>', methods=['POST'])
def merge_topics(source_id, target_id):
    """Merge two topics"""
    try:
        data = request.get_json()
        merged_by = data.get('merged_by', 'user')
        
        service = get_topic_service()
        success = service.merge_topics(source_id, target_id, merged_by)
        
        if success:
            return jsonify({'message': 'Topics merged successfully'})
        else:
            return jsonify({'error': 'Could not merge topics'}), 400
    except Exception as e:
        logger.error(f"Error merging topics {source_id} -> {target_id}: {e}")
        return jsonify({'error': str(e)}), 500

# Classification endpoints

@bp.route('/api/customer/<int:customer_id>/classify', methods=['POST'])
def auto_classify_emails(customer_id):
    """Automatically classify emails for a customer"""
    try:
        data = request.get_json()
        limit = data.get('limit', 50)
        force_reclassify = data.get('force_reclassify', False)
        
        classifier = get_topic_classifier()
        results = classifier.auto_classify_emails(
            customer_id=customer_id,
            limit=limit,
            force_reclassify=force_reclassify
        )
        
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error auto-classifying emails for customer {customer_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/customer/<int:customer_id>/auto-classify', methods=['POST'])
def auto_classify_emails_alias(customer_id):
    """Automatically classify emails for a customer (alias endpoint)"""
    try:
        data = request.get_json() or {}
        limit = data.get('limit', 50)
        force_reclassify = data.get('force_reclassify', False)
        algorithms = data.get('algorithms', ['keyword', 'embedding', 'context', 'frequency'])
        
        classifier = get_topic_classifier()
        results = classifier.auto_classify_emails(
            customer_id=customer_id,
            limit=limit,
            force_reclassify=force_reclassify,
            algorithms=algorithms
        )
        
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error auto-classifying emails for customer {customer_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/email/<int:email_id>/classify', methods=['POST'])
def classify_single_email(email_id):
    """Classify a single email"""
    try:
        data = request.get_json()
        methods = data.get('methods', ['keyword', 'embedding', 'context', 'frequency'])
        
        classifier = get_topic_classifier()
        result = classifier.classify_email(email_id, methods=methods)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error classifying email {email_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/email/<int:email_id>/assign-topic', methods=['POST'])
def assign_topic_to_email(email_id):
    """Manually assign a topic to an email"""
    try:
        data = request.get_json()
        topic_id = data['topic_id']
        confidence_score = data.get('confidence_score', 1.0)
        assigned_by = data.get('assigned_by', 'user')
        
        service = get_topic_service()
        assignment = service.assign_topic_to_email(
            email_id=email_id,
            topic_id=topic_id,
            confidence_score=confidence_score,
            classification_method='manual',
            assigned_by=assigned_by
        )
        
        return jsonify({
            'assignment': assignment.to_dict(),
            'message': 'Topic assigned successfully'
        })
    except Exception as e:
        logger.error(f"Error assigning topic to email {email_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/email/<int:email_id>/remove-topic', methods=['POST'])
def remove_topic_from_email(email_id):
    """Remove a topic assignment from an email"""
    try:
        data = request.get_json()
        topic_id = data['topic_id']
        
        service = get_topic_service()
        success = service.remove_topic_from_email(email_id, topic_id)
        
        if success:
            return jsonify({'message': 'Topic removed successfully'})
        else:
            return jsonify({'error': 'Topic assignment not found'}), 404
    except Exception as e:
        logger.error(f"Error removing topic from email {email_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/email/<int:email_id>/verify-topic', methods=['POST'])
def verify_topic_assignment(email_id):
    """Verify a topic assignment"""
    try:
        data = request.get_json()
        topic_id = data['topic_id']
        verified_by = data.get('verified_by', 'user')
        
        assignment = EmailTopic.query.filter_by(
            email_id=email_id,
            topic_id=topic_id
        ).first()
        
        if not assignment:
            return jsonify({'error': 'Topic assignment not found'}), 404
        
        assignment.is_verified = True
        assignment.verified_at = db.func.current_timestamp()
        assignment.verified_by = verified_by
        
        db.session.commit()
        
        return jsonify({
            'assignment': assignment.to_dict(),
            'message': 'Topic assignment verified'
        })
    except Exception as e:
        logger.error(f"Error verifying topic assignment: {e}")
        return jsonify({'error': str(e)}), 500

# Keywords endpoints

@bp.route('/api/topic/<int:topic_id>/keywords')
def get_topic_keywords(topic_id):
    """Get keywords for a topic"""
    try:
        from models import TopicKeyword
        keywords = TopicKeyword.query.filter_by(topic_id=topic_id).all()
        
        return jsonify([{
            'id': kw.id,
            'keyword': kw.keyword,
            'weight': kw.weight,
            'match_count': kw.match_count,
            'created_by': kw.created_by
        } for kw in keywords])
    except Exception as e:
        logger.error(f"Error getting keywords for topic {topic_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/topic/<int:topic_id>/keywords/add', methods=['POST'])
def add_keyword_to_topic(topic_id):
    """Add a keyword to a topic"""
    try:
        data = request.get_json()
        keyword = data['keyword']
        weight = data.get('weight', 1.0)
        created_by = data.get('created_by', 'user')
        
        service = get_topic_service()
        keyword_obj = service.add_keyword_to_topic(
            topic_id=topic_id,
            keyword=keyword,
            weight=weight,
            created_by=created_by
        )
        
        return jsonify({
            'keyword': {
                'id': keyword_obj.id,
                'keyword': keyword_obj.keyword,
                'weight': keyword_obj.weight
            },
            'message': 'Keyword added successfully'
        })
    except Exception as e:
        logger.error(f"Error adding keyword to topic {topic_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/topic/<int:topic_id>/keywords/remove', methods=['POST'])
def remove_keyword_from_topic(topic_id):
    """Remove a keyword from a topic"""
    try:
        data = request.get_json()
        keyword = data['keyword']
        
        service = get_topic_service()
        success = service.remove_keyword_from_topic(topic_id, keyword)
        
        if success:
            return jsonify({'message': 'Keyword removed successfully'})
        else:
            return jsonify({'error': 'Keyword not found'}), 404
    except Exception as e:
        logger.error(f"Error removing keyword from topic {topic_id}: {e}")
        return jsonify({'error': str(e)}), 500

# Analytics endpoints

@bp.route('/api/customer/<int:customer_id>/analytics')
def get_classification_analytics(customer_id):
    """Get classification analytics for a customer"""
    try:
        classifier = get_topic_classifier()
        analytics = classifier.get_classification_analytics(customer_id=customer_id)
        
        return jsonify(analytics)
    except Exception as e:
        logger.error(f"Error getting analytics for customer {customer_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/customer/<int:customer_id>/suggestions')
def get_topic_suggestions(customer_id):
    """Get topic suggestions for unclassified emails"""
    try:
        data = request.args
        min_cluster_size = int(data.get('min_cluster_size', 3))
        
        classifier = get_topic_classifier()
        suggestions = classifier.suggest_new_topics(
            customer_id=customer_id,
            min_cluster_size=min_cluster_size
        )
        
        return jsonify({
            'suggestions': suggestions,
            'count': len(suggestions)
        })
    except Exception as e:
        logger.error(f"Error getting suggestions for customer {customer_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/customer/<int:customer_id>/statistics')
def get_customer_statistics(customer_id):
    """Get topic statistics for a customer"""
    try:
        from models import EmailThread
        
        # Get email counts
        total_emails = EmailThread.query.filter_by(customer_id=customer_id).count()
        
        # Get classification stats
        classified_emails = db.session.query(
            EmailThread.id
        ).join(EmailTopic).filter(
            EmailThread.customer_id == customer_id
        ).distinct().count()
        
        # Get topic counts
        service = get_topic_service()
        main_topics = service.get_topics_by_level(level=0, customer_id=customer_id)
        sub_topics = service.get_topics_by_level(level=1, customer_id=customer_id)
        micro_topics = service.get_topics_by_level(level=2, customer_id=customer_id)
        
        return jsonify({
            'total_emails': total_emails,
            'classified_emails': classified_emails,
            'unclassified_emails': total_emails - classified_emails,
            'classification_rate': classified_emails / total_emails if total_emails > 0 else 0,
            'topic_counts': {
                'main_topics': len(main_topics),
                'sub_topics': len(sub_topics),
                'micro_topics': len(micro_topics),
                'total_topics': len(main_topics) + len(sub_topics) + len(micro_topics)
            }
        })
    except Exception as e:
        logger.error(f"Error getting statistics for customer {customer_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/customer/<int:customer_id>/stats')
def get_customer_stats(customer_id):
    """Get topic statistics for a customer (alias for statistics endpoint)"""
    try:
        from models import EmailThread
        
        # Get email counts
        total_emails = EmailThread.query.filter_by(customer_id=customer_id).count()
        
        # Get classification stats
        classified_emails = db.session.query(
            EmailThread.id
        ).join(EmailTopic).filter(
            EmailThread.customer_id == customer_id
        ).distinct().count()
        
        # Get average confidence score
        avg_confidence = db.session.query(
            db.func.avg(EmailTopic.confidence_score)
        ).join(EmailThread).filter(
            EmailThread.customer_id == customer_id
        ).scalar() or 0
        
        # Get auto-classified count
        auto_classified = db.session.query(
            EmailThread.id
        ).join(EmailTopic).filter(
            EmailThread.customer_id == customer_id,
            EmailTopic.classification_method != 'manual'
        ).distinct().count()
        
        # Get topic counts
        service = get_topic_service()
        main_topics = service.get_topics_by_level(level=0, customer_id=customer_id)
        sub_topics = service.get_topics_by_level(level=1, customer_id=customer_id)
        micro_topics = service.get_topics_by_level(level=2, customer_id=customer_id)
        
        return jsonify({
            'total_topics': len(main_topics) + len(sub_topics) + len(micro_topics),
            'classified_emails': classified_emails,
            'avg_confidence': round(avg_confidence * 100, 1) if avg_confidence else 0,
            'auto_classified': auto_classified,
            'classification_rate': round((classified_emails / total_emails * 100), 1) if total_emails > 0 else 0,
            'total_emails': total_emails,
            'unclassified_emails': total_emails - classified_emails
        })
    except Exception as e:
        logger.error(f"Error getting stats for customer {customer_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/topic/<int:topic_id>/emails')
def get_topic_emails_endpoint(topic_id):
    """Get emails assigned to a topic"""
    try:
        service = get_topic_service()
        limit = request.args.get('limit', 20, type=int)
        
        emails = service.get_topic_emails(topic_id, limit=limit)
        
        return jsonify(emails)
    except Exception as e:
        logger.error(f"Error getting emails for topic {topic_id}: {e}")
        return jsonify({'error': str(e)}), 500