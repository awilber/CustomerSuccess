import os
import email
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from models import db, EmailThread, Customer
import mimetypes
import json
from services.logger import log_event

def parse_google_takeout(extract_path, customer_id):
    """Parse Google Takeout export and extract emails"""
    email_count = 0
    log_event('info', f'Starting Google Takeout parse from {extract_path}')
    
    # Look for mbox files in the extracted directory
    mbox_files = []
    for root, dirs, files in os.walk(extract_path):
        for file in files:
            if file.endswith('.mbox'):
                mbox_files.append(os.path.join(root, file))
    
    log_event('info', f'Found {len(mbox_files)} MBOX files to process')
    
    for i, filepath in enumerate(mbox_files):
        log_event('info', f'Processing MBOX file {i+1}/{len(mbox_files)}: {os.path.basename(filepath)}')
        count = parse_mbox_file(filepath, customer_id)
        email_count += count
    
    # Also look for .json files with email metadata
    for root, dirs, files in os.walk(extract_path):
        for file in files:
            if file.endswith('.json') and 'mail' in file.lower():
                filepath = os.path.join(root, file)
                count = parse_json_emails(filepath, customer_id)
                email_count += count
    
    return email_count

def parse_mbox_file(filepath, customer_id):
    """Parse an mbox file and extract emails"""
    email_count = 0
    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
    log_event('info', f'Starting to parse MBOX file: {os.path.basename(filepath)} ({file_size_mb:.1f} MB)')
    
    try:
        with open(filepath, 'rb') as f:
            # Read the entire file content
            content = f.read()
            
        # Split by 'From ' at the beginning of a line (mbox format)
        messages = content.split(b'\nFrom ')
        
        for i, raw_message in enumerate(messages):
            if i == 0 and not raw_message.startswith(b'From '):
                continue
                
            try:
                # Parse the email message
                if i > 0:
                    raw_message = b'From ' + raw_message
                    
                msg = email.message_from_bytes(raw_message)
                
                # Extract email metadata
                email_data = extract_email_data(msg)
                
                if email_data:
                    # Check if email already exists
                    existing = EmailThread.query.filter_by(
                        message_id=email_data['message_id']
                    ).first()
                    
                    if not existing:
                        email_thread = EmailThread(
                            customer_id=customer_id,
                            subject=email_data['subject'],
                            date=email_data['date'],
                            sender_name=email_data['sender_name'],
                            sender_email=email_data['sender_email'],
                            recipient_name=email_data['recipient_name'],
                            recipient_email=email_data['recipient_email'],
                            body_preview=email_data['body_preview'],
                            body_full=email_data['body_full'],
                            message_id=email_data['message_id'],
                            takeout_file=os.path.basename(filepath)
                        )
                        db.session.add(email_thread)
                        email_count += 1
                        
                        if email_count % 100 == 0:
                            log_event('info', f'Processed {email_count} emails from {os.path.basename(filepath)}')
                            db.session.commit()  # Commit in batches
                        
            except Exception as e:
                log_event('warning', f'Error parsing message: {str(e)}')
                continue
        
        db.session.commit()
        log_event('info', f'Successfully imported {email_count} emails from {os.path.basename(filepath)}')
        
    except Exception as e:
        log_event('error', f'Error reading mbox file {filepath}: {str(e)}')
    
    return email_count

def parse_json_emails(filepath, customer_id):
    """Parse JSON format email exports"""
    email_count = 0
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle different JSON structures
        emails = []
        if isinstance(data, list):
            emails = data
        elif isinstance(data, dict) and 'messages' in data:
            emails = data['messages']
        
        for email_data in emails:
            try:
                # Extract relevant fields
                date = datetime.fromisoformat(email_data.get('date', ''))
                
                email_thread = EmailThread(
                    customer_id=customer_id,
                    subject=email_data.get('subject', 'No Subject'),
                    date=date,
                    sender_name=email_data.get('from', {}).get('name', ''),
                    sender_email=email_data.get('from', {}).get('email', ''),
                    recipient_name=email_data.get('to', [{}])[0].get('name', ''),
                    recipient_email=email_data.get('to', [{}])[0].get('email', ''),
                    body_preview=email_data.get('snippet', '')[:500],
                    body_full=email_data.get('body', ''),
                    message_id=email_data.get('id', ''),
                    takeout_file=os.path.basename(filepath)
                )
                
                # Check if email already exists
                existing = EmailThread.query.filter_by(
                    message_id=email_thread.message_id
                ).first()
                
                if not existing and email_thread.message_id:
                    db.session.add(email_thread)
                    email_count += 1
                    
            except Exception as e:
                print(f"Error parsing JSON email: {str(e)}")
                continue
        
        db.session.commit()
        
    except Exception as e:
        print(f"Error reading JSON file: {str(e)}")
    
    return email_count

def extract_email_data(msg):
    """Extract relevant data from an email message"""
    try:
        # Get basic headers
        subject = msg.get('Subject', 'No Subject')
        message_id = msg.get('Message-ID', '')
        
        # Parse date
        date_str = msg.get('Date', '')
        try:
            date = parsedate_to_datetime(date_str)
        except:
            date = datetime.utcnow()
        
        # Parse sender
        from_header = msg.get('From', '')
        sender_name, sender_email = parse_email_address(from_header)
        
        # Parse recipient
        to_header = msg.get('To', '')
        recipient_name, recipient_email = parse_email_address(to_header)
        
        # Extract body
        body = extract_body(msg)
        body_preview = body[:500] if body else ''
        
        return {
            'subject': subject,
            'date': date,
            'sender_name': sender_name,
            'sender_email': sender_email,
            'recipient_name': recipient_name,
            'recipient_email': recipient_email,
            'body_preview': body_preview,
            'body_full': body,
            'message_id': message_id
        }
        
    except Exception as e:
        print(f"Error extracting email data: {str(e)}")
        return None

def parse_email_address(header):
    """Parse email address from header"""
    if not header:
        return '', ''
    
    # Regular expression to extract name and email
    match = re.match(r'^"?([^"<]+)"?\s*<?([^>]+)>?$', header.strip())
    if match:
        name = match.group(1).strip()
        email_addr = match.group(2).strip()
        return name, email_addr
    
    # If no match, assume the whole thing is an email
    return '', header.strip()

def extract_body(msg):
    """Extract body text from email message"""
    body = ''
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == 'text/plain':
                try:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
                except:
                    continue
            elif content_type == 'text/html' and not body:
                try:
                    html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    # Simple HTML to text conversion
                    body = re.sub('<[^<]+?>', '', html_body)
                except:
                    continue
    else:
        try:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        except:
            body = str(msg.get_payload())
    
    return body.strip()