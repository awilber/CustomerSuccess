import os
import json
import ssl
import httplib2
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle
from datetime import datetime
from models import db, FileReference

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

class GoogleDriveService:
    def __init__(self, credentials_file='credentials.json', token_file='token.pickle'):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None
        self.creds = None
        
    def authenticate(self):
        """Authenticate and create Google Drive service"""
        # Load existing token
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                self.creds = pickle.load(token)
        
        # If there are no (valid) credentials available, let the user log in
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                # Create request with custom HTTP object for SSL handling
                http = httplib2.Http()
                if os.environ.get('FLASK_ENV') == 'development':
                    http.disable_ssl_certificate_validation = True
                self.creds.refresh(Request(http=http))
            else:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.credentials_file}\n"
                        "Please download credentials from Google Cloud Console"
                    )
                    
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                self.creds = flow.run_local_server(port=0)
                
            # Save the credentials for the next run
            with open(self.token_file, 'wb') as token:
                pickle.dump(self.creds, token)
        
        # Build service with proper http authorization
        if os.environ.get('FLASK_ENV') == 'development':
            # Create an httplib2.Http instance with SSL certificate verification disabled
            http = httplib2.Http()
            http.disable_ssl_certificate_validation = True
            # Authorize the httplib2.Http object with our credentials
            authorized_http = self.creds.authorize(http)
            self.service = build('drive', 'v3', http=authorized_http)
        else:
            # Production mode - use default SSL verification
            self.service = build('drive', 'v3', credentials=self.creds)
        return True
    
    def list_shared_drives(self):
        """List all shared drives accessible to the user"""
        try:
            results = self.service.drives().list(
                pageSize=100,
                fields="drives(id, name)"
            ).execute()
            
            return results.get('drives', [])
            
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def list_files_in_drive(self, drive_id, folder_id=None, query=''):
        """List files in a specific shared drive or folder"""
        try:
            # Build the query
            q_parts = [f"'{folder_id or drive_id}' in parents"]
            if query:
                q_parts.append(f"name contains '{query}'")
            q_parts.append("trashed = false")
            
            q = ' and '.join(q_parts)
            
            # Additional parameters for shared drives
            params = {
                'q': q,
                'pageSize': 100,
                'fields': "files(id, name, mimeType, size, modifiedTime, webViewLink, parents)",
                'orderBy': 'folder,name'
            }
            
            # If listing from a shared drive (not a folder), include shared drive support
            if not folder_id:
                params.update({
                    'corpora': 'drive',
                    'driveId': drive_id,
                    'includeItemsFromAllDrives': True,
                    'supportsAllDrives': True
                })
            else:
                params.update({
                    'includeItemsFromAllDrives': True,
                    'supportsAllDrives': True
                })
            
            results = self.service.files().list(**params).execute()
            
            return results.get('files', [])
            
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def get_file_metadata(self, file_id):
        """Get detailed metadata for a specific file"""
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, size, modifiedTime, webViewLink, parents, description',
                supportsAllDrives=True
            ).execute()
            
            return file
            
        except HttpError as error:
            print(f'An error occurred: {error}')
            return None
    
    def save_file_reference(self, file_data, customer_id):
        """Save a file reference to the database"""
        # Check if already exists
        existing = FileReference.query.filter_by(
            drive_id=file_data['id'],
            customer_id=customer_id
        ).first()
        
        if not existing:
            file_ref = FileReference(
                customer_id=customer_id,
                drive_id=file_data['id'],
                file_name=file_data['name'],
                mime_type=file_data.get('mimeType', ''),
                size_bytes=int(file_data.get('size', 0)) if file_data.get('size') else None,
                last_modified=datetime.fromisoformat(file_data['modifiedTime'].replace('Z', '+00:00'))
            )
            db.session.add(file_ref)
            db.session.commit()
            return file_ref
        
        return existing
    
    def scan_directory(self, drive_id, folder_id=None):
        """Recursively scan a Google Drive directory and return all files"""
        all_files = []
        
        def scan_folder(current_folder_id=None):
            """Recursive function to scan folders"""
            files = self.list_files_in_drive(drive_id, current_folder_id or folder_id)
            
            for file in files:
                if file['mimeType'] == 'application/vnd.google-apps.folder':
                    # Recursively scan subfolder
                    scan_folder(file['id'])
                else:
                    # Add file to results
                    all_files.append(file)
        
        scan_folder()
        return all_files

# Global instance
drive_service = None

def get_drive_service():
    """Get or create the Google Drive service instance"""
    global drive_service
    if not drive_service:
        drive_service = GoogleDriveService()
    return drive_service