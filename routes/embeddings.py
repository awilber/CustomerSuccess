from flask import Blueprint, request, jsonify, render_template
from services.embeddings_service import get_embeddings_service
from models import Customer, db
import threading
import time

bp = Blueprint('embeddings', __name__, url_prefix='/embeddings')

# Global storage for background tasks
processing_tasks = {}

@bp.route('/customer/<int:customer_id>')
def customer_embeddings(customer_id):
    """Main customer embeddings interface"""
    customer = Customer.query.get_or_404(customer_id)
    return render_template('embeddings/customer.html', customer=customer)

@bp.route('/api/customer/<int:customer_id>/stats')
def get_customer_stats(customer_id):
    """Get email statistics for a customer"""
    sender_filter = request.args.getlist('senders')
    recipient_filter = request.args.getlist('recipients')
    
    stats = get_embeddings_service().get_email_stats_for_customer(
        customer_id=customer_id,
        sender_filter=sender_filter if sender_filter else None,
        recipient_filter=recipient_filter if recipient_filter else None
    )
    
    return jsonify(stats)

@bp.route('/api/customer/<int:customer_id>/email-addresses')
def get_email_addresses(customer_id):
    """Get unique email addresses for a customer"""
    addresses = get_embeddings_service().get_unique_email_addresses(customer_id)
    return jsonify(addresses)

@bp.route('/api/customer/<int:customer_id>/process', methods=['POST'])
def process_embeddings(customer_id):
    """Start processing embeddings for selected emails"""
    data = request.get_json()
    
    year = data.get('year')
    month = data.get('month')
    sender_filter = data.get('senders')
    recipient_filter = data.get('recipients')
    embedding_method = data.get('embedding_method', 'openai')  # 'openai' or 'tfidf'
    
    # Get email IDs matching the filters
    email_ids = get_embeddings_service().get_filtered_email_ids(
        customer_id=customer_id,
        year=year,
        month=month,
        sender_filter=sender_filter,
        recipient_filter=recipient_filter
    )
    
    if not email_ids:
        return jsonify({'error': 'No emails found matching the selected criteria'}), 400
    
    # Create a unique task ID
    task_id = "customer_{}_{}" .format(customer_id, int(time.time()))
    
    # Initialize task status
    processing_tasks[task_id] = {
        'status': 'starting',
        'progress': 0,
        'total': len(email_ids),
        'processed': 0,
        'errors': 0,
        'skipped': 0,
        'start_time': time.time()
    }
    
    # Get reference to current app before starting thread
    from flask import current_app
    app_instance = current_app._get_current_object()
    
    # Start background processing
    def background_process():
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info("Background process started for task {}".format(task_id))
            
            def progress_callback(current, total):
                progress = int((current / total) * 100)
                processing_tasks[task_id]['progress'] = progress
                processing_tasks[task_id]['processed'] = current
                logger.info("Progress for {}: {}/{}".format(task_id, current, total))
            
            processing_tasks[task_id]['status'] = 'processing'
            
            # Run within application context using the captured app instance
            with app_instance.app_context():
                logger.info("Entering app context for task {}".format(task_id))
                
                # Create service instance with the requested method
                from services.embeddings_service import EmbeddingsService
                service = EmbeddingsService(force_simple=(embedding_method == 'tfidf'))
                logger.info("EmbeddingsService created for task {}".format(task_id))
                
                results = service.process_email_embeddings(
                    email_ids=email_ids,
                    progress_callback=progress_callback
                )
                logger.info("Processing completed for task {}: {}".format(task_id, results))
                
                processing_tasks[task_id].update({
                    'status': 'completed',
                    'progress': 100,
                    'processed': results['processed'],
                    'errors': results['errors'],
                    'skipped': results['skipped'],
                    'end_time': time.time()
                })
                
        except Exception as e:
            logger.error("Error in background process for task {}: {}".format(task_id, str(e)))
            import traceback
            logger.error("Traceback: {}".format(traceback.format_exc()))
            processing_tasks[task_id].update({
                'status': 'error',
                'error': str(e),
                'end_time': time.time()
            })
    
    # Start the background thread
    thread = threading.Thread(target=background_process)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'task_id': task_id,
        'message': 'Started processing {} emails'.format(len(email_ids)),
        'total_emails': len(email_ids)
    })

@bp.route('/api/task/<task_id>/status')
def get_task_status(task_id):
    """Get the status of a processing task"""
    if task_id not in processing_tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    task = processing_tasks[task_id]
    
    # Calculate duration if available
    if 'start_time' in task:
        if 'end_time' in task:
            task['duration'] = task['end_time'] - task['start_time']
        else:
            task['duration'] = time.time() - task['start_time']
    
    return jsonify(task)

@bp.route('/api/task/<task_id>/cancel', methods=['POST'])
def cancel_task(task_id):
    """Cancel a processing task"""
    if task_id not in processing_tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    # In a real implementation, you'd need a way to signal the background thread to stop
    # For now, we'll just mark it as cancelled
    processing_tasks[task_id]['status'] = 'cancelled'
    
    return jsonify({'message': 'Task cancelled'})

@bp.route('/api/cleanup-tasks', methods=['POST'])
def cleanup_tasks():
    """Clean up old completed tasks"""
    current_time = time.time()
    tasks_to_remove = []
    
    for task_id, task in processing_tasks.items():
        # Remove tasks older than 1 hour
        if 'end_time' in task and (current_time - task['end_time']) > 3600:
            tasks_to_remove.append(task_id)
    
    for task_id in tasks_to_remove:
        del processing_tasks[task_id]
    
    return jsonify({'message': 'Cleaned up {} old tasks'.format(len(tasks_to_remove))})

@bp.route('/api/customer/<int:customer_id>/topics')
def get_customer_topics(customer_id):
    """Get topics for a customer"""
    try:
        topics = get_embeddings_service().extract_topics_from_embeddings(
            customer_id=customer_id,
            max_main_topics=10,
            max_sub_topics=20
        )
        return jsonify(topics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/customer/<int:customer_id>/extract-topics', methods=['POST'])
def extract_topics(customer_id):
    """Extract topics from existing embeddings"""
    try:
        max_main_topics = request.json.get('max_main_topics', 10)
        max_sub_topics = request.json.get('max_sub_topics', 20)
        
        topics = get_embeddings_service().extract_topics_from_embeddings(
            customer_id=customer_id,
            max_main_topics=max_main_topics,
            max_sub_topics=max_sub_topics
        )
        
        return jsonify(topics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500