import threading
import queue
import time
from datetime import datetime
from models import db, FileReference, DirectoryLink
from services.directory_scanner import directory_scanner
from services.embeddings_service import embeddings_service
from services.drive_service import get_drive_service

class BackgroundTaskProcessor:
    """Simple background task processor using threads"""
    
    def __init__(self):
        self.task_queue = queue.Queue()
        self.running = False
        self.worker_thread = None
    
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
                print(f"Error processing task: {str(e)}")
    
    def _process_directory_scan(self, kwargs):
        """Process directory scan task"""
        directory_path = kwargs.get('directory_path')
        customer_id = kwargs.get('customer_id')
        directory_link_id = kwargs.get('directory_link_id')
        
        if directory_path and customer_id:
            # Scan directory
            results = directory_scanner.scan_directory(
                directory_path, customer_id, directory_link_id
            )
            
            # Queue file processing tasks for new files
            with db.app.app_context():
                pending_files = FileReference.query.filter_by(
                    customer_id=customer_id,
                    processing_status='pending'
                ).all()
                
                for file_ref in pending_files:
                    self.add_task('process_file', file_id=file_ref.id)
    
    def _process_drive_directory_scan(self, kwargs):
        """Process Google Drive directory scan task"""
        drive_id = kwargs.get('drive_id')
        folder_id = kwargs.get('folder_id')
        customer_id = kwargs.get('customer_id')
        directory_link_id = kwargs.get('directory_link_id')
        
        if drive_id and customer_id:
            try:
                with db.app.app_context():
                    # Update scan status
                    dir_link = DirectoryLink.query.get(directory_link_id)
                    if dir_link:
                        dir_link.scan_status = 'scanning'
                        db.session.commit()
                    
                    # Get drive service
                    drive = get_drive_service()
                    if not drive.service:
                        drive.authenticate()
                    
                    # Scan the directory
                    files = drive.scan_directory(drive_id, folder_id)
                    
                    # Save file references
                    file_count = 0
                    total_size = 0
                    
                    for file_data in files:
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
                        
            except Exception as e:
                print(f"Error scanning Drive directory: {str(e)}")
                with db.app.app_context():
                    dir_link = DirectoryLink.query.get(directory_link_id)
                    if dir_link:
                        dir_link.scan_status = 'error'
                        db.session.commit()
    
    def _process_file(self, kwargs):
        """Process individual file"""
        file_id = kwargs.get('file_id')
        
        if file_id:
            with db.app.app_context():
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

# Global instance
background_processor = BackgroundTaskProcessor()