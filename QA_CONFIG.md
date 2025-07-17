# QA Configuration for CustomerSuccess Flask Application

## Project-Specific QA Commands

### Flask Application Launch Test
```bash
# Activate virtual environment and test application launch
cd "/Users/arlonwilber/Library/CloudStorage/GoogleDrive-awilber@wiredtriangle.com/Shared drives/AW/Personal/Projects/CustomerSuccess"
source venv/bin/activate

# Test basic application launch (30 second timeout)
timeout 30 python app.py --test-mode || { echo "❌ Flask app failed to launch"; exit 1; }

# Alternative: Start app in background and test endpoint
python app.py &
APP_PID=$!
sleep 10
curl -f http://localhost:5000/ || { echo "❌ Flask endpoint failed"; kill $APP_PID; exit 1; }
kill $APP_PID
```

### Code Quality Checks
```bash
# Python-specific linting and formatting
black . --check --line-length 100
flake8 . --max-line-length 100 --ignore E203,W503
mypy . --ignore-missing-imports

# Fix formatting issues
black . --line-length 100
```

### Database and Template Verification
```bash
# Test database initialization
python -c "from app import create_app; app = create_app(); app.test_client().get('/init-db')"

# Test template compilation
python -c "
from app import create_app
from flask import render_template
app = create_app()
with app.app_context():
    render_template('index.html', customers=[])
    render_template('customers/detail.html', customer=None, directories=[], files=[])
"
```

### Blueprint Registration Verification
```bash
# Test that all required blueprints are registered
python -c "
from app import create_app
app = create_app()
required_blueprints = ['auth', 'logs', 'directories', 'admin', 'embeddings', 'topics', 'customers', 'drive']
registered = [bp.name for bp in app.blueprints.values()]
missing = [bp for bp in required_blueprints if bp not in registered]
if missing:
    print(f'❌ Missing blueprints: {missing}')
    exit(1)
else:
    print('✅ All blueprints registered')
"
```

### Port Management
```bash
# Check for port conflicts and find available port
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
if port:
    print(f'✅ Available port: {port}')
else:
    print('❌ No available ports found')
    exit(1)
"
```

### Critical Endpoint Testing
```bash
# Test critical application endpoints
python -c "
from app import create_app
app = create_app()
client = app.test_client()

# Test main routes
endpoints = [
    ('/', 'GET'),
    ('/init-db', 'GET'),
    ('/health', 'GET'),
]

for endpoint, method in endpoints:
    response = client.open(endpoint, method=method)
    if response.status_code >= 400:
        print(f'❌ {endpoint} failed: {response.status_code}')
        exit(1)
    else:
        print(f'✅ {endpoint} OK')
"
```

### Background Task Verification
```bash
# Test background task processor initialization
python -c "
from services.background_tasks import BackgroundTaskProcessor
from app import create_app

app = create_app()
processor = BackgroundTaskProcessor(app)

# Test that processor can be initialized with app context
with app.app_context():
    processor.start()
    print('✅ Background processor initialized')
    processor.stop()
"
```

### Google Drive Integration Test
```bash
# Test Google Drive service initialization (if credentials exist)
python -c "
import os
if os.path.exists('credentials.json'):
    from services.drive_service import get_drive_service
    drive = get_drive_service()
    print('✅ Google Drive service initialized')
else:
    print('ℹ️  No credentials.json - skipping Drive test')
"
```

## Pre-Commit Hook Script

Create `.git/hooks/pre-commit`:
```bash
#!/bin/sh
echo "🔄 Running CustomerSuccess QA checks..."

# Source the QA config
source "$(dirname "$0")/../../QA_CONFIG.md"

cd "$(git rev-parse --show-toplevel)"

# Run Flask-specific checks
if [ -f "app.py" ]; then
    source venv/bin/activate
    
    # Code quality
    black . --check --line-length 100 || { echo "❌ Code formatting failed"; exit 1; }
    
    # Blueprint verification
    python -c "
from app import create_app
app = create_app()
required_blueprints = ['auth', 'logs', 'directories', 'admin', 'embeddings', 'topics', 'customers', 'drive']
registered = [bp.name for bp in app.blueprints.values()]
missing = [bp for bp in required_blueprints if bp not in registered]
if missing:
    print(f'❌ Missing blueprints: {missing}')
    exit(1)
" || exit 1
    
    # Application launch test
    timeout 30 python app.py --test-mode || { echo "❌ Flask app failed to launch"; exit 1; }
    
    echo "✅ All QA checks passed"
fi
```

## Automated Todo Creation Template

For every code change, automatically create these QA verification todos:

1. **Code Quality**: Run black, flake8, mypy
2. **Blueprint Verification**: Check all required blueprints registered
3. **Database Test**: Verify database initialization works
4. **Template Compilation**: Test all templates render without errors
5. **Port Management**: Verify port availability and conflicts
6. **Application Launch**: Test Flask app starts successfully
7. **Endpoint Testing**: Verify critical routes respond correctly
8. **Background Tasks**: Test background processor initialization
9. **Integration Tests**: Test Google Drive and other services
10. **Full End-to-End**: Complete user workflow testing

## Integration with Utils

### WebTester Integration
```bash
# Run comprehensive UI tests
cd ../utils/WebTester
npm run test:smoke -- --base-url http://localhost:5000 --project CustomerSuccess
```

### App Status Checker Integration
```bash
# Verify application health
cd ../utils/app-status-checker
node index.js --project-root "$PWD" --format json --flask-port 5000
```

### Port Manager Integration
```bash
# Handle port conflicts intelligently
cd ../utils/port-manager
node index.js --check-ports 5000,5010,5020 --project CustomerSuccess
```

This configuration ensures the blueprint registration error and similar issues are caught automatically before code can be considered complete.