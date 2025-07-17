import threading
import queue
import time
from datetime import datetime
from models import db, FileReference, DirectoryLink
from services.directory_scanner import directory_scanner
from services.embeddings_service import embeddings_service
from services.drive_service import get_drive_service
from services.directory_logging import directory_logger
import logging

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class BackgroundTaskProcessor:
    """Simple background task processor using threads"""
    
    def __init__(self, app=None):
        self.task_queue = queue.Queue()
        self.running = False
        self.worker_thread = None
        self.app = app
    
    def start(self):
        """Start the background processor"""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._process_tasks, daemon=True)
            self.worker_thread.start()
    
    def stop(self):
        """Stop the background processor"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
    
    def add_task(self, task_type, **kwargs):
        """Add a task to the queue"""
        task = {
            'type': task_type,
            'kwargs': kwargs,
            'created_at': datetime.utcnow()
        }
        logger.info(f"Adding background task: {task_type} with args: {kwargs}")
        self.task_queue.put(task)
    
    def _process_tasks(self):
        """Main task processing loop"""
        while self.running:
            try:
                # Get task with timeout
                task = self.task_queue.get(timeout=1)
                
                # Process based on task type
                if task['type'] == 'scan_directory':
                    self._process_directory_scan(task['kwargs'])
                
                elif task['type'] == 'scan_drive_directory':
                    self._process_drive_directory_scan(task['kwargs'])
                    
                elif task['type'] == 'process_file':
                    self._process_file(task['kwargs'])
                    
                elif task['type'] == 'correlate_files':
                    self._correlate_files(task['kwargs'])
                    
                elif task['type'] == 'recalculate_importance':
                    self._recalculate_importance(task['kwargs'])
                
            except queue.Empty:
                # No tasks, continue
                continue
            except Exception as e:
                logger.error(f"Error processing background task: {str(e)}", exc_info=True)
    
    def _process_directory_scan(self, kwargs):
        """Process directory scan task"""
        directory_path = kwargs.get('directory_path')
        customer_id = kwargs.get('customer_id')
        directory_link_id = kwargs.get('directory_link_id')
        
        logger.info(f"Starting background directory scan task for customer {customer_id}: {directory_path}")
        
        if not directory_path or not customer_id:
            logger.error(f"Invalid directory scan parameters: directory_path={directory_path}, customer_id={customer_id}")
            return
            
        try:
            # Scan directory
            logger.info(f"Calling directory scanner for path: {directory_path}")
            results = directory_scanner.scan_directory(
                directory_path, customer_id, directory_link_id
            )
            
            logger.info(f"Directory scan completed. Results: {results}")
            
            # Queue file processing tasks for new files
            with self.app.app_context():
                pending_files = FileReference.query.filter_by(
                    customer_id=customer_id,
                    processing_status='pending'
                ).all()
                
                logger.info(f"Found {len(pending_files)} pending files to process")
                
                for file_ref in pending_files:
                    logger.debug(f"Queueing file processing task for file {file_ref.id}: {file_ref.filename}")
                    self.add_task('process_file', file_id=file_ref.id)
                    
        except Exception as e:
            logger.error(f"Error in directory scan task: {str(e)}", exc_info=True)
            
            # Update directory link status to failed
            if directory_link_id:
                try:
                    with self.app.app_context():
                        dir_link = DirectoryLink.query.get(directory_link_id)
                        if dir_link:
                            dir_link.scan_status = 'failed'
                            db.session.commit()
                            logger.info(f"Updated directory link {directory_link_id} status to 'failed'")
                except Exception as db_error:
                    logger.error(f"Error updating directory link status: {str(db_error)}")
    
    def _process_drive_directory_scan(self, kwargs):
        """Process Google Drive directory scan task"""
        drive_id = kwargs.get('drive_id')
        folder_id = kwargs.get('folder_id')
        customer_id = kwargs.get('customer_id')
        directory_link_id = kwargs.get('directory_link_id')
        
        # Log scan start
        directory_logger.log_scan_start(
            customer_id=customer_id,
            directory_link_id=directory_link_id,
            scan_type='google_drive',
            scan_details={
                'drive_id': drive_id,
                'folder_id': folder_id,
                'customer_id': customer_id
            }
        )
        
        if drive_id and customer_id:
            try:
                with self.app.app_context():
                    # Update scan status
                    dir_link = DirectoryLink.query.get(directory_link_id)
                    if dir_link:
                        dir_link.scan_status = 'scanning'
                        db.session.commit()
                        
                        directory_logger.log_scan_progress(
                            directory_link_id=directory_link_id,
                            current_files=0,
                            total_files=0,
                            current_folders=0,
                            total_folders=0,
                            current_file=None,
                            current_folder=f"Starting scan of {dir_link.name}"
                        )
                    
                    # Get drive service
                    drive = get_drive_service()
                    if not drive.service:
                        directory_logger.log_authentication_status(
                            auth_type='google_drive',
                            success=False,
                            details={'message': 'Drive service not authenticated, attempting auth'}
                        )
                        auth_success = drive.authenticate()
                        directory_logger.log_authentication_status(
                            auth_type='google_drive',
                            success=auth_success,
                            details={'message': 'Authentication completed'}
                        )
                        
                        if not auth_success:
                            raise Exception("Google Drive authentication failed")
                    
                    # Scan the directory with progress tracking
                    directory_logger.log_api_call(
                        api_name='google_drive',
                        operation='scan_directory',
                        success=True,
                        response_data={'message': 'Starting directory scan'}
                    )
                    
                    files = drive.scan_directory(drive_id, folder_id)
                    
                    directory_logger.log_api_call(
                        api_name='google_drive',
                        operation='scan_directory',
                        success=True,
                        response_data={'files_found': len(files)}
                    )
                    
                    # Save file references with progress tracking
                    file_count = 0
                    total_size = 0
                    total_files = len(files)
                    
                    for i, file_data in enumerate(files):
                        # Log progress every 10 files
                        if i % 10 == 0:
                            directory_logger.log_scan_progress(
                                directory_link_id=directory_link_id,
                                current_files=i,
                                total_files=total_files,
                                current_folders=0,
                                total_folders=0,
                                current_file=file_data.get('name', 'Unknown file')
                            )
                        
                        # Save file reference
                        file_ref = drive.save_file_reference(file_data, customer_id)
                        file_count += 1
                        if file_data.get('size'):
                            total_size += int(file_data['size'])
                        
                        # Queue for processing
                        if file_ref and file_ref.processing_status == 'pending':
                            self.add_task('process_file', file_id=file_ref.id)
                    
                    # Update directory link stats
                    if dir_link:
                        dir_link.file_count = file_count
                        dir_link.total_size = total_size
                        dir_link.last_scanned = datetime.utcnow()
                        dir_link.scan_status = 'completed'
                        db.session.commit()
                        
                        # Log completion
                        directory_logger.log_scan_completion(
                            directory_link_id=directory_link_id,
                            results={
                                'files_processed': file_count,
                                'total_size_bytes': total_size,
                                'folders_processed': 0,
                                'scan_duration': 'completed'
                            }
                        )
                        
            except Exception as e:
                error_msg = f"Error scanning Drive directory: {str(e)}"
                directory_logger.log_scan_error(
                    directory_link_id=directory_link_id,
                    error=error_msg,
                    details={
                        'drive_id': drive_id,
                        'folder_id': folder_id,
                        'customer_id': customer_id,
                        'exception': str(e)
                    }
                )
                
                logger.error(error_msg, exc_info=True)
                
                with self.app.app_context():
                    dir_link = DirectoryLink.query.get(directory_link_id)
                    if dir_link:
                        dir_link.scan_status = 'error'
                        db.session.commit()
    
    def _process_file(self, kwargs):
        """Process individual file"""
        file_id = kwargs.get('file_id')
        
        if file_id:
            with self.app.app_context():
                # Process file content and generate embeddings
                success = embeddings_service.process_file(file_id)
                
                if success:
                    # Queue correlation task
                    file_ref = FileReference.query.get(file_id)
                    if file_ref:
                        self.add_task('correlate_files', 
                                    customer_id=file_ref.customer_id,
                                    file_id=file_id)
    
    def _correlate_files(self, kwargs):
        """Correlate files with emails"""
        customer_id = kwargs.get('customer_id')
        file_id = kwargs.get('file_id')
        
        if customer_id:
            # This will be implemented by the correlation engine
            from services.correlation_engine import correlation_engine
            correlation_engine.correlate_customer_files(customer_id, file_id)
    
    def _recalculate_importance(self, kwargs):
        """Recalculate file importance scores"""
        customer_id = kwargs.get('customer_id')
        
        if customer_id:
            from services.correlation_engine import correlation_engine
            correlation_engine.recalculate_importance_scores(customer_id)

# Global instance - initialized without app, will be set up in app.py
background_processor = None

def get_background_processor():
    """Get the global background processor instance"""
    return background_processor