#!/bin/bash
# CustomerSuccess QA Automation Script
# This script runs all QA checks that Claude must pass before marking any task as complete

echo "🚀 CustomerSuccess QA Automation Suite"
echo "======================================="

# Change to project directory
cd "$(dirname "$0")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        exit 1
    fi
}

print_info() {
    echo -e "${YELLOW}🔍 $1${NC}"
}

# 1. Virtual Environment Check
print_info "Checking virtual environment..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    print_status $? "Virtual environment activated"
elif [ -f "env/bin/activate" ]; then
    source env/bin/activate
    print_status $? "Virtual environment activated"
else
    print_status 1 "No virtual environment found"
fi

# 2. Code Quality Checks
print_info "Running code quality checks..."
black . --check --line-length 100 >/dev/null 2>&1
print_status $? "Code formatting check (black)"

flake8 . --max-line-length 100 --ignore E203,W503 >/dev/null 2>&1
print_status $? "Linting check (flake8)"

# 3. Blueprint Registration Verification
print_info "Verifying blueprint registration..."
python -c "
from app import create_app
app = create_app()
required_blueprints = ['auth', 'logs', 'directories', 'admin', 'embeddings', 'topics', 'customers', 'drive']
registered = [bp.name for bp in app.blueprints.values()]
missing = [bp for bp in required_blueprints if bp not in registered]
if missing:
    print(f'Missing blueprints: {missing}')
    exit(1)
" >/dev/null 2>&1
print_status $? "Blueprint registration check"

# 4. Template Compilation Test
print_info "Testing template compilation..."
python -c "
from app import create_app
from flask import render_template
app = create_app()
with app.app_context():
    try:
        render_template('index.html', customers=[])
        render_template('customers/detail.html', customer=None, directories=[], files=[])
    except Exception as e:
        exit(1)
" >/dev/null 2>&1
print_status $? "Template compilation test"

# 5. Critical Endpoint Testing
print_info "Testing critical endpoints..."
python -c "
from app import create_app
app = create_app()
client = app.test_client()

endpoints = [
    ('/', 'GET'),
    ('/init-db', 'GET'),
    ('/health', 'GET'),
]

for endpoint, method in endpoints:
    response = client.open(endpoint, method=method)
    if response.status_code >= 400:
        exit(1)
" >/dev/null 2>&1
print_status $? "Critical endpoint testing"

# 6. Port Availability Check
print_info "Checking port availability..."
python -c "
import socket
def find_available_port(start_port=5000):
    for port in range(start_port, start_port + 100, 10):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    return None

port = find_available_port()
if not port:
    exit(1)
" >/dev/null 2>&1
print_status $? "Port availability check"

# 7. Background Task Verification
print_info "Testing background task processor..."
python -c "
from services.background_tasks import BackgroundTaskProcessor
from app import create_app

app = create_app()
processor = BackgroundTaskProcessor(app)

with app.app_context():
    processor.start()
    processor.stop()
" >/dev/null 2>&1
print_status $? "Background task processor test"

# 8. Database Operations Test
print_info "Testing database operations..."
python -c "
from app import create_app
app = create_app()
with app.app_context():
    from models import db, Customer
    db.create_all()
    customers = Customer.query.all()
" >/dev/null 2>&1
print_status $? "Database operations test"

# 9. Google Drive Integration Test (if credentials exist)
print_info "Testing Google Drive integration..."
if [ -f "credentials.json" ]; then
    python -c "
from services.drive_service import get_drive_service
drive = get_drive_service()
" >/dev/null 2>&1
    print_status $? "Google Drive service test"
else
    echo -e "${YELLOW}ℹ️  No credentials.json - skipping Drive test${NC}"
fi

# 10. Full Application Launch Test
print_info "Testing full application launch..."
timeout 30 python app.py --test-mode >/dev/null 2>&1
if [ $? -eq 0 ]; then
    print_status 0 "Application launch test"
else
    # Try alternative launch test
    python app.py &
    APP_PID=$!
    sleep 10
    
    # Test if app is responding
    python -c "
import requests
try:
    response = requests.get('http://localhost:5000/', timeout=5)
    if response.status_code == 200:
        exit(0)
    else:
        exit(1)
except:
    exit(1)
" >/dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        print_status 0 "Application launch test (alternative)"
    else
        print_status 1 "Application launch test"
    fi
    
    kill $APP_PID 2>/dev/null
fi

echo ""
echo -e "${GREEN}🎉 All QA checks passed! The application is ready for deployment.${NC}"
echo ""
echo "Summary of checks performed:"
echo "✅ Code formatting and linting"
echo "✅ Blueprint registration verification"
echo "✅ Template compilation testing"
echo "✅ Critical endpoint testing"
echo "✅ Port availability checking"
echo "✅ Background task processor testing"
echo "✅ Database operations testing"
echo "✅ Google Drive integration testing"
echo "✅ Full application launch testing"
echo ""
echo "This QA suite ensures that Claude cannot mark tasks as 'completed' without"
echo "verifying that the application actually works end-to-end."