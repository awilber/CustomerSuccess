import re
from datetime import datetime, timedelta
from collections import defaultdict
from models import db, EmailThread, Customer, Person
from sqlalchemy import func, or_, and_
import json

class InsightsService:
    def __init__(self):
        self.topic_keywords = {
            'contract': ['contract', 'agreement', 'terms', 'clause', 'negotiation', 'pricing', 'renewal'],
            'technical': ['bug', 'issue', 'error', 'problem', 'fix', 'broken', 'not working', 'crash'],
            'feature': ['feature', 'request', 'enhancement', 'improvement', 'add', 'new functionality'],
            'meeting': ['meeting', 'call', 'discussion', 'agenda', 'schedule', 'conference'],
            'delivery': ['delivery', 'timeline', 'deadline', 'milestone', 'completion', 'progress'],
            'payment': ['payment', 'invoice', 'billing', 'charge', 'fee', 'cost'],
        }
    
    def search_context(self, customer_id, query, search_mode='strict'):
        """Search emails for context around a specific query
        
        Args:
            customer_id: Customer ID to search within
            query: Search query
            search_mode: 'strict' (exact matches only), 'related' (include related terms), 'fuzzy' (broader matching)
        """
        # Get all emails for the customer
        emails = EmailThread.query.filter_by(customer_id=customer_id).all()
        
        # Filter emails that match the query
        query_lower = query.lower()
        query_words = set(query_lower.split())
        matching_emails = []
        
        for email in emails:
            score = 0
            matches = []
            direct_match = False
            
            # Check subject
            subject_lower = email.subject.lower()
            if query_lower in subject_lower:
                score += 10  # Increased weight for exact phrase match
                matches.append('subject')
                direct_match = True
            elif any(word in subject_lower for word in query_words):
                score += 5  # Partial word match
                matches.append('subject')
                direct_match = True
            
            # Check body
            if email.body_full:
                body_lower = email.body_full.lower()
                if query_lower in body_lower:
                    score += 5  # Exact phrase match in body
                    matches.append('body')
                    direct_match = True
                    # Extra points for multiple occurrences
                    score += min(body_lower.count(query_lower) * 0.5, 5)  # Cap at 5 extra points
                elif any(word in body_lower for word in query_words):
                    score += 2  # Partial word match
                    matches.append('body')
                    direct_match = True
            
            # Only check related keywords if not in strict mode
            if search_mode != 'strict':
                for topic, keywords in self.topic_keywords.items():
                    if any(keyword == query_lower for keyword in keywords):
                        # This IS the topic we're searching for
                        for keyword in keywords:
                            if keyword != query_lower and (keyword in subject_lower or (email.body_full and keyword in body_lower)):
                                score += 0.5
                                if topic not in matches:
                                    matches.append(topic)
            
            # Include email based on search mode
            include_email = False
            if search_mode == 'strict' and direct_match:
                include_email = True
            elif search_mode == 'related' and score > 0:
                include_email = True
            elif search_mode == 'fuzzy' and score > 0:
                include_email = True
            
            if include_email:
                matching_emails.append({
                    'email': email,
                    'score': score,
                    'matches': matches,
                    'direct_match': direct_match
                })
        
        # Sort by score and date
        matching_emails.sort(key=lambda x: (x['score'], x['email'].date), reverse=True)
        
        return matching_emails
    
    def generate_narrative(self, customer_id, query, matching_emails):
        """Generate a narrative summary of the issue"""
        if not matching_emails:
            return "No relevant communications found for this query."
        
        # Group emails by topic and time period
        timeline = defaultdict(list)
        topics = defaultdict(int)
        participants = defaultdict(int)
        
        for match in matching_emails:
            email = match['email']
            month_key = email.date.strftime('%Y-%m')
            timeline[month_key].append(email)
            
            # Track participants
            participants[email.sender_name] += 1
            participants[email.recipient_name] += 1
            
            # Track topics
            for topic in match['matches']:
                if topic not in ['subject', 'body']:
                    topics[topic] += 1
        
        # Build narrative
        narrative_parts = []
        
        # Introduction
        first_email = matching_emails[-1]['email']  # Oldest
        last_email = matching_emails[0]['email']    # Newest
        
        narrative_parts.append(
            f"Found {len(matching_emails)} relevant communications about '{query}' "
            f"spanning from {first_email.date.strftime('%B %d, %Y')} "
            f"to {last_email.date.strftime('%B %d, %Y')}."
        )
        
        # Key participants
        top_participants = sorted(participants.items(), key=lambda x: x[1], reverse=True)[:4]
        if top_participants:
            names = [name for name, count in top_participants if name]
            if names:
                narrative_parts.append(
                    f"Key participants include: {', '.join(names)}."
                )
        
        # Topic analysis
        if topics:
            top_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)
            topic_desc = []
            for topic, count in top_topics:
                if topic == 'technical':
                    topic_desc.append("technical issues")
                elif topic == 'contract':
                    topic_desc.append("contract negotiations")
                elif topic == 'feature':
                    topic_desc.append("feature requests")
                elif topic == 'meeting':
                    topic_desc.append("meetings and discussions")
                elif topic == 'delivery':
                    topic_desc.append("delivery timelines")
                elif topic == 'payment':
                    topic_desc.append("payment matters")
            
            if topic_desc:
                narrative_parts.append(
                    f"The communications cover {', '.join(topic_desc)}."
                )
        
        # Timeline summary
        monthly_counts = {month: len(emails) for month, emails in timeline.items()}
        if len(monthly_counts) > 1:
            peak_month = max(monthly_counts.items(), key=lambda x: x[1])
            peak_date = datetime.strptime(peak_month[0], '%Y-%m')
            narrative_parts.append(
                f"Activity peaked in {peak_date.strftime('%B %Y')} with {peak_month[1]} messages."
            )
        
        # Recent activity
        recent_emails = [m['email'] for m in matching_emails if (datetime.utcnow() - m['email'].date).days < 30]
        if recent_emails:
            narrative_parts.append(
                f"There have been {len(recent_emails)} related messages in the past 30 days."
            )
        
        return " ".join(narrative_parts)
    
    def extract_key_messages(self, matching_emails, limit=10):
        """Extract the most important messages from the matches"""
        # Take top scored matches
        key_messages = []
        
        for match in matching_emails[:limit]:
            email = match['email']
            
            # Extract relevant excerpt
            excerpt = self._extract_excerpt(email, match['matches'])
            
            key_messages.append({
                'id': email.id,
                'date': email.date,
                'sender': email.sender_name,
                'sender_side': email.sender_side,
                'recipient': email.recipient_name,
                'subject': email.subject,
                'excerpt': excerpt,
                'score': match['score']
            })
        
        return key_messages
    
    def _extract_excerpt(self, email, matches, context_chars=150):
        """Extract relevant excerpt from email body"""
        if not email.body_full:
            return email.body_preview or ""
        
        # Find first occurrence of query terms
        body_lower = email.body_full.lower()
        best_pos = -1
        
        # Look for direct query matches first
        for match in matches:
            if match in ['subject', 'body']:
                continue
            pos = body_lower.find(match.lower())
            if pos != -1 and (best_pos == -1 or pos < best_pos):
                best_pos = pos
        
        if best_pos == -1:
            # Fall back to first 300 chars
            return email.body_full[:300] + "..." if len(email.body_full) > 300 else email.body_full
        
        # Extract context around match
        start = max(0, best_pos - context_chars)
        end = min(len(email.body_full), best_pos + context_chars)
        
        excerpt = email.body_full[start:end]
        
        # Clean up excerpt
        if start > 0:
            excerpt = "..." + excerpt.lstrip()
        if end < len(email.body_full):
            excerpt = excerpt.rstrip() + "..."
        
        return excerpt

# Global instance
insights_service = InsightsService()