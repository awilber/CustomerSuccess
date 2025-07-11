# Google Drive Integration Updates

## SSL Error Fix

Updated `services/drive_service.py` to handle SSL certificate verification errors:
- Added httplib2 import for custom HTTP handling
- Modified authentication to disable SSL verification in development mode
- Added SSL handling for token refresh
- Added httplib2==0.22.0 to requirements.txt

## Google Drive Directory Linking

Added functionality to link Google Drive directories to customers:

### Database Changes
Updated `DirectoryLink` model to support both local and Drive directories:
- `link_type`: 'local' or 'drive' 
- `drive_id`: Google Drive ID
- `folder_id`: Specific folder within a drive
- Made `path` nullable for Drive directories

### New Features
1. **Link Drive Directories**: Added button in directories list page to link Google Drive folders
2. **Drive Directory Scanning**: Background task to scan and index files in linked Drive directories
3. **Mixed Directory Display**: Updated UI to show both local and Drive directories with appropriate icons
4. **Recursive Scanning**: Added method to recursively scan Drive folders and subfolders

### Routes Added
- `/directories/link-drive/<customer_id>`: Link a Google Drive directory to a customer

### UI Updates
- Added "Link Google Drive" button to directories list
- Updated directory display to show Drive icon for Google Drive directories
- Added "Link This Directory" button when browsing Google Drive
- Shows Drive ID and Folder ID for Drive directories instead of local path

### Background Processing
Added `scan_drive_directory` task to:
- Authenticate with Google Drive
- Recursively scan selected Drive directory
- Save file references to database
- Queue files for processing
- Update directory statistics

## Usage

1. **Fix SSL Errors**: The SSL verification is now disabled in development mode. Set `FLASK_ENV=development` in your environment.

2. **Link Drive Directory**:
   - Go to a customer's directories page
   - Click "Link Google Drive"
   - Browse to the desired drive/folder
   - Click "Link This Directory"
   - The directory will be scanned in the background

3. **Update Database**: Run `python update_database.py` to add the new columns to the database.

## Next Steps
- Add support for downloading Drive files for processing
- Implement Drive file content extraction
- Add Drive-specific file preview functionality