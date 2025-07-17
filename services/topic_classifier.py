"""
Advanced topic classification service with multiple algorithms and confidence scoring.
"""

import json
import re
import math
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from collections import defaultdict, Counter
from sqlalchemy import and_, or_, func, desc

from models import (
    db, Topic, EmailTopic, TopicKeyword, TopicSimilarity, 
    EmailThread, Customer
)
from services.embeddings_service import get_embeddings_service

logger = logging.getLogger(__name__)

class TopicClassifier:
    """Advanced topic classification with multiple algorithms"""
    
    def __init__(self):
        self.min_confidence_threshold = 0.3
        self.keyword_weight = 0.4
        self.embedding_weight = 0.6
        self.context_weight = 0.3
        self.frequency_weight = 0.2
        
    def classify_email(self, email_id: int, methods: List[str] = None) -> Dict:
        """
        Classify an email using multiple methods and return confidence scores.
        
        Args:
            email_id: ID of the email to classify
            methods: List of methods to use ['keyword', 'embedding', 'context', 'frequency']
        
        Returns:
            Dict with classification results and confidence scores
        """
        if methods is None:
            methods = ['keyword', 'embedding', 'context', 'frequency']
        
        email = EmailThread.query.get(email_id)
        if not email:
            return {'error': 'Email not found'}
        
        # Get all active topics
        topics = Topic.query.filter_by(is_active=True).all()
        if not topics:
            return {'error': 'No active topics found'}
        
        # Calculate scores for each method
        method_scores = {}
        
        if 'keyword' in methods:
            method_scores['keyword'] = self._classify_by_keywords(email, topics)
        
        if 'embedding' in methods:
            method_scores['embedding'] = self._classify_by_embeddings(email, topics)
        
        if 'context' in methods:
            method_scores['context'] = self._classify_by_context(email, topics)
        
        if 'frequency' in methods:
            method_scores['frequency'] = self._classify_by_frequency(email, topics)
        
        # Combine scores using weighted average
        final_scores = self._combine_scores(method_scores)
        
        # Filter by confidence threshold
        confident_topics = [
            {
                'topic_id': topic_id,
                'topic_name': Topic.query.get(topic_id).name,
                'confidence_score': score,
                'method_breakdown': {
                    method: method_scores[method].get(topic_id, 0.0)
                    for method in method_scores
                }
            }
            for topic_id, score in final_scores.items()
            if score >= self.min_confidence_threshold
        ]
        
        # Sort by confidence
        confident_topics.sort(key=lambda x: x['confidence_score'], reverse=True)
        
        return {
            'email_id': email_id,
            'classifications': confident_topics,
            'methods_used': methods,
            'total_topics_considered': len(topics),
            'confident_topics': len(confident_topics)
        }
    
    def _classify_by_keywords(self, email: EmailThread, topics: List[Topic]) -> Dict[int, float]:
        """Classify email based on keyword matching"""
        scores = {}
        
        # Combine subject and body text
        text_content = f"{email.subject or ''} {email.body_full or email.body_preview or ''}"
        text_content = text_content.lower()
        
        # Remove common stop words
        stop_words = {
            'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'but',
            'in', 'with', 'to', 'for', 'of', 'as', 'by', 'that', 'this',
            'it', 'from', 'be', 'are', 'been', 'was', 'were', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'should', 'could', 'can', 'may', 'might', 'must', 'shall'
        }
        
        # Extract words
        words = re.findall(r'\\b[a-zA-Z]{2,}\\b', text_content)
        words = [word for word in words if word not in stop_words]
        word_count = len(words)
        
        if word_count == 0:
            return scores
        
        # Score each topic based on keyword matches
        for topic in topics:
            topic_score = 0.0
            keyword_matches = 0
            
            # Get keywords for this topic
            keywords = TopicKeyword.query.filter_by(topic_id=topic.id).all()
            
            for keyword_obj in keywords:
                keyword = keyword_obj.keyword.lower()
                
                # Exact match
                if keyword in text_content:
                    topic_score += keyword_obj.weight
                    keyword_matches += 1
                    
                    # Bonus for multiple occurrences
                    occurrences = text_content.count(keyword)
                    if occurrences > 1:
                        topic_score += (occurrences - 1) * keyword_obj.weight * 0.1
                
                # Partial match for compound keywords
                if ' ' in keyword:
                    keyword_words = keyword.split()
                    if all(kw in text_content for kw in keyword_words):
                        topic_score += keyword_obj.weight * 0.7
                        keyword_matches += 1
            
            # Normalize score
            if keyword_matches > 0:
                # Factor in keyword density
                keyword_density = keyword_matches / word_count
                topic_score *= (1 + keyword_density)
                
                # Cap at 1.0
                scores[topic.id] = min(topic_score / 10.0, 1.0)
        
        return scores
    
    def _classify_by_embeddings(self, email: EmailThread, topics: List[Topic]) -> Dict[int, float]:
        """Classify email based on embedding similarity"""
        scores = {}
        
        if not email.has_embedding or not email.embedding:
            return scores
        
        try:
            email_embedding = json.loads(email.embedding)
        except json.JSONDecodeError:
            return scores
        
        embeddings_service = get_embeddings_service()
        
        # For each topic, find similar emails and calculate average similarity
        for topic in topics:
            topic_assignments = EmailTopic.query.filter_by(
                topic_id=topic.id
            ).join(EmailThread).filter(
                EmailThread.has_embedding == True
            ).limit(20).all()  # Limit for performance
            
            if not topic_assignments:
                continue
            
            similarities = []
            
            for assignment in topic_assignments:
                other_email = assignment.email
                if other_email.embedding:
                    try:
                        other_embedding = json.loads(other_email.embedding)
                        similarity = embeddings_service.calculate_similarity(
                            email_embedding, other_embedding
                        )
                        similarities.append(similarity)
                    except json.JSONDecodeError:
                        continue
            
            if similarities:
                # Use weighted average (higher confidence assignments get more weight)
                weighted_sum = sum(
                    sim * assignment.confidence_score
                    for sim, assignment in zip(similarities, topic_assignments)
                )
                weight_sum = sum(assignment.confidence_score for assignment in topic_assignments)
                
                if weight_sum > 0:
                    avg_similarity = weighted_sum / weight_sum
                    scores[topic.id] = max(0.0, min(avg_similarity, 1.0))
        
        return scores
    
    def _classify_by_context(self, email: EmailThread, topics: List[Topic]) -> Dict[int, float]:
        """Classify email based on contextual information"""
        scores = {}
        
        # Context factors
        context_factors = {
            'sender_domain': self._get_sender_domain_score(email),
            'email_thread': self._get_email_thread_score(email),
            'time_context': self._get_time_context_score(email),
            'recipient_pattern': self._get_recipient_pattern_score(email)
        }
        
        # Get emails from same sender for pattern analysis
        sender_emails = EmailThread.query.filter_by(
            sender_email=email.sender_email,
            customer_id=email.customer_id
        ).filter(EmailThread.id != email.id).limit(10).all()
        
        # Analyze sender's topic patterns
        sender_topic_patterns = defaultdict(list)
        
        for sender_email in sender_emails:
            assignments = EmailTopic.query.filter_by(email_id=sender_email.id).all()
            for assignment in assignments:
                sender_topic_patterns[assignment.topic_id].append(assignment.confidence_score)
        
        # Score topics based on sender patterns
        for topic in topics:
            topic_score = 0.0
            
            # Sender topic affinity
            if topic.id in sender_topic_patterns:
                confidences = sender_topic_patterns[topic.id]
                avg_confidence = sum(confidences) / len(confidences)
                topic_score += avg_confidence * 0.5
            
            # Apply context factors
            for factor, weight in context_factors.items():
                topic_score += weight * 0.1  # Small contextual boost
            
            if topic_score > 0:
                scores[topic.id] = min(topic_score, 1.0)
        
        return scores
    
    def _classify_by_frequency(self, email: EmailThread, topics: List[Topic]) -> Dict[int, float]:
        """Classify email based on topic frequency patterns"""
        scores = {}
        
        # Get recent emails from same customer
        recent_emails = EmailThread.query.filter_by(
            customer_id=email.customer_id
        ).filter(
            EmailThread.date >= datetime.now().replace(month=datetime.now().month - 1)
        ).limit(100).all()
        
        # Count topic frequencies
        topic_frequencies = defaultdict(int)
        total_assignments = 0
        
        for recent_email in recent_emails:
            assignments = EmailTopic.query.filter_by(email_id=recent_email.id).all()
            for assignment in assignments:
                topic_frequencies[assignment.topic_id] += 1
                total_assignments += 1
        
        if total_assignments == 0:
            return scores
        
        # Score topics based on recent frequency
        for topic in topics:
            if topic.id in topic_frequencies:
                frequency = topic_frequencies[topic.id]
                frequency_score = frequency / total_assignments
                
                # Apply frequency boost (common topics get slight preference)
                scores[topic.id] = min(frequency_score * 2.0, 0.5)  # Cap at 0.5
        
        return scores
    
    def _combine_scores(self, method_scores: Dict[str, Dict[int, float]]) -> Dict[int, float]:
        """Combine scores from different methods using weighted average"""
        combined_scores = defaultdict(float)
        
        weights = {
            'keyword': self.keyword_weight,
            'embedding': self.embedding_weight,
            'context': self.context_weight,
            'frequency': self.frequency_weight
        }
        
        # Normalize weights
        total_weight = sum(weights.get(method, 0) for method in method_scores.keys())
        if total_weight == 0:
            return combined_scores
        
        for method, method_weight in weights.items():
            if method in method_scores:
                normalized_weight = method_weight / total_weight
                
                for topic_id, score in method_scores[method].items():
                    combined_scores[topic_id] += score * normalized_weight
        
        return dict(combined_scores)
    
    def _get_sender_domain_score(self, email: EmailThread) -> float:
        """Get score based on sender domain"""
        if not email.sender_email:
            return 0.0
        
        domain = email.sender_email.split('@')[-1].lower()
        
        # Internal domains get different treatment
        internal_domains = ['wiredtriangle.com', 'knewvantage.com']
        if domain in internal_domains:
            return 0.2
        
        # External domains
        return 0.1
    
    def _get_email_thread_score(self, email: EmailThread) -> float:
        """Get score based on email thread context"""
        if not email.subject:
            return 0.0
        
        # Look for thread indicators
        thread_indicators = ['re:', 'fwd:', 'fw:', 'reply:', 'forward:']
        subject_lower = email.subject.lower()
        
        for indicator in thread_indicators:
            if subject_lower.startswith(indicator):
                return 0.3
        
        return 0.1
    
    def _get_time_context_score(self, email: EmailThread) -> float:
        """Get score based on time context"""
        if not email.date:
            return 0.0
        
        # Recent emails get slight boost
        days_ago = (datetime.now() - email.date).days
        
        if days_ago <= 7:
            return 0.2
        elif days_ago <= 30:
            return 0.1
        
        return 0.0
    
    def _get_recipient_pattern_score(self, email: EmailThread) -> float:
        """Get score based on recipient patterns"""
        if not email.recipient_email:
            return 0.0
        
        # Internal recipients
        internal_domains = ['wiredtriangle.com', 'knewvantage.com']
        recipient_domain = email.recipient_email.split('@')[-1].lower()
        
        if recipient_domain in internal_domains:
            return 0.2
        
        return 0.1
    
    def auto_classify_emails(self, customer_id: int, limit: int = 50, 
                           force_reclassify: bool = False) -> Dict:
        """
        Automatically classify multiple emails for a customer.
        
        Args:
            customer_id: Customer ID to classify emails for
            limit: Maximum number of emails to process
            force_reclassify: Whether to reclassify already classified emails
        
        Returns:
            Dict with classification results and statistics
        """
        # Get unclassified emails (or all if force_reclassify)
        query = EmailThread.query.filter_by(customer_id=customer_id)
        
        if not force_reclassify:
            # Only get emails without topic assignments
            classified_email_ids = db.session.query(EmailTopic.email_id).distinct().subquery()
            query = query.filter(~EmailThread.id.in_(classified_email_ids))
        
        emails = query.order_by(desc(EmailThread.date)).limit(limit).all()
        
        if not emails:
            return {
                'processed': 0,
                'classified': 0,
                'skipped': 0,
                'error': 'No emails found to classify'
            }
        
        results = {
            'processed': 0,
            'classified': 0,
            'skipped': 0,
            'errors': [],
            'classifications': []
        }
        
        from services.topic_service import get_topic_service
        topic_service = get_topic_service()
        
        # Process each email
        for email in emails:
            try:
                # Classify the email
                classification_result = self.classify_email(email.id)
                
                if 'error' in classification_result:
                    results['errors'].append(f"Email {email.id}: {classification_result['error']}")
                    results['skipped'] += 1
                    continue
                
                # Assign confident topics
                email_classifications = []
                for topic_data in classification_result['classifications']:
                    if topic_data['confidence_score'] >= self.min_confidence_threshold:
                        # Create topic assignment
                        topic_service.assign_topic_to_email(
                            email_id=email.id,
                            topic_id=topic_data['topic_id'],
                            confidence_score=topic_data['confidence_score'],
                            classification_method='auto_classification',
                            assigned_by='system'
                        )
                        
                        email_classifications.append({
                            'topic_name': topic_data['topic_name'],
                            'confidence': topic_data['confidence_score']
                        })
                
                results['classifications'].append({
                    'email_id': email.id,
                    'subject': email.subject,
                    'topics': email_classifications
                })
                
                if email_classifications:
                    results['classified'] += 1
                else:
                    results['skipped'] += 1
                
                results['processed'] += 1
                
            except Exception as e:
                logger.error(f"Error classifying email {email.id}: {e}")
                results['errors'].append(f"Email {email.id}: {str(e)}")
                results['skipped'] += 1
        
        return results
    
    def get_classification_analytics(self, customer_id: int = None) -> Dict:
        """Get analytics about topic classification performance"""
        
        query = EmailTopic.query
        if customer_id:
            query = query.join(EmailThread).filter(EmailThread.customer_id == customer_id)
        
        assignments = query.all()
        
        analytics = {
            'total_assignments': len(assignments),
            'method_breakdown': defaultdict(int),
            'confidence_distribution': defaultdict(int),
            'topic_usage': defaultdict(int),
            'verification_stats': {
                'verified': 0,
                'unverified': 0,
                'verification_rate': 0.0
            }
        }
        
        # Analyze assignments
        for assignment in assignments:
            # Method breakdown
            analytics['method_breakdown'][assignment.classification_method or 'unknown'] += 1
            
            # Confidence distribution
            confidence_bucket = int(assignment.confidence_score * 10) / 10
            analytics['confidence_distribution'][confidence_bucket] += 1
            
            # Topic usage
            topic_name = assignment.topic.name if assignment.topic else 'Unknown'
            analytics['topic_usage'][topic_name] += 1
            
            # Verification stats
            if assignment.is_verified:
                analytics['verification_stats']['verified'] += 1
            else:
                analytics['verification_stats']['unverified'] += 1
        
        # Calculate verification rate
        if analytics['total_assignments'] > 0:
            analytics['verification_stats']['verification_rate'] = (
                analytics['verification_stats']['verified'] / analytics['total_assignments']
            )
        
        return analytics
    
    def suggest_new_topics(self, customer_id: int, min_cluster_size: int = 3) -> List[Dict]:
        """Suggest new topics based on unclassified email clusters"""
        
        # Get unclassified emails
        classified_email_ids = db.session.query(EmailTopic.email_id).distinct().subquery()
        unclassified_emails = EmailThread.query.filter_by(
            customer_id=customer_id
        ).filter(
            ~EmailThread.id.in_(classified_email_ids)
        ).all()
        
        if len(unclassified_emails) < min_cluster_size:
            return []
        
        # Simple keyword-based clustering
        suggestions = []
        
        # Extract common keywords from subjects
        subject_words = []
        for email in unclassified_emails:
            if email.subject:
                words = re.findall(r'\\b[a-zA-Z]{3,}\\b', email.subject.lower())
                subject_words.extend(words)
        
        # Find most common words
        word_counts = Counter(subject_words)
        common_words = [word for word, count in word_counts.most_common(20) if count >= min_cluster_size]
        
        # Create topic suggestions
        for word in common_words:
            related_emails = [
                email for email in unclassified_emails
                if email.subject and word in email.subject.lower()
            ]
            
            if len(related_emails) >= min_cluster_size:
                suggestions.append({
                    'suggested_name': word.title(),
                    'email_count': len(related_emails),
                    'sample_subjects': [email.subject for email in related_emails[:3]],
                    'confidence': min(len(related_emails) / 10.0, 1.0)
                })
        
        return suggestions

# Global instance
_topic_classifier = None

def get_topic_classifier() -> TopicClassifier:
    """Get the global topic classifier instance"""
    global _topic_classifier
    if _topic_classifier is None:
        _topic_classifier = TopicClassifier()
    return _topic_classifier