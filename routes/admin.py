from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
import os
import subprocess
import sys
import logging

bp = Blueprint('admin', __name__, url_prefix='/admin')
logger = logging.getLogger(__name__)

@bp.route('/migrate-topics')
def migrate_topics():
    """Run topic hierarchy migration"""
    try:
        # Import and run migration
        from migrations.add_topic_hierarchy import main as run_migration
        
        result = run_migration()
        
        if result == 0:
            flash('Topic hierarchy migration completed successfully!', 'success')
        else:
            flash('Topic hierarchy migration failed. Check logs for details.', 'error')
            
    except Exception as e:
        logger.error(f"Migration error: {e}")
        flash(f'Migration error: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@bp.route('/system-info')
def system_info():
    """Display system information"""
    from models import db, Customer, EmailThread, Topic, EmailTopic
    
    info = {
        'database_tables': [],
        'customer_count': 0,
        'email_count': 0,
        'topic_count': 0,
        'email_topic_assignments': 0
    }
    
    try:
        # Get table information
        inspector = db.inspect(db.engine)
        info['database_tables'] = inspector.get_table_names()
        
        # Get counts
        info['customer_count'] = Customer.query.count()
        info['email_count'] = EmailThread.query.count()
        
        # Check if topic tables exist
        if 'topic' in info['database_tables']:
            info['topic_count'] = Topic.query.count()
        
        if 'email_topic' in info['database_tables']:
            info['email_topic_assignments'] = EmailTopic.query.count()
            
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        info['error'] = str(e)
    
    return jsonify(info)

@bp.route('/test-topic-service')
def test_topic_service():
    """Test the topic service functionality"""
    try:
        from services.topic_service import get_topic_service
        
        service = get_topic_service()
        
        # Test creating a topic
        test_topic = service.create_topic(
            name="Test Topic",
            description="Test topic for validation",
            level=0,
            created_by="admin_test"
        )
        
        # Test topic hierarchy
        hierarchy = service.get_topic_hierarchy()
        
        # Clean up test topic
        service.delete_topic(test_topic.id)
        
        return jsonify({
            'status': 'success',
            'message': 'Topic service is working correctly',
            'hierarchy_count': len(hierarchy)
        })
        
    except Exception as e:
        logger.error(f"Topic service test error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500