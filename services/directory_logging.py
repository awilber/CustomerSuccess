import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

class DirectoryLogger:
    """Comprehensive logging service for directory operations"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        # Create dedicated log file for directory operations
        self.log_file = os.path.join(log_dir, "directory_operations.log")
        
        # Set up detailed logging
        self.logger = logging.getLogger("directory_operations")
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # File handler for detailed logs
        file_handler = logging.FileHandler(self.log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler for critical issues
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        
        # Detailed formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # JSON progress file for real-time status updates
        self.progress_file = os.path.join(log_dir, "directory_scan_progress.json")
        
    def log_directory_link_start(self, customer_id: int, directory_type: str, 
                               drive_id: str = None, folder_id: str = None, 
                               folder_name: str = None, path: str = None):
        """Log the start of directory linking process"""
        details = {
            "customer_id": customer_id,
            "directory_type": directory_type,
            "drive_id": drive_id,
            "folder_id": folder_id,
            "folder_name": folder_name,
            "path": path,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info(f"Directory link started: {json.dumps(details, indent=2)}")
        
        # Update progress file
        self.update_progress(f"customer_{customer_id}", {
            "status": "linking",
            "details": details,
            "progress": {"current": 0, "total": 0, "message": "Starting directory link..."}
        })
        
    def log_directory_link_success(self, customer_id: int, directory_link_id: int, 
                                 directory_type: str, details: Dict[str, Any]):
        """Log successful directory linking"""
        log_data = {
            "customer_id": customer_id,
            "directory_link_id": directory_link_id,
            "directory_type": directory_type,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info(f"Directory link successful: {json.dumps(log_data, indent=2)}")
        
        # Update progress file
        self.update_progress(f"customer_{customer_id}", {
            "status": "linked",
            "details": log_data,
            "progress": {"current": 1, "total": 1, "message": "Directory linked successfully"}
        })
        
    def log_directory_link_error(self, customer_id: int, directory_type: str, 
                               error: str, details: Dict[str, Any]):
        """Log directory linking error"""
        log_data = {
            "customer_id": customer_id,
            "directory_type": directory_type,
            "error": error,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.error(f"Directory link failed: {json.dumps(log_data, indent=2)}")
        
        # Update progress file
        self.update_progress(f"customer_{customer_id}", {
            "status": "error",
            "error": error,
            "details": log_data,
            "progress": {"current": 0, "total": 0, "message": f"Error: {error}"}
        })
        
    def log_scan_start(self, customer_id: int, directory_link_id: int, 
                      scan_type: str, scan_details: Dict[str, Any]):
        """Log the start of directory scanning"""
        log_data = {
            "customer_id": customer_id,
            "directory_link_id": directory_link_id,
            "scan_type": scan_type,
            "scan_details": scan_details,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info(f"Directory scan started: {json.dumps(log_data, indent=2)}")
        
        # Update progress file
        self.update_progress(f"scan_{directory_link_id}", {
            "status": "scanning",
            "scan_type": scan_type,
            "details": log_data,
            "progress": {"current": 0, "total": 0, "message": "Starting directory scan..."}
        })
        
    def log_scan_progress(self, directory_link_id: int, current_files: int, 
                         total_files: int, current_folders: int, total_folders: int,
                         current_file: str = None, current_folder: str = None):
        """Log scanning progress with detailed counts"""
        progress_data = {
            "directory_link_id": directory_link_id,
            "files": {"current": current_files, "total": total_files},
            "folders": {"current": current_folders, "total": total_folders},
            "current_file": current_file,
            "current_folder": current_folder,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.debug(f"Scan progress: {json.dumps(progress_data)}")
        
        # Update progress file
        message = f"Scanned {current_files} files"
        if total_files > 0:
            message += f" of {total_files}"
        if current_folders > 0:
            message += f", {current_folders} folders"
        if current_file:
            message += f" (processing: {current_file})"
            
        self.update_progress(f"scan_{directory_link_id}", {
            "status": "scanning",
            "progress": {
                "current": current_files,
                "total": total_files,
                "message": message,
                "folders": {"current": current_folders, "total": total_folders}
            },
            "details": progress_data
        })
        
    def log_scan_completion(self, directory_link_id: int, results: Dict[str, Any]):
        """Log completion of directory scanning"""
        log_data = {
            "directory_link_id": directory_link_id,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info(f"Directory scan completed: {json.dumps(log_data, indent=2)}")
        
        # Update progress file
        files_processed = results.get("files_processed", 0)
        folders_processed = results.get("folders_processed", 0)
        
        self.update_progress(f"scan_{directory_link_id}", {
            "status": "completed",
            "results": results,
            "progress": {
                "current": files_processed,
                "total": files_processed,
                "message": f"Scan completed: {files_processed} files, {folders_processed} folders processed"
            }
        })
        
    def log_scan_error(self, directory_link_id: int, error: str, details: Dict[str, Any]):
        """Log directory scanning error"""
        log_data = {
            "directory_link_id": directory_link_id,
            "error": error,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.error(f"Directory scan failed: {json.dumps(log_data, indent=2)}")
        
        # Update progress file
        self.update_progress(f"scan_{directory_link_id}", {
            "status": "error",
            "error": error,
            "details": log_data,
            "progress": {"current": 0, "total": 0, "message": f"Scan failed: {error}"}
        })
        
    def log_authentication_status(self, auth_type: str, success: bool, details: Dict[str, Any]):
        """Log authentication attempts and status"""
        log_data = {
            "auth_type": auth_type,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        
        level = logging.INFO if success else logging.ERROR
        self.logger.log(level, f"Authentication {auth_type}: {json.dumps(log_data, indent=2)}")
        
    def log_api_call(self, api_name: str, operation: str, success: bool, 
                    response_data: Any = None, error: str = None):
        """Log API calls (Google Drive, etc.)"""
        log_data = {
            "api_name": api_name,
            "operation": operation,
            "success": success,
            "response_data": response_data,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        
        level = logging.DEBUG if success else logging.ERROR
        self.logger.log(level, f"API call {api_name}.{operation}: {json.dumps(log_data, indent=2)}")
        
    def update_progress(self, operation_id: str, progress_data: Dict[str, Any]):
        """Update progress file with current operation status"""
        try:
            # Read existing progress
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r') as f:
                    all_progress = json.load(f)
            else:
                all_progress = {}
            
            # Update this operation's progress
            all_progress[operation_id] = progress_data
            all_progress[operation_id]["last_updated"] = datetime.now().isoformat()
            
            # Write back to file
            with open(self.progress_file, 'w') as f:
                json.dump(all_progress, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to update progress file: {str(e)}")
            
    def get_progress(self, operation_id: str = None) -> Dict[str, Any]:
        """Get current progress for an operation or all operations"""
        try:
            if not os.path.exists(self.progress_file):
                return {}
                
            with open(self.progress_file, 'r') as f:
                all_progress = json.load(f)
                
            if operation_id:
                return all_progress.get(operation_id, {})
            else:
                return all_progress
                
        except Exception as e:
            self.logger.error(f"Failed to read progress file: {str(e)}")
            return {}
            
    def clear_progress(self, operation_id: str = None):
        """Clear progress for an operation or all operations"""
        try:
            if not os.path.exists(self.progress_file):
                return
                
            if operation_id:
                with open(self.progress_file, 'r') as f:
                    all_progress = json.load(f)
                    
                all_progress.pop(operation_id, None)
                
                with open(self.progress_file, 'w') as f:
                    json.dump(all_progress, f, indent=2)
            else:
                # Clear all progress
                with open(self.progress_file, 'w') as f:
                    json.dump({}, f)
                    
        except Exception as e:
            self.logger.error(f"Failed to clear progress: {str(e)}")

# Global instance
directory_logger = DirectoryLogger()