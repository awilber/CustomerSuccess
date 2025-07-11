# CustomerSuccess

A comprehensive customer relationship management and success tracking application designed for real estate markets.

## Overview

CustomerSuccess helps real estate professionals manage client relationships, analyze communication patterns, and track project progress across three main market segments:

1. **Residential Real Estate Resales** - Individual homes through traditional brokerages
2. **Residential Project Unit Sales** - Developer inventory management and presales
3. **Commercial Real Estate** - Business property transactions and management

## Key Features

- 📧 **Google Takeout Email Integration** - Import and analyze email communications
- 📁 **Google Drive Integration** - Link and monitor shared drives and folders
- 📊 **Interactive Analytics** - Timeline visualizations and communication patterns
- 🔍 **AI-Powered Insights** - Contextual search and content correlation
- 🏷️ **Smart Tagging System** - Categorize emails and files automatically
- ⚡ **Background Processing** - Asynchronous file analysis and correlation
- 🎯 **Real-time Search** - Advanced filtering and contextual queries

## Technology Stack

- **Backend**: Flask 3.1, SQLAlchemy 2.0, Python 3.13
- **Frontend**: Alpine.js, TailwindCSS, Plotly.js
- **Database**: SQLite (development), PostgreSQL (production)
- **Integrations**: Google Drive API, Google OAuth2
- **Deployment**: AWS EC2, Docker (production ready)

## Quick Start

### Prerequisites
- Python 3.13+
- Google Cloud Console project with Drive API enabled
- OAuth2 credentials (`credentials.json`)

### Local Development

```bash
# Clone the repository
git clone https://github.com/yourusername/CustomerSuccess.git
cd CustomerSuccess

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

The app will automatically find an available port starting from 5000.

### First Time Setup

1. Place your `credentials.json` file in the project root
2. Visit `http://localhost:5000/init-db` to initialize with sample data
3. Navigate to Google Drive integration to authenticate

## Architecture

### Core Components

- **Models** (`models/`): SQLAlchemy entities for customers, emails, files, and correlations
- **Routes** (`routes/`): Blueprint-based API endpoints and views
- **Services** (`services/`): Business logic for integrations and background processing
- **Templates** (`templates/`): Jinja2 templates with responsive design

### Data Flow

1. **Email Import**: Google Takeout ZIP files → Parsed emails → Database storage
2. **File Monitoring**: Google Drive/Local directories → Background scanning → Metadata extraction
3. **AI Correlation**: Content analysis → Relationship detection → Insights generation
4. **Analytics**: Aggregated data → Interactive visualizations → User insights

## Deployment

### AWS Production Deployment

```bash
# Install AWS CLI and configure credentials
aws configure

# Deploy using provided scripts
./deploy/aws-deploy.sh

# Or manually deploy with Docker
docker build -t customer-success .
docker run -p 80:5000 customer-success
```

### Environment Variables

```bash
# Required for production
export FLASK_ENV=production
export DATABASE_URL=postgresql://user:pass@host:port/dbname
export SECRET_KEY=your-secret-key
export GOOGLE_CLIENT_ID=your-client-id
export GOOGLE_CLIENT_SECRET=your-client-secret
```

## API Documentation

### Customer Management
- `GET /api/customers` - List all customers
- `POST /api/customers` - Create new customer
- `GET /api/customers/{id}` - Get customer details

### Analytics
- `GET /api/analytics/timeline/{customer_id}` - Communication timeline
- `POST /api/insights/query/{customer_id}` - Contextual search

### File Management
- `POST /api/directories/link/{customer_id}` - Link directory
- `GET /api/directories/analysis/{customer_id}` - File analysis dashboard

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Development Workflow

This project uses Git Flow:
- `main` - Production-ready code
- `develop` - Integration branch for features
- `feature/*` - New features and enhancements
- `hotfix/*` - Critical production fixes

## License

This project is proprietary software. All rights reserved.

## Support

For support and questions:
- Create an issue in the GitHub repository
- Contact the development team

---

Built with ❤️ for real estate professionals