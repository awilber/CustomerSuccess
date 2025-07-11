# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CustomerSuccess is a project focused on customer relationship management and success tracking for real estate markets. The project targets three main market segments:
1. Residential real estate resales (individual homes through traditional brokerages)
2. Residential project unit sales (preselling and selling inventory for developers)
3. Commercial real estate

## Project Status

This is a fully developed Flask web application with advanced features including Google Drive integration, email parsing, analytics, and file correlation. The application uses SQLAlchemy for database management and includes background processing for file analysis.

## Development Setup

This is a Flask-based web application for customer relationship management.

### Setup Commands:

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

The app will automatically find an available port starting from 5000.

### First Time Setup:

1. Run the app: `python app.py`
2. Visit http://localhost:5000/init-db to initialize the database with sample data
3. The default customer "HCR" will be created with sample people

## Architecture Overview

The application follows a modular Flask architecture:

### Core Components
- **Models** (`models/__init__.py`): SQLAlchemy models for Customer, Person, EmailThread, FileReference, DirectoryLink, Tag, and correlation tables
- **Routes** (`routes/`): Blueprint-based route handlers for different features
- **Services** (`services/`): Business logic for email parsing, Google Drive integration, file analysis, and background processing
- **Background Tasks** (`services/background_tasks.py`): Asynchronous processing for file analysis and correlation

### Data Models
- **Customer**: Central entity linking all other data
- **Person**: Contact individuals (internal team vs customer team)
- **EmailThread**: Parsed email communications with full-text storage
- **FileReference**: Files from Google Drive or local directories with metadata and embeddings
- **DirectoryLink**: Linked local or Google Drive directories for monitoring
- **Tag**: Categorization system for emails and files
- **Correlations**: AI-powered relationships between files and emails

### Integration Points
- **Google Drive API**: OAuth2 authentication and file access
- **Email Parsing**: Google Takeout ZIP file processing
- **Analytics**: Plotly-based timeline visualizations

## Port Management

When starting any services:
1. Check if the requested port is already in use
2. If occupied, check if it's a previous instance of this project
3. Use increments of 10 for alternative ports (e.g., 3000, 3010, 3020)
4. Update all related configurations when ports change

## Key Features

1. **Google Takeout Email Import**: Upload ZIP files containing email exports with full parsing
2. **Google Drive Integration**: OAuth2 authentication, browse drives, link directories
3. **Timeline Visualization**: Interactive Plotly timeline showing communication history
4. **Customer Management**: Track multiple customers with associated people and teams
5. **File Analysis**: Automatic scanning of linked directories with metadata extraction
6. **AI Correlation Engine**: Links related files and emails based on content analysis
7. **Tagging System**: Categorize emails and files with custom tags
8. **Background Processing**: Asynchronous file analysis and correlation detection
9. **Analytics Dashboard**: Communication patterns and relationship insights

## Common Development Tasks

### Database Operations
```bash
# Reset database completely
rm database.db
python app.py
# Visit /init-db to create sample data

# Run database migrations
python add_tags_migration.py
python update_database.py
```

### Google Drive Setup
1. Place `credentials.json` file in project root (Google Cloud Console OAuth2 credentials)
2. Visit `/drive/setup` to authenticate and authorize access
3. Token will be saved automatically for subsequent requests

### Background Processing
The application starts background tasks automatically on startup. Key services:
- File analysis and metadata extraction
- Email-file correlation detection
- Directory monitoring and scanning

### Adding New Features
- **Routes**: Add new blueprints in `routes/` directory
- **Services**: Business logic goes in `services/` directory  
- **Models**: Database models in `models/__init__.py`
- **Templates**: Jinja2 templates in `templates/` with base.html inheritance

### Testing Data Import
1. **Email Import**: Upload Google Takeout ZIP through customer detail page
2. **Directory Linking**: Use `/directories/link-drive/<customer_id>` for Google Drive folders
3. **Local Directories**: Use `/directories/link/<customer_id>` for local folder scanning