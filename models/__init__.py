from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    company = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    people = db.relationship('Person', backref='customer', lazy='dynamic')
    email_threads = db.relationship('EmailThread', backref='customer', lazy='dynamic')
    file_references = db.relationship('FileReference', backref='customer', lazy='dynamic')
    
    def __repr__(self):
        return f'<Customer {self.name}>'

class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    side = db.Column(db.String(20), nullable=False)  # 'us' or 'customer'
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    color = db.Column(db.String(7))  # Hex color for timeline
    
    def __repr__(self):
        return f'<Person {self.name} ({self.side})>'

class EmailThread(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    subject = db.Column(db.String(500))
    date = db.Column(db.DateTime, nullable=False)
    sender_name = db.Column(db.String(100))
    sender_email = db.Column(db.String(100))
    recipient_name = db.Column(db.String(100))
    recipient_email = db.Column(db.String(100))
    body_preview = db.Column(db.Text)  # First 500 chars
    body_full = db.Column(db.Text)
    takeout_file = db.Column(db.String(200))
    message_id = db.Column(db.String(200), unique=True)
    
    def __repr__(self):
        return f'<EmailThread {self.subject[:50]}...>'
    
    @property
    def sender_side(self):
        # Determine if sender is 'us' or 'customer' based on email domain
        our_domains = ['wiredtriangle.com', 'gmail.com']  # Add your domains
        if self.sender_email:
            domain = self.sender_email.split('@')[-1].lower()
            return 'us' if domain in our_domains else 'customer'
        return 'unknown'

class FileReference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    drive_id = db.Column(db.String(200))
    file_name = db.Column(db.String(500), nullable=False)
    file_path = db.Column(db.String(1000))
    mime_type = db.Column(db.String(100))
    size_bytes = db.Column(db.Integer)
    last_modified = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Enhanced metadata
    content_hash = db.Column(db.String(64))  # SHA256 hash
    created_by = db.Column(db.String(200))
    created_date = db.Column(db.DateTime)
    file_type = db.Column(db.String(50))  # Detailed file type
    topic = db.Column(db.String(200))  # Auto-detected topic
    importance_score = db.Column(db.Float, default=0.0)  # Calculated importance
    
    # Embeddings and analysis
    embedding = db.Column(db.Text)  # JSON array of floats
    summary = db.Column(db.Text)  # AI-generated summary
    keywords = db.Column(db.Text)  # JSON array of keywords
    
    # Processing status
    processing_status = db.Column(db.String(50), default='pending')  # pending, processing, completed, error
    processed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    
    # Relationships
    correlations = db.relationship('FileEmailCorrelation', backref='file', lazy='dynamic')
    
    def __repr__(self):
        return f'<FileReference {self.file_name}>'

class FileEmailCorrelation(db.Model):
    """Tracks correlations between files and email threads"""
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('file_reference.id'), nullable=False)
    email_id = db.Column(db.Integer, db.ForeignKey('email_thread.id'), nullable=False)
    correlation_score = db.Column(db.Float)  # Strength of correlation
    correlation_type = db.Column(db.String(50))  # mention, attachment, topic, timeline
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to email
    email = db.relationship('EmailThread', backref='file_correlations')

class DirectoryLink(db.Model):
    """Tracks linked directories for monitoring"""
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    path = db.Column(db.String(1000), nullable=True)  # Nullable for Drive directories
    name = db.Column(db.String(200))
    scan_status = db.Column(db.String(50), default='pending')
    last_scanned = db.Column(db.DateTime)
    file_count = db.Column(db.Integer, default=0)
    total_size = db.Column(db.BigInteger, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Google Drive specific fields
    link_type = db.Column(db.String(20), default='local')  # 'local' or 'drive'
    drive_id = db.Column(db.String(200))  # For Google Drive folders
    folder_id = db.Column(db.String(200))  # Specific folder within a drive
    
    # Relationship
    customer = db.relationship('Customer', backref='directory_links')

class Tag(db.Model):
    """Tags for categorizing emails and files"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    color = db.Column(db.String(7), default='#6B7280')  # Hex color
    category = db.Column(db.String(50))  # e.g., 'topic', 'status', 'priority'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'category': self.category
        }

class EmailTag(db.Model):
    """Many-to-many relationship between emails and tags"""
    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey('email_thread.id'), nullable=False)
    tag_id = db.Column(db.Integer, db.ForeignKey('tag.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100))  # User who added the tag
    
    # Relationships
    email = db.relationship('EmailThread', backref='email_tags')
    tag = db.relationship('Tag', backref='email_tags')