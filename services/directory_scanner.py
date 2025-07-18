import os
import hashlib
import mimetypes
from datetime import datetime
# import magic  # Optional dependency
import json
from pathlib import Path
from models import db, FileReference, DirectoryLink
import platform
import pwd
import stat
import logging

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class DirectoryScanner:
    def __init__(self):
        self.supported_extensions = {
            '.txt', '.md', '.pdf', '.doc', '.docx', '.xls', '.xlsx',
            '.ppt', '.pptx', '.csv', '.json', '.xml', '.html', '.htm',
            '.py', '.js', '.java', '.cpp', '.c', '.h', '.cs', '.rb',
            '.go', '.rs', '.swift', '.kt', '.scala', '.r', '.sql',
            '.yaml', '.yml', '.ini', '.conf', '.log', '.msg', '.eml',
            '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg',
            '.mp4', '.avi', '.mov', '.mp3', '.wav', '.flac'
        }
        
        # self.mime = magic.Magic(mime=True)  # Optional
        
    def scan_directory(self, directory_path, customer_id, directory_link_id=None):
        """Scan a directory and catalog all files"""
        logger.info(f"Starting directory scan for customer {customer_id}: {directory_path}")
        
        results = {
            'total_files': 0,
            'new_files': 0,
            'updated_files': 0,
            'errors': [],
            'total_size': 0
        }
        
        if not os.path.exists(directory_path):
            error_msg = f"Directory not found: {directory_path}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            return results
        
        # Update directory link status
        if directory_link_id:
            dir_link = DirectoryLink.query.get(directory_link_id)
            if dir_link:
                logger.info(f"Setting directory link {directory_link_id} status to 'scanning'")
                dir_link.scan_status = 'scanning'
                dir_link.last_scanned = datetime.utcnow()
                db.session.commit()
            else:
                logger.warning(f"Directory link {directory_link_id} not found in database")
        
        # Get initial directory stats
        try:
            dir_size = sum(os.path.getsize(os.path.join(dirpath, filename))
                          for dirpath, dirnames, filenames in os.walk(directory_path)
                          for filename in filenames)
            logger.info(f"Directory contains {dir_size / (1024*1024):.2f} MB of data")
        except Exception as e:
            logger.warning(f"Could not calculate directory size: {e}")
            
        start_time = datetime.utcnow()
        
        try:
            processed_count = 0
            for root, dirs, files in os.walk(directory_path):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                logger.info(f"Processing directory: {root} (contains {len(files)} files)")
                
                for filename in files:
                    if filename.startswith('.'):
                        continue
                        
                    filepath = os.path.join(root, filename)
                    processed_count += 1
                    
                    try:
                        file_info = self._process_file(filepath, customer_id, directory_path)
                        if file_info:
                            results['total_files'] += 1
                            results['total_size'] += file_info.get('size', 0)
                            
                            if file_info.get('is_new'):
                                results['new_files'] += 1
                                logger.debug(f"New file detected: {filepath}")
                            elif file_info.get('is_updated'):
                                results['updated_files'] += 1
                                logger.debug(f"Updated file detected: {filepath}")
                                
                            # Log progress every 100 files
                            if processed_count % 100 == 0:
                                logger.info(f"Processed {processed_count} files. Stats: {results['total_files']} valid, {results['new_files']} new, {results['updated_files']} updated")
                                
                    except Exception as e:
                        error_msg = f"Error processing {filepath}: {str(e)}"
                        logger.error(error_msg)
                        results['errors'].append(error_msg)
        
        except Exception as e:
            error_msg = f"Error scanning directory: {str(e)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
        
        # Calculate scan duration
        scan_duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Directory scan completed in {scan_duration:.2f} seconds")
        logger.info(f"Scan results: {results['total_files']} total files, {results['new_files']} new, {results['updated_files']} updated, {len(results['errors'])} errors")
        
        # Update directory link with results
        if directory_link_id:
            dir_link = DirectoryLink.query.get(directory_link_id)
            if dir_link:
                logger.info(f"Updating directory link {directory_link_id} status to 'completed'")
                dir_link.scan_status = 'completed'
                dir_link.file_count = results['total_files']
                dir_link.total_size = results['total_size']
                db.session.commit()
            else:
                logger.warning(f"Directory link {directory_link_id} not found for completion update")
        
        # Log any errors that occurred
        if results['errors']:
            logger.warning(f"Scan completed with {len(results['errors'])} errors:")
            for error in results['errors'][:10]:  # Log first 10 errors
                logger.warning(f"  - {error}")
            if len(results['errors']) > 10:
                logger.warning(f"  ... and {len(results['errors']) - 10} more errors")
        
        return results
    
    def _process_file(self, filepath, customer_id, base_path):
        """Process a single file and store its metadata"""
        try:
            # Get file stats
            stats = os.stat(filepath)
            file_size = stats.st_size
            
            # Skip very large files (>100MB)
            if file_size > 100 * 1024 * 1024:
                return None
            
            # Calculate content hash
            content_hash = self._calculate_hash(filepath)
            
            # Check if file already exists
            existing = FileReference.query.filter_by(
                customer_id=customer_id,
                content_hash=content_hash
            ).first()
            
            # Get file metadata
            file_ext = Path(filepath).suffix.lower()
            if file_ext not in self.supported_extensions:
                return None
            
            file_info = {
                'size': file_size,
                'is_new': not existing,
                'is_updated': False
            }
            
            # Create or update file reference
            if existing:
                # Check if file has been modified
                last_modified = datetime.fromtimestamp(stats.st_mtime)
                if existing.last_modified and last_modified > existing.last_modified:
                    existing.last_modified = last_modified
                    existing.processing_status = 'pending'  # Re-process if modified
                    file_info['is_updated'] = True
            else:
                # Create new file reference
                relative_path = os.path.relpath(filepath, base_path)
                
                file_ref = FileReference(
                    customer_id=customer_id,
                    file_name=os.path.basename(filepath),
                    file_path=filepath,
                    mime_type=self._get_mime_type(filepath),
                    size_bytes=file_size,
                    last_modified=datetime.fromtimestamp(stats.st_mtime),
                    created_date=datetime.fromtimestamp(stats.st_ctime),
                    content_hash=content_hash,
                    file_type=file_ext[1:] if file_ext else 'unknown',
                    processing_status='pending'
                )
                
                # Try to get created_by (owner)
                if platform.system() != 'Windows':
                    try:
                        file_ref.created_by = pwd.getpwuid(stats.st_uid).pw_name
                    except:
                        pass
                
                db.session.add(file_ref)
            
            db.session.commit()
            return file_info
            
        except Exception as e:
            print(f"Error processing file {filepath}: {str(e)}")
            return None
    
    def _calculate_hash(self, filepath, chunk_size=8192):
        """Calculate SHA256 hash of file content"""
        sha256 = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(chunk_size):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except:
            return None
    
    def _get_mime_type(self, filepath):
        """Get MIME type of file"""
        # Use mimetypes module (standard library)
        mime_type, _ = mimetypes.guess_type(filepath)
        return mime_type or 'application/octet-stream'
    
    def get_directory_stats(self, directory_path):
        """Get statistics about a directory without full scan"""
        stats = {
            'exists': os.path.exists(directory_path),
            'is_directory': os.path.isdir(directory_path) if os.path.exists(directory_path) else False,
            'readable': os.access(directory_path, os.R_OK) if os.path.exists(directory_path) else False,
            'file_count': 0,
            'total_size': 0,
            'subdirs': []
        }
        
        if stats['exists'] and stats['is_directory'] and stats['readable']:
            try:
                # Quick scan for stats
                for item in os.listdir(directory_path):
                    item_path = os.path.join(directory_path, item)
                    if os.path.isfile(item_path) and not item.startswith('.'):
                        stats['file_count'] += 1
                        stats['total_size'] += os.path.getsize(item_path)
                    elif os.path.isdir(item_path) and not item.startswith('.'):
                        stats['subdirs'].append(item)
            except:
                pass
        
        return stats

# Global scanner instance
directory_scanner = DirectoryScanner()