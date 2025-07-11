#!/usr/bin/env python3
"""
Database migration script to add tags and email_tags tables
"""

import sqlite3
import os
from datetime import datetime

# Get database path
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'database.db')

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

# Connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Starting tags migration...")

# Create tag table
try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tag (
            id INTEGER PRIMARY KEY,
            name VARCHAR(50) NOT NULL UNIQUE,
            color VARCHAR(7) DEFAULT '#6B7280',
            category VARCHAR(50),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✓ Created tag table")
except sqlite3.OperationalError as e:
    print(f"✗ Failed to create tag table: {e}")

# Create email_tag table
try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_tag (
            id INTEGER PRIMARY KEY,
            email_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(100),
            FOREIGN KEY (email_id) REFERENCES email_thread (id),
            FOREIGN KEY (tag_id) REFERENCES tag (id),
            UNIQUE(email_id, tag_id)
        )
    """)
    print("✓ Created email_tag table")
except sqlite3.OperationalError as e:
    print(f"✗ Failed to create email_tag table: {e}")

# Insert default tags
default_tags = [
    ('Contract', '#7C3AED', 'topic'),
    ('Technical', '#EF4444', 'topic'),
    ('Payment', '#10B981', 'topic'),
    ('Feature Request', '#3B82F6', 'topic'),
    ('Meeting', '#F59E0B', 'topic'),
    ('Timeline', '#EC4899', 'topic'),
    ('Urgent', '#DC2626', 'priority'),
    ('High Priority', '#F59E0B', 'priority'),
    ('Normal', '#6B7280', 'priority'),
    ('Resolved', '#10B981', 'status'),
    ('In Progress', '#3B82F6', 'status'),
    ('Pending', '#F59E0B', 'status'),
    ('Blocked', '#EF4444', 'status')
]

for name, color, category in default_tags:
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO tag (name, color, category) VALUES (?, ?, ?)",
            (name, color, category)
        )
    except sqlite3.Error as e:
        print(f"Failed to insert tag {name}: {e}")

# Create indexes for better performance
try:
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_tag_email_id ON email_tag(email_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_tag_tag_id ON email_tag(tag_id)")
    print("✓ Created indexes")
except sqlite3.OperationalError as e:
    print(f"✗ Failed to create indexes: {e}")

# Commit changes
conn.commit()
print(f"\nMigration completed. Inserted {len(default_tags)} default tags.")

# Verify tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('tag', 'email_tag')")
tables = cursor.fetchall()
print(f"\nCreated tables: {[t[0] for t in tables]}")

# Show tag count
cursor.execute("SELECT COUNT(*) FROM tag")
tag_count = cursor.fetchone()[0]
print(f"Total tags in database: {tag_count}")

conn.close()