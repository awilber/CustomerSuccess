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
    topics = db.relationship('Topic', secondary='customer_topic', backref='customers')
    
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
    
    # Embeddings and processing
    embedding = db.Column(db.Text)  # JSON array of floats
    embedding_model = db.Column(db.String(100))  # Model used for embedding
    has_embedding = db.Column(db.Boolean, default=False)  # Quick lookup
    embedding_processed_at = db.Column(db.DateTime)
    embedding_error = db.Column(db.Text)
    
    # Topics extracted from embeddings
    main_topics = db.Column(db.Text)  # JSON array of main topics
    sub_topics = db.Column(db.Text)  # JSON array of sub topics
    topics_extracted_at = db.Column(db.DateTime)
    topics_extraction_error = db.Column(db.Text)
    
    def __repr__(self):
        return f'<EmailThread {self.subject[:50]}...>'
    
    @property
    def sender_side(self):
        # Determine if sender is 'us' or 'customer' based on email domain
        our_domains = ['wiredtriangle.com', 'knewvantage.com']  # Updated domains
        if self.sender_email:
            domain = self.sender_email.split('@')[-1].lower()
            return 'us' if domain in our_domains else 'customer'
        return 'unknown'
    
    @property
    def involves_our_domain(self):
        """Check if email involves our domain (@wiredtriangle.com or @knewvantage.com)"""
        our_domains = ['wiredtriangle.com', 'knewvantage.com']
        sender_domain = self.sender_email.split('@')[-1].lower() if self.sender_email else ''
        recipient_domain = self.recipient_email.split('@')[-1].lower() if self.recipient_email else ''
        return sender_domain in our_domains or recipient_domain in our_domains

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

class Topic(db.Model):
    """Hierarchical topic structure for email classification"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Hierarchy
    parent_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=True)
    level = db.Column(db.Integer, default=0)  # 0=main, 1=sub, 2=micro
    
    # Classification metadata
    keywords = db.Column(db.Text)  # JSON array of keywords
    color = db.Column(db.String(7), default='#6B7280')  # Hex color for visualization
    
    # Auto-generation metadata
    auto_generated = db.Column(db.Boolean, default=False)  # True if generated by AI
    confidence_score = db.Column(db.Float, default=0.0)  # Confidence in topic classification
    
    # Usage statistics
    email_count = db.Column(db.Integer, default=0)  # Cached count of associated emails
    last_used = db.Column(db.DateTime)  # Last time topic was assigned
    
    # Status and management
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))  # User who created the topic
    
    # Self-referential relationship for hierarchy
    parent = db.relationship('Topic', remote_side=[id], backref='children')
    
    def __repr__(self):
        return f'<Topic {self.name} (Level {self.level})>'
    
    @property
    def full_path(self):
        """Get full hierarchical path (e.g., 'Real Estate > Residential > Pricing')"""
        path = []
        current = self
        while current:
            path.append(current.name)
            current = current.parent
        return ' > '.join(reversed(path))
    
    @property
    def is_main_topic(self):
        """Check if this is a main topic (level 0)"""
        return self.level == 0
    
    @property
    def is_sub_topic(self):
        """Check if this is a sub topic (level 1)"""
        return self.level == 1
    
    @property
    def is_micro_topic(self):
        """Check if this is a micro topic (level 2)"""
        return self.level == 2
    
    def get_descendants(self):
        """Get all descendant topics (children, grandchildren, etc.)"""
        descendants = []
        for child in self.children:
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants
    
    def get_ancestors(self):
        """Get all ancestor topics (parent, grandparent, etc.)"""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors
    
    def to_dict(self, include_hierarchy=True):
        """Convert topic to dictionary for JSON serialization"""
        result = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'level': self.level,
            'color': self.color,
            'email_count': self.email_count,
            'is_active': self.is_active,
            'auto_generated': self.auto_generated,
            'confidence_score': self.confidence_score,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_hierarchy:
            result['parent_id'] = self.parent_id
            result['full_path'] = self.full_path
            result['children'] = [child.to_dict(include_hierarchy=False) for child in self.children]
        
        return result

class EmailTopic(db.Model):
    """Many-to-many relationship between emails and topics with confidence scoring"""
    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey('email_thread.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    
    # Classification metadata
    confidence_score = db.Column(db.Float, default=0.0)  # 0.0-1.0 confidence in classification
    classification_method = db.Column(db.String(50))  # 'manual', 'embedding', 'keyword', 'ml'
    
    # Assignment metadata
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_by = db.Column(db.String(100))  # User who assigned (or 'system' for auto)
    
    # Validation
    is_verified = db.Column(db.Boolean, default=False)  # Manual verification by user
    verified_at = db.Column(db.DateTime)
    verified_by = db.Column(db.String(100))
    
    # Relationships
    email = db.relationship('EmailThread', backref='topic_assignments')
    topic = db.relationship('Topic', backref='email_assignments')
    
    # Unique constraint to prevent duplicate assignments
    __table_args__ = (db.UniqueConstraint('email_id', 'topic_id', name='unique_email_topic'),)
    
    def __repr__(self):
        return f'<EmailTopic Email:{self.email_id} Topic:{self.topic_id} Confidence:{self.confidence_score:.2f}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'email_id': self.email_id,
            'topic_id': self.topic_id,
            'confidence_score': self.confidence_score,
            'classification_method': self.classification_method,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
            'assigned_by': self.assigned_by,
            'is_verified': self.is_verified,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'verified_by': self.verified_by,
            'topic': self.topic.to_dict(include_hierarchy=False) if self.topic else None
        }

class TopicKeyword(db.Model):
    """Keywords associated with topics for automatic classification"""
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    keyword = db.Column(db.String(100), nullable=False)
    weight = db.Column(db.Float, default=1.0)  # Weight for classification scoring
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100))
    
    # Performance tracking
    match_count = db.Column(db.Integer, default=0)  # How many times this keyword matched
    last_matched = db.Column(db.DateTime)
    
    # Relationships
    topic = db.relationship('Topic', backref='keywords_rel')
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('topic_id', 'keyword', name='unique_topic_keyword'),)
    
    def __repr__(self):
        return f'<TopicKeyword "{self.keyword}" for {self.topic.name if self.topic else "Unknown"}>'

class TopicSimilarity(db.Model):
    """Tracks similarity between topics for clustering and recommendation"""
    id = db.Column(db.Integer, primary_key=True)
    topic1_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    topic2_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    similarity_score = db.Column(db.Float, nullable=False)  # 0.0-1.0
    
    # Calculation metadata
    calculation_method = db.Column(db.String(50))  # 'embedding', 'keyword', 'cooccurrence'
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    topic1 = db.relationship('Topic', foreign_keys=[topic1_id], backref='similarities_as_topic1')
    topic2 = db.relationship('Topic', foreign_keys=[topic2_id], backref='similarities_as_topic2')
    
    # Unique constraint and ensure topic1_id < topic2_id to avoid duplicates
    __table_args__ = (db.UniqueConstraint('topic1_id', 'topic2_id', name='unique_topic_similarity'),)
    
    def __repr__(self):
        return f'<TopicSimilarity {self.topic1_id}↔{self.topic2_id} ({self.similarity_score:.2f})>'

# Association table for customer-topic many-to-many relationship
customer_topic = db.Table('customer_topic',
    db.Column('customer_id', db.Integer, db.ForeignKey('customer.id'), primary_key=True),
    db.Column('topic_id', db.Integer, db.ForeignKey('topic.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)