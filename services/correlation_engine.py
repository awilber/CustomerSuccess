import json
import re
from datetime import datetime, timedelta
from models import db, FileReference, EmailThread, FileEmailCorrelation, Customer
from services.embeddings_service import embeddings_service
from sqlalchemy import and_, or_

class CorrelationEngine:
    """Engine for correlating files with email threads"""
    
    def correlate_customer_files(self, customer_id, specific_file_id=None):
        """Correlate files with emails for a customer"""
        # Get files to correlate
        if specific_file_id:
            files = FileReference.query.filter_by(
                id=specific_file_id,
                customer_id=customer_id,
                processing_status='completed'
            ).all()
        else:
            files = FileReference.query.filter_by(
                customer_id=customer_id,
                processing_status='completed'
            ).all()
        
        # Get all emails for the customer
        emails = EmailThread.query.filter_by(customer_id=customer_id).all()
        
        for file_ref in files:
            self._correlate_file_with_emails(file_ref, emails)
    
    def _correlate_file_with_emails(self, file_ref, emails):
        """Correlate a single file with emails"""
        # Clear existing correlations for this file
        FileEmailCorrelation.query.filter_by(file_id=file_ref.id).delete()
        
        correlations = []
        
        for email in emails:
            correlation_score = 0
            correlation_types = []
            
            # 1. Direct filename mention
            if file_ref.file_name.lower() in email.subject.lower():
                correlation_score += 0.8
                correlation_types.append('subject_mention')
            
            if email.body_full and file_ref.file_name.lower() in email.body_full.lower():
                correlation_score += 0.6
                correlation_types.append('body_mention')
            
            # 2. Keyword overlap
            if file_ref.keywords and email.body_full:
                file_keywords = json.loads(file_ref.keywords) if isinstance(file_ref.keywords, str) else []
                keyword_score = self._calculate_keyword_overlap(file_keywords, email.body_full)
                if keyword_score > 0.2:
                    correlation_score += keyword_score * 0.5
                    correlation_types.append('keyword_match')
            
            # 3. Temporal correlation (file modified around email time)
            if file_ref.last_modified and email.date:
                time_diff = abs((file_ref.last_modified - email.date).total_seconds())
                if time_diff < 86400:  # Within 24 hours
                    correlation_score += 0.3
                    correlation_types.append('temporal_24h')
                elif time_diff < 604800:  # Within 7 days
                    correlation_score += 0.1
                    correlation_types.append('temporal_7d')
            
            # 4. Topic similarity
            if file_ref.topic and email.subject:
                if file_ref.topic.lower() in email.subject.lower():
                    correlation_score += 0.2
                    correlation_types.append('topic_match')
            
            # 5. Embedding similarity (if available)
            if file_ref.embedding and hasattr(email, 'embedding') and email.embedding:
                similarity = embeddings_service.calculate_similarity(
                    file_ref.embedding, email.embedding
                )
                if similarity > 0.7:
                    correlation_score += similarity * 0.4
                    correlation_types.append('semantic_similarity')
            
            # Store correlation if significant
            if correlation_score > 0.1:
                correlation = FileEmailCorrelation(
                    file_id=file_ref.id,
                    email_id=email.id,
                    correlation_score=min(correlation_score, 1.0),
                    correlation_type=','.join(correlation_types)
                )
                correlations.append(correlation)
        
        # Bulk insert correlations
        if correlations:
            db.session.bulk_save_objects(correlations)
            db.session.commit()
    
    def _calculate_keyword_overlap(self, file_keywords, email_text):
        """Calculate keyword overlap score"""
        if not file_keywords or not email_text:
            return 0
        
        email_lower = email_text.lower()
        matches = sum(1 for keyword in file_keywords if keyword.lower() in email_lower)
        
        return min(matches / len(file_keywords), 1.0)
    
    def recalculate_importance_scores(self, customer_id):
        """Recalculate importance scores for all files"""
        files = FileReference.query.filter_by(customer_id=customer_id).all()
        
        for file_ref in files:
            # Calculate importance based on:
            # 1. Number of email correlations
            correlation_count = file_ref.correlations.count()
            
            # 2. Strength of correlations
            avg_correlation = db.session.query(
                db.func.avg(FileEmailCorrelation.correlation_score)
            ).filter_by(file_id=file_ref.id).scalar() or 0
            
            # 3. Recency of correlated emails
            recent_correlations = file_ref.correlations.join(EmailThread).filter(
                EmailThread.date > datetime.utcnow() - timedelta(days=30)
            ).count()
            
            # 4. File metadata factors
            metadata_score = 0
            if file_ref.last_modified:
                days_old = (datetime.utcnow() - file_ref.last_modified).days
                if days_old < 7:
                    metadata_score += 0.3
                elif days_old < 30:
                    metadata_score += 0.2
                elif days_old < 90:
                    metadata_score += 0.1
            
            # Calculate final importance score
            importance_score = (
                min(correlation_count / 10, 1.0) * 0.3 +  # Correlation count (max 10)
                avg_correlation * 0.3 +                    # Average correlation strength
                min(recent_correlations / 5, 1.0) * 0.2 + # Recent correlations (max 5)
                metadata_score * 0.2                       # File metadata
            )
            
            file_ref.importance_score = round(importance_score, 3)
        
        db.session.commit()
    
    def get_file_timeline_data(self, customer_id, email_thread_filter=None):
        """Get data for file importance heatmap"""
        # Base query
        query = db.session.query(
            FileReference.id,
            FileReference.file_name,
            FileReference.last_modified,
            FileReference.importance_score,
            FileReference.topic,
            db.func.count(FileEmailCorrelation.id).label('correlation_count')
        ).outerjoin(FileEmailCorrelation).filter(
            FileReference.customer_id == customer_id
        ).group_by(FileReference.id)
        
        # Apply email thread filter if provided
        if email_thread_filter:
            # Get emails matching the filter
            email_ids = db.session.query(EmailThread.id).filter(
                EmailThread.customer_id == customer_id,
                or_(
                    EmailThread.subject.contains(email_thread_filter),
                    EmailThread.body_preview.contains(email_thread_filter)
                )
            ).subquery()
            
            # Filter files correlated with these emails
            query = query.join(
                FileEmailCorrelation,
                FileReference.id == FileEmailCorrelation.file_id
            ).filter(
                FileEmailCorrelation.email_id.in_(email_ids)
            )
        
        results = query.all()
        
        # Format for heatmap
        heatmap_data = []
        for result in results:
            if result.last_modified:
                heatmap_data.append({
                    'file_id': result.id,
                    'file_name': result.file_name,
                    'date': result.last_modified.isoformat(),
                    'importance': result.importance_score or 0,
                    'topic': result.topic or 'general',
                    'correlations': result.correlation_count
                })
        
        return heatmap_data

# Global instance
correlation_engine = CorrelationEngine()