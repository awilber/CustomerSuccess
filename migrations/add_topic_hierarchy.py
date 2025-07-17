#!/usr/bin/env python3
"""
Migration script to add topic hierarchy tables to the database.
This script adds the new topic-related tables for hierarchical topic management.
"""

import sqlite3
import os
from datetime import datetime

def get_db_path():
    """Get the database path"""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database.db')

def create_topic_tables():
    """Create the new topic hierarchy tables"""
    
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create Topic table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS topic (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(200) NOT NULL,
                description TEXT,
                parent_id INTEGER,
                level INTEGER DEFAULT 0,
                keywords TEXT,
                color VARCHAR(7) DEFAULT '#6B7280',
                auto_generated BOOLEAN DEFAULT FALSE,
                confidence_score REAL DEFAULT 0.0,
                email_count INTEGER DEFAULT 0,
                last_used DATETIME,
                is_active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by VARCHAR(100),
                FOREIGN KEY (parent_id) REFERENCES topic(id)
            )
        ''')
        
        # Create EmailTopic table (many-to-many with confidence scoring)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_topic (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER NOT NULL,
                topic_id INTEGER NOT NULL,
                confidence_score REAL DEFAULT 0.0,
                classification_method VARCHAR(50),
                assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                assigned_by VARCHAR(100),
                is_verified BOOLEAN DEFAULT FALSE,
                verified_at DATETIME,
                verified_by VARCHAR(100),
                FOREIGN KEY (email_id) REFERENCES email_thread(id),
                FOREIGN KEY (topic_id) REFERENCES topic(id),
                UNIQUE(email_id, topic_id)
            )
        ''')
        
        # Create TopicKeyword table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS topic_keyword (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id INTEGER NOT NULL,
                keyword VARCHAR(100) NOT NULL,
                weight REAL DEFAULT 1.0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by VARCHAR(100),
                match_count INTEGER DEFAULT 0,
                last_matched DATETIME,
                FOREIGN KEY (topic_id) REFERENCES topic(id),
                UNIQUE(topic_id, keyword)
            )
        ''')
        
        # Create TopicSimilarity table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS topic_similarity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic1_id INTEGER NOT NULL,
                topic2_id INTEGER NOT NULL,
                similarity_score REAL NOT NULL,
                calculation_method VARCHAR(50),
                calculated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (topic1_id) REFERENCES topic(id),
                FOREIGN KEY (topic2_id) REFERENCES topic(id),
                UNIQUE(topic1_id, topic2_id)
            )
        ''')
        
        # Create customer_topic association table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customer_topic (
                customer_id INTEGER NOT NULL,
                topic_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (customer_id, topic_id),
                FOREIGN KEY (customer_id) REFERENCES customer(id),
                FOREIGN KEY (topic_id) REFERENCES topic(id)
            )
        ''')
        
        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_topic_parent ON topic(parent_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_topic_level ON topic(level)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_topic_active ON topic(is_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_topic_email ON email_topic(email_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_topic_topic ON email_topic(topic_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_topic_confidence ON email_topic(confidence_score)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_topic_keyword_topic ON topic_keyword(topic_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_topic_keyword_keyword ON topic_keyword(keyword)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_topic_similarity_score ON topic_similarity(similarity_score)')
        
        conn.commit()
        print("✓ Topic hierarchy tables created successfully")
        
        # Insert some sample main topics
        sample_topics = [
            ('Real Estate', 'General real estate related communications', 0, '#10B981'),
            ('Property Management', 'Property management and maintenance topics', 0, '#3B82F6'),
            ('Client Relations', 'Client communication and relationship management', 0, '#8B5CF6'),
            ('Market Analysis', 'Market research and analysis discussions', 0, '#F59E0B'),
            ('Legal & Compliance', 'Legal matters and compliance issues', 0, '#EF4444'),
            ('Financial', 'Financial discussions and transactions', 0, '#06B6D4'),
            ('Technology', 'Technology and system related topics', 0, '#84CC16'),
            ('Marketing', 'Marketing and promotional activities', 0, '#EC4899')
        ]
        
        for name, description, level, color in sample_topics:
            cursor.execute('''
                INSERT OR IGNORE INTO topic (name, description, level, color, auto_generated, created_by)
                VALUES (?, ?, ?, ?, TRUE, 'system')
            ''', (name, description, level, color))
        
        # Insert some sample sub-topics
        cursor.execute('SELECT id, name FROM topic WHERE level = 0')
        main_topics = cursor.fetchall()
        
        sub_topics = {
            'Real Estate': [
                ('Residential Sales', 'Single family home sales and listings'),
                ('Commercial Properties', 'Commercial real estate transactions'),
                ('Property Valuations', 'Property appraisals and valuations'),
                ('Market Listings', 'New property listings and updates')
            ],
            'Client Relations': [
                ('Initial Consultations', 'First meetings with potential clients'),
                ('Follow-ups', 'Follow-up communications with clients'),
                ('Feedback', 'Client feedback and reviews'),
                ('Referrals', 'Client referrals and recommendations')
            ],
            'Market Analysis': [
                ('Price Trends', 'Market price trends and analysis'),
                ('Competitive Analysis', 'Competitor analysis and positioning'),
                ('Market Reports', 'Market research reports and insights'),
                ('Forecasting', 'Market forecasts and predictions')
            ],
            'Financial': [
                ('Commission Tracking', 'Commission calculations and tracking'),
                ('Expense Reports', 'Business expense reporting'),
                ('Tax Matters', 'Tax-related financial discussions'),
                ('Investment Analysis', 'Investment opportunity analysis')
            ]
        }
        
        for topic_id, topic_name in main_topics:
            if topic_name in sub_topics:
                for sub_name, sub_description in sub_topics[topic_name]:
                    cursor.execute('''
                        INSERT OR IGNORE INTO topic (name, description, parent_id, level, auto_generated, created_by)
                        VALUES (?, ?, ?, 1, TRUE, 'system')
                    ''', (sub_name, sub_description, topic_id))
        
        conn.commit()
        print("✓ Sample topic hierarchy created successfully")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Error creating topic tables: {e}")
        raise
    finally:
        conn.close()

def migrate_existing_topics():
    """Migrate existing JSON topic data to the new structure"""
    
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Get emails with existing topic data
        cursor.execute('''
            SELECT id, main_topics, sub_topics, customer_id 
            FROM email_thread 
            WHERE main_topics IS NOT NULL OR sub_topics IS NOT NULL
        ''')
        
        emails_with_topics = cursor.fetchall()
        
        if not emails_with_topics:
            print("No existing topic data found to migrate")
            return
        
        print(f"Found {len(emails_with_topics)} emails with topic data to migrate")
        
        import json
        
        # Process each email
        for email_id, main_topics_json, sub_topics_json, customer_id in emails_with_topics:
            try:
                # Parse main topics
                if main_topics_json:
                    main_topics = json.loads(main_topics_json)
                    for topic_data in main_topics:
                        topic_name = topic_data.get('name', '')
                        confidence = topic_data.get('count', 0) / 100.0  # Convert count to confidence
                        
                        if topic_name:
                            # Find or create topic
                            cursor.execute('SELECT id FROM topic WHERE name = ? AND level = 0', (topic_name,))
                            topic_row = cursor.fetchone()
                            
                            if not topic_row:
                                # Create new main topic
                                cursor.execute('''
                                    INSERT INTO topic (name, level, auto_generated, created_by, email_count)
                                    VALUES (?, 0, TRUE, 'migration', 1)
                                ''', (topic_name,))
                                topic_id = cursor.lastrowid
                            else:
                                topic_id = topic_row[0]
                                # Update email count
                                cursor.execute('''
                                    UPDATE topic SET email_count = email_count + 1
                                    WHERE id = ?
                                ''', (topic_id,))
                            
                            # Create email-topic association
                            cursor.execute('''
                                INSERT OR IGNORE INTO email_topic 
                                (email_id, topic_id, confidence_score, classification_method, assigned_by)
                                VALUES (?, ?, ?, 'migration', 'system')
                            ''', (email_id, topic_id, min(confidence, 1.0)))
                
                # Parse sub topics
                if sub_topics_json:
                    sub_topics = json.loads(sub_topics_json)
                    for topic_data in sub_topics:
                        topic_name = topic_data.get('name', '')
                        confidence = topic_data.get('count', 0) / 100.0
                        
                        if topic_name:
                            # Find or create topic
                            cursor.execute('SELECT id FROM topic WHERE name = ? AND level = 1', (topic_name,))
                            topic_row = cursor.fetchone()
                            
                            if not topic_row:
                                # Create new sub topic
                                cursor.execute('''
                                    INSERT INTO topic (name, level, auto_generated, created_by, email_count)
                                    VALUES (?, 1, TRUE, 'migration', 1)
                                ''', (topic_name,))
                                topic_id = cursor.lastrowid
                            else:
                                topic_id = topic_row[0]
                                # Update email count
                                cursor.execute('''
                                    UPDATE topic SET email_count = email_count + 1
                                    WHERE id = ?
                                ''', (topic_id,))
                            
                            # Create email-topic association
                            cursor.execute('''
                                INSERT OR IGNORE INTO email_topic 
                                (email_id, topic_id, confidence_score, classification_method, assigned_by)
                                VALUES (?, ?, ?, 'migration', 'system')
                            ''', (email_id, topic_id, min(confidence, 1.0)))
                
            except json.JSONDecodeError:
                print(f"Warning: Could not parse topic data for email {email_id}")
                continue
            except Exception as e:
                print(f"Warning: Error processing email {email_id}: {e}")
                continue
        
        conn.commit()
        print("✓ Existing topic data migrated successfully")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Error migrating existing topics: {e}")
        raise
    finally:
        conn.close()

def main():
    """Run the migration"""
    print("Starting topic hierarchy migration...")
    
    try:
        create_topic_tables()
        migrate_existing_topics()
        print("\n✓ Topic hierarchy migration completed successfully!")
        print("\nNew tables created:")
        print("- topic (hierarchical topic structure)")
        print("- email_topic (many-to-many email-topic relationships)")
        print("- topic_keyword (keywords for automatic classification)")
        print("- topic_similarity (topic similarity scoring)")
        print("- customer_topic (customer-topic associations)")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())