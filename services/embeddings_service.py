import json
import requests
from datetime import datetime
# from typing import List, Dict, Optional  # Commenting out for Python 2 compatibility
import re
import logging
from models import db, EmailThread
from flask import current_app

logger = logging.getLogger(__name__)

class EmbeddingsService:
    """Service for calculating and managing email embeddings"""
    
    def __init__(self, api_key=None, model="text-embedding-3-small", force_simple=False):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.openai.com/v1/embeddings"
        self.force_simple = force_simple
        # Use simple embeddings if forced
        self.use_simple_embeddings = force_simple
        
        # For simple embeddings
        self.stopwords = set([
            'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'but',
            'in', 'with', 'to', 'for', 'of', 'as', 'by', 'that', 'this',
            'it', 'from', 'be', 'are', 'been', 'was', 'were', 'being'
        ])
    
    def _get_api_key(self):
        """Get API key with lazy loading from Flask config"""
        if self.api_key:
            return self.api_key
        try:
            from flask import current_app
            return current_app.config.get('OPENAI_API_KEY')
        except RuntimeError:
            # No application context available
            return None
    
    def _should_use_simple_embeddings(self):
        """Determine if we should use simple embeddings"""
        if self.force_simple:
            return True
        api_key = self._get_api_key()
        return not api_key
    
    def get_embedding(self, text):
        """Get embedding for a single text"""
        if self._should_use_simple_embeddings():
            return self._generate_simple_embedding(text)
            
        api_key = self._get_api_key()
        if not api_key:
            return self._generate_simple_embedding(text)
            
        headers = {
            "Authorization": "Bearer {}".format(api_key),
            "Content-Type": "application/json"
        }
        
        data = {
            "input": text,
            "model": self.model
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if 'data' in result and len(result['data']) > 0:
                return result['data'][0]['embedding']
            else:
                logger.error("Unexpected API response format: {}".format(result))
                return self._generate_simple_embedding(text)
                
        except requests.exceptions.RequestException as e:
            logger.error("API request failed: {}".format(e))
            return self._generate_simple_embedding(text)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse API response: {}".format(e))
            return self._generate_simple_embedding(text)
    
    def get_embeddings_batch(self, texts):
        """Get embeddings for multiple texts in batch"""
        if self._should_use_simple_embeddings():
            return [self._generate_simple_embedding(text) for text in texts]
            
        api_key = self._get_api_key()
        if not api_key:
            return [self._generate_simple_embedding(text) for text in texts]
            
        headers = {
            "Authorization": "Bearer {}".format(api_key),
            "Content-Type": "application/json"
        }
        
        # OpenAI API supports batch processing
        data = {
            "input": texts,
            "model": self.model
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            if 'data' in result:
                embeddings = []
                for item in result['data']:
                    if 'embedding' in item:
                        embeddings.append(item['embedding'])
                    else:
                        embeddings.append(None)
                return embeddings
            else:
                logger.error("Unexpected API response format: {}".format(result))
                return [self._generate_simple_embedding(text) for text in texts]
                
        except requests.exceptions.RequestException as e:
            logger.error("Batch API request failed: {}".format(e))
            return [self._generate_simple_embedding(text) for text in texts]
        except json.JSONDecodeError as e:
            logger.error("Failed to parse batch API response: {}".format(e))
            return [self._generate_simple_embedding(text) for text in texts]
    
    def process_email_embeddings(self, email_ids, progress_callback=None):
        """Process embeddings for a list of email IDs"""
        results = {
            'processed': 0,
            'errors': 0,
            'skipped': 0,
            'total': len(email_ids)
        }
        
        # Get emails in batches
        batch_size = 20 if not self._should_use_simple_embeddings() else 100
        
        for i in range(0, len(email_ids), batch_size):
            batch_ids = email_ids[i:i + batch_size]
            emails = EmailThread.query.filter(EmailThread.id.in_(batch_ids)).all()
            
            # Check for missing email IDs
            found_ids = set(email.id for email in emails)
            missing_ids = set(batch_ids) - found_ids
            for missing_id in missing_ids:
                logger.warning("Email ID {} not found in database - skipping".format(missing_id))
                results['skipped'] += 1
            
            # Skip emails that already have embeddings
            emails_to_process = []
            for email in emails:
                if email.has_embedding:
                    logger.info("Skipping email ID {} - already has embedding (processed at: {})".format(
                        email.id, email.embedding_processed_at
                    ))
                    results['skipped'] += 1
                else:
                    emails_to_process.append(email)
            
            if not emails_to_process:
                if progress_callback:
                    progress_callback(i + len(batch_ids), len(email_ids))
                continue
            
            # Prepare text for embedding
            texts = []
            for email in emails_to_process:
                # Combine subject and body for embedding
                text = "Subject: {}\n\nBody: {}".format(email.subject or '', email.body_full or email.body_preview or '')
                texts.append(text[:8000])  # Limit text length
            
            # Get embeddings
            embeddings = self.get_embeddings_batch(texts)
            
            # Save embeddings to database
            for email, embedding in zip(emails_to_process, embeddings):
                try:
                    if embedding:
                        email.embedding = json.dumps(embedding)
                        email.embedding_model = self.model
                        email.has_embedding = True
                        email.embedding_processed_at = datetime.utcnow()
                        email.embedding_error = None
                        results['processed'] += 1
                    else:
                        email.embedding_error = "Failed to get embedding"
                        results['errors'] += 1
                        
                except Exception as e:
                    logger.error("Error saving embedding for email {}: {}".format(email.id, e))
                    email.embedding_error = str(e)
                    results['errors'] += 1
            
            # Commit batch
            try:
                db.session.commit()
            except Exception as e:
                logger.error("Error committing batch: {}".format(e))
                db.session.rollback()
                results['errors'] += len(emails_to_process)
                results['processed'] = max(0, results['processed'] - len(emails_to_process))
            
            # Update progress
            if progress_callback:
                progress_callback(i + len(batch_ids), len(email_ids))
        
        return results
    
    def get_email_stats_for_customer(self, customer_id, sender_filter=None, 
                                   recipient_filter=None):
        """Get email statistics by year/month for a customer with filtering"""
        
        # Base query
        query = EmailThread.query.filter_by(customer_id=customer_id)
        
        # Apply sender filter if provided
        if sender_filter:
            query = query.filter(EmailThread.sender_email.in_(sender_filter))
        
        # Apply recipient filter if provided  
        if recipient_filter:
            query = query.filter(EmailThread.recipient_email.in_(recipient_filter))
        
        # Default filter: only emails involving our domains
        if not sender_filter and not recipient_filter:
            our_domains = ['wiredtriangle.com', 'knewvantage.com']
            domain_filters = []
            for domain in our_domains:
                domain_filters.append(EmailThread.sender_email.like('%@{}'.format(domain)))
                domain_filters.append(EmailThread.recipient_email.like('%@{}'.format(domain)))
            query = query.filter(db.or_(*domain_filters))
        
        emails = query.all()
        
        # Organize by year/month
        stats = {}
        for email in emails:
            year = email.date.year
            month = email.date.month
            
            if year not in stats:
                stats[year] = {'total': 0, 'with_embeddings': 0, 'months': {}}
            
            if month not in stats[year]['months']:
                stats[year]['months'][month] = {'total': 0, 'with_embeddings': 0}
            
            # Count totals
            stats[year]['total'] += 1
            stats[year]['months'][month]['total'] += 1
            
            # Count with embeddings
            if email.has_embedding:
                stats[year]['with_embeddings'] += 1
                stats[year]['months'][month]['with_embeddings'] += 1
        
        return stats
    
    def get_unique_email_addresses(self, customer_id):
        """Get unique sender and recipient email addresses for a customer"""
        emails = EmailThread.query.filter_by(customer_id=customer_id).all()
        
        senders = set()
        recipients = set()
        
        for email in emails:
            if email.sender_email:
                senders.add(email.sender_email)
            if email.recipient_email:
                recipients.add(email.recipient_email)
        
        return {
            'senders': sorted(list(senders)),
            'recipients': sorted(list(recipients))
        }
    
    def get_filtered_email_ids(self, customer_id, year=None, month=None,
                             sender_filter=None, recipient_filter=None):
        """Get email IDs matching the specified filters"""
        
        # Base query
        query = EmailThread.query.filter_by(customer_id=customer_id)
        
        # Apply date filters
        if year:
            query = query.filter(db.extract('year', EmailThread.date) == year)
        if month:
            query = query.filter(db.extract('month', EmailThread.date) == month)
        
        # Apply sender filter if provided
        if sender_filter:
            query = query.filter(EmailThread.sender_email.in_(sender_filter))
        
        # Apply recipient filter if provided
        if recipient_filter:
            query = query.filter(EmailThread.recipient_email.in_(recipient_filter))
        
        # Default filter: only emails involving our domains
        if not sender_filter and not recipient_filter:
            our_domains = ['wiredtriangle.com', 'knewvantage.com']
            domain_filters = []
            for domain in our_domains:
                domain_filters.append(EmailThread.sender_email.like('%@{}'.format(domain)))
                domain_filters.append(EmailThread.recipient_email.like('%@{}'.format(domain)))
            query = query.filter(db.or_(*domain_filters))
        
        emails = query.all()
        return [email.id for email in emails]
    
    def _generate_simple_embedding(self, content):
        """Generate a simple embedding vector as fallback"""
        if not content:
            return [0.0] * 100
        
        # Simple approach: TF-IDF based embedding
        words = re.findall(r'\b[a-zA-Z]{3,}\b', content.lower())
        words = [w for w in words if w not in self.stopwords]
        
        # Create a simple hash-based embedding
        embedding = [0.0] * 100
        for word in set(words):
            # Simple hash function without hashlib
            hash_val = sum(ord(c) for c in word) * 17
            position = hash_val % 100
            # TF score
            tf = words.count(word) / len(words) if words else 0
            embedding[position] += tf
        
        # Normalize without numpy
        norm = sum(x*x for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        return embedding
    
    def calculate_similarity(self, embedding1, embedding2):
        """Calculate cosine similarity between two embeddings"""
        if isinstance(embedding1, str):
            embedding1 = json.loads(embedding1)
        if isinstance(embedding2, str):
            embedding2 = json.loads(embedding2)
        
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        return dot_product  # Already normalized
    
    def extract_topics_from_embeddings(self, customer_id, max_main_topics=10, max_sub_topics=20):
        """Extract topics from existing embeddings using clustering and save to hierarchy"""
        try:
            # Get all emails with embeddings for this customer
            emails = EmailThread.query.filter_by(customer_id=customer_id).filter(
                EmailThread.has_embedding == True
            ).all()
            
            if not emails:
                return {'main_topics': [], 'sub_topics': [], 'error': 'No embeddings found'}
            
            # Extract embeddings and texts
            embeddings = []
            texts = []
            email_ids = []
            
            for email in emails:
                if email.embedding:
                    embedding = json.loads(email.embedding)
                    embeddings.append(embedding)
                    texts.append(email.subject or '')
                    email_ids.append(email.id)
            
            if not embeddings:
                return {'main_topics': [], 'sub_topics': [], 'error': 'No valid embeddings found'}
            
            # Simple clustering approach for topic extraction
            topics = self._cluster_embeddings_for_topics(embeddings, texts, email_ids)
            
            # Import topic service for hierarchy management
            from services.topic_service import get_topic_service
            topic_service = get_topic_service()
            
            # Create/update topics in hierarchy
            created_main_topics = []
            created_sub_topics = []
            
            # Process main topics
            for topic_data in topics.get('main_topics', [])[:max_main_topics]:
                topic_name = topic_data['name']
                email_list = topic_data['emails']
                
                # Find or create topic
                from models import Topic
                existing_topic = Topic.query.filter_by(name=topic_name, level=0).first()
                
                if not existing_topic:
                    # Create new main topic
                    new_topic = topic_service.create_topic(
                        name=topic_name,
                        description=f"Auto-generated main topic from embeddings",
                        level=0,
                        created_by='embeddings_system'
                    )
                    topic_id = new_topic.id
                else:
                    topic_id = existing_topic.id
                
                # Assign emails to topic
                for email_id in email_list:
                    topic_service.assign_topic_to_email(
                        email_id=email_id,
                        topic_id=topic_id,
                        confidence_score=0.8,
                        classification_method='embedding_clustering',
                        assigned_by='embeddings_system'
                    )
                
                created_main_topics.append({
                    'name': topic_name,
                    'count': len(email_list),
                    'emails': email_list,
                    'topic_id': topic_id
                })
            
            # Process sub topics
            for topic_data in topics.get('sub_topics', [])[:max_sub_topics]:
                topic_name = topic_data['name']
                email_list = topic_data['emails']
                
                # Find or create topic
                existing_topic = Topic.query.filter_by(name=topic_name, level=1).first()
                
                if not existing_topic:
                    # Create new sub topic
                    new_topic = topic_service.create_topic(
                        name=topic_name,
                        description=f"Auto-generated sub topic from embeddings",
                        level=1,
                        created_by='embeddings_system'
                    )
                    topic_id = new_topic.id
                else:
                    topic_id = existing_topic.id
                
                # Assign emails to topic
                for email_id in email_list:
                    topic_service.assign_topic_to_email(
                        email_id=email_id,
                        topic_id=topic_id,
                        confidence_score=0.7,
                        classification_method='embedding_clustering',
                        assigned_by='embeddings_system'
                    )
                
                created_sub_topics.append({
                    'name': topic_name,
                    'count': len(email_list),
                    'emails': email_list,
                    'topic_id': topic_id
                })
            
            # Update topic statistics
            topic_service.update_topic_statistics()
            
            return {
                'main_topics': created_main_topics,
                'sub_topics': created_sub_topics,
                'total_emails': len(emails),
                'processed_emails': len(embeddings)
            }
            
        except Exception as e:
            logger.error("Error extracting topics: {}".format(e))
            return {'main_topics': [], 'sub_topics': [], 'error': str(e)}
    
    def _cluster_embeddings_for_topics(self, embeddings, texts, email_ids):
        """Simple clustering approach to identify topics"""
        # Simple approach: find most common words/phrases in different clusters
        main_topics = []
        sub_topics = []
        
        # Group emails by similarity
        clusters = self._simple_clustering(embeddings, texts, email_ids)
        
        for cluster in clusters:
            # Extract topic from cluster
            topic = self._extract_topic_from_cluster(cluster)
            if topic:
                if len(main_topics) < 10:
                    main_topics.append(topic)
                elif len(sub_topics) < 20:
                    sub_topics.append(topic)
        
        return {'main_topics': main_topics, 'sub_topics': sub_topics}
    
    def _simple_clustering(self, embeddings, texts, email_ids, num_clusters=15):
        """Simple clustering without external libraries"""
        if not embeddings:
            return []
        
        # Simple approach: group by similarity threshold
        clusters = []
        used_indices = set()
        
        for i, embedding in enumerate(embeddings):
            if i in used_indices:
                continue
                
            cluster = {
                'center': embedding,
                'texts': [texts[i]],
                'ids': [email_ids[i]],
                'indices': [i]
            }
            used_indices.add(i)
            
            # Find similar embeddings
            for j, other_embedding in enumerate(embeddings):
                if j in used_indices:
                    continue
                    
                similarity = self.calculate_similarity(embedding, other_embedding)
                if similarity > 0.8:  # Similarity threshold
                    cluster['texts'].append(texts[j])
                    cluster['ids'].append(email_ids[j])
                    cluster['indices'].append(j)
                    used_indices.add(j)
            
            if len(cluster['texts']) > 1:  # Only keep clusters with multiple emails
                clusters.append(cluster)
        
        # Sort by cluster size
        clusters.sort(key=lambda x: len(x['texts']), reverse=True)
        return clusters[:num_clusters]
    
    def _extract_topic_from_cluster(self, cluster):
        """Extract a topic name from a cluster of texts"""
        texts = cluster['texts']
        if not texts:
            return None
        
        # Simple approach: find most common words
        word_counts = {}
        for text in texts:
            words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
            for word in words:
                if word not in self.stopwords:
                    word_counts[word] = word_counts.get(word, 0) + 1
        
        # Get top words
        if word_counts:
            sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
            top_words = [word for word, count in sorted_words[:3]]
            return {
                'name': ' '.join(top_words),
                'count': len(texts),
                'emails': cluster['ids']
            }
        
        return None

# Global instance - lazy initialization
embeddings_service = None

def get_embeddings_service():
    global embeddings_service
    if embeddings_service is None:
        embeddings_service = EmbeddingsService()
    return embeddings_service