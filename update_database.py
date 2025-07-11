#!/usr/bin/env python3
"""
Database migration script to add new columns to existing tables
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

print("Starting database migration...")

# Check if columns already exist
cursor.execute("PRAGMA table_info(directory_link)")
columns = [column[1] for column in cursor.fetchall()]

migrations = []

# Add new columns to directory_link table
if 'link_type' not in columns:
    migrations.append("ALTER TABLE directory_link ADD COLUMN link_type VARCHAR(20) DEFAULT 'local'")
    print("Adding link_type column...")

if 'drive_id' not in columns:
    migrations.append("ALTER TABLE directory_link ADD COLUMN drive_id VARCHAR(200)")
    print("Adding drive_id column...")

if 'folder_id' not in columns:
    migrations.append("ALTER TABLE directory_link ADD COLUMN folder_id VARCHAR(200)")
    print("Adding folder_id column...")

# Execute migrations
for migration in migrations:
    try:
        cursor.execute(migration)
        print(f"✓ Executed: {migration}")
    except sqlite3.OperationalError as e:
        print(f"✗ Failed: {migration} - {e}")

# Commit changes
conn.commit()
print(f"\nMigration completed. {len(migrations)} changes applied.")

# Verify changes
cursor.execute("PRAGMA table_info(directory_link)")
print("\nCurrent directory_link schema:")
for column in cursor.fetchall():
    print(f"  - {column[1]} ({column[2]})")

conn.close()