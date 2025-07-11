from flask import Flask, render_template, redirect, url_for
from flask_cors import CORS
from config import Config
from models import db, Customer, Person, EmailThread, FileReference
from datetime import datetime
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions
    db.init_app(app)
    CORS(app)
    
    # Create upload directory
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'google_takeout'), exist_ok=True)
    
    return app

app = create_app()

# Set up logging (temporarily disabled to debug)
# from services.logger import setup_logging
# console_handler = setup_logging(app)

# Import routes after app creation to avoid circular imports
from routes import customers, uploads, analytics, imports, drive, insights, directories, auth

app.register_blueprint(auth.bp)
app.register_blueprint(customers.bp)
app.register_blueprint(uploads.bp)
app.register_blueprint(analytics.bp)
app.register_blueprint(imports.bp)
app.register_blueprint(drive.bp)
app.register_blueprint(insights.bp)
app.register_blueprint(directories.bp)
# app.register_blueprint(logs.bp)

# Start background processor
from services.background_tasks import background_processor
background_processor.start()

# Global authentication check
@app.before_request
def require_login():
    from flask import session, request
    # Skip authentication for login/logout routes
    if request.endpoint and (request.endpoint.startswith('auth.') or request.endpoint == 'static'):
        return
    
    # Check if user is authenticated
    if not session.get('authenticated'):
        return redirect(url_for('auth.login', next=request.url))

@app.route('/')
def index():
    return render_template('index.html', customers=Customer.query.all())

@app.route('/init-db')
def init_db():
    with app.app_context():
        db.create_all()
        
        # Create default customer if none exists
        if Customer.query.count() == 0:
            hcr = Customer(
                name='HCR',
                company='Heller-Coley-Reed'
            )
            db.session.add(hcr)
            
            # Add default people
            people = [
                Person(name='Cameron', email='cameron@wiredtriangle.com', side='us', customer=hcr, color='#3B82F6'),
                Person(name='Arlon', email='awilber@wiredtriangle.com', side='us', customer=hcr, color='#2563EB'),
                Person(name='Kathlene', email='kathlene@hcr.com', side='customer', customer=hcr, color='#10B981'),
                Person(name='Leigh', email='leigh@hcr.com', side='customer', customer=hcr, color='#059669'),
            ]
            for person in people:
                db.session.add(person)
            
            db.session.commit()
            
    return redirect(url_for('index'))

@app.template_filter('datetime')
def datetime_filter(date):
    if date:
        return date.strftime('%Y-%m-%d %I:%M %p')
    return ''

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # Check if port is available, starting from 5010 to avoid AirPlay on 5000
    import socket
    port = int(os.environ.get('PORT', 5010))
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('', port))
            s.close()
            break
        except OSError:
            port += 10
            if port > 5100:
                print("No available ports found")
                exit(1)
    
    print(f"Starting CustomerSuccess app on port {port}")
    app.run(debug=True, port=port)