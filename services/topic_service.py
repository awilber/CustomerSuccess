"""
Topic hierarchy management service.
Provides functionality for managing hierarchical topics, classification, and relationships.
"""

import json
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from sqlalchemy import and_, or_, func, desc
from models import (
    db,
    Topic,
    EmailTopic,
    TopicKeyword,
    TopicSimilarity,
    EmailThread,
    Customer,
    customer_topic,
)

logger = logging.getLogger(__name__)


class TopicService:
    """Service for managing topic hierarchy and classification"""

    def __init__(self):
        self.max_main_topics = 10
        self.max_sub_topics = 20
        self.max_micro_topics = 50

    def create_topic(
        self,
        name,
        description=None,
        parent_id=None,
        level=None,
        color=None,
        created_by=None,
        keywords=None,
    ):
        """Create a new topic in the hierarchy"""

        # Auto-determine level if not provided
        if level is None:
            if parent_id is None:
                level = 0  # Main topic
            else:
                parent = Topic.query.get(parent_id)
                if parent:
                    level = parent.level + 1
                else:
                    level = 0

        # Validate level limits
        if level == 0 and self.get_topic_count(level=0) >= self.max_main_topics:
            raise ValueError(
                "Maximum main topics ({}) reached".format(self.max_main_topics)
            )
        elif level == 1 and self.get_topic_count(level=1) >= self.max_sub_topics:
            raise ValueError(
                "Maximum sub topics ({}) reached".format(self.max_sub_topics)
            )
        elif level == 2 and self.get_topic_count(level=2) >= self.max_micro_topics:
            raise ValueError(
                "Maximum micro topics ({}) reached".format(self.max_micro_topics)
            )

        # Create topic
        topic = Topic(
            name=name,
            description=description,
            parent_id=parent_id,
            level=level,
            color=color or self._generate_color_for_level(level),
            created_by=created_by,
            auto_generated=False,
        )

        db.session.add(topic)
        db.session.flush()  # Get the ID

        # Add keywords if provided
        if keywords:
            for keyword in keywords:
                self.add_keyword_to_topic(topic.id, keyword, created_by=created_by)

        db.session.commit()
        logger.info(f"Created topic: {name} (Level {level})")
        return topic

    def get_topic_hierarchy(
        self, customer_id: int = None, include_inactive: bool = False
    ) -> List[Dict]:
        """Get the complete topic hierarchy for a customer"""

        query = Topic.query

        if not include_inactive:
            query = query.filter(Topic.is_active == True)

        if customer_id:
            # Filter by customer association
            query = query.join(customer_topic).filter(
                customer_topic.c.customer_id == customer_id
            )

        # Get all topics ordered by level and name
        topics = query.order_by(Topic.level, Topic.name).all()

        # Build hierarchy
        hierarchy = []
        topic_map = {}

        for topic in topics:
            topic_dict = topic.to_dict()
            topic_map[topic.id] = topic_dict

            if topic.parent_id is None:
                hierarchy.append(topic_dict)
            else:
                parent = topic_map.get(topic.parent_id)
                if parent:
                    if "children" not in parent:
                        parent["children"] = []
                    parent["children"].append(topic_dict)

        return hierarchy

    def get_topics_by_level(
        self, level: int, parent_id: int = None, customer_id: int = None
    ) -> List[Topic]:
        """Get topics filtered by level and optional parent"""

        query = Topic.query.filter(Topic.level == level, Topic.is_active == True)

        if parent_id is not None:
            query = query.filter(Topic.parent_id == parent_id)

        if customer_id:
            query = query.join(customer_topic).filter(
                customer_topic.c.customer_id == customer_id
            )

        return query.order_by(Topic.name).all()

    def get_topic_count(self, level: int = None, parent_id: int = None) -> int:
        """Get count of topics at a specific level or under a parent"""

        query = Topic.query.filter(Topic.is_active == True)

        if level is not None:
            query = query.filter(Topic.level == level)

        if parent_id is not None:
            query = query.filter(Topic.parent_id == parent_id)

        return query.count()

    def assign_topic_to_email(
        self,
        email_id: int,
        topic_id: int,
        confidence_score: float = 1.0,
        classification_method: str = "manual",
        assigned_by: str = None,
    ) -> EmailTopic:
        """Assign a topic to an email with confidence scoring"""

        # Check if assignment already exists
        existing = EmailTopic.query.filter_by(
            email_id=email_id, topic_id=topic_id
        ).first()
        if existing:
            # Update existing assignment
            existing.confidence_score = confidence_score
            existing.classification_method = classification_method
            existing.assigned_by = assigned_by
            existing.assigned_at = datetime.utcnow()
            db.session.commit()
            return existing

        # Create new assignment
        assignment = EmailTopic(
            email_id=email_id,
            topic_id=topic_id,
            confidence_score=confidence_score,
            classification_method=classification_method,
            assigned_by=assigned_by,
        )

        db.session.add(assignment)

        # Update topic email count
        topic = Topic.query.get(topic_id)
        if topic:
            topic.email_count = Topic.query.get(topic_id).email_assignments.count() + 1
            topic.last_used = datetime.utcnow()

        db.session.commit()
        logger.info(
            f"Assigned topic {topic_id} to email {email_id} with confidence {confidence_score}"
        )
        return assignment

    def remove_topic_from_email(self, email_id: int, topic_id: int) -> bool:
        """Remove a topic assignment from an email"""

        assignment = EmailTopic.query.filter_by(
            email_id=email_id, topic_id=topic_id
        ).first()
        if assignment:
            db.session.delete(assignment)

            # Update topic email count
            topic = Topic.query.get(topic_id)
            if topic:
                topic.email_count = max(0, topic.email_count - 1)

            db.session.commit()
            logger.info(f"Removed topic {topic_id} from email {email_id}")
            return True

        return False

    def get_email_topics(self, email_id: int) -> List[Dict]:
        """Get all topics assigned to an email"""

        assignments = EmailTopic.query.filter_by(email_id=email_id).all()
        return [assignment.to_dict() for assignment in assignments]

    def get_topic_emails(self, topic_id: int, limit: int = None) -> List[Dict]:
        """Get all emails assigned to a topic"""

        query = EmailTopic.query.filter_by(topic_id=topic_id).join(EmailThread)
        query = query.order_by(
            desc(EmailTopic.confidence_score), desc(EmailThread.date)
        )

        if limit:
            query = query.limit(limit)

        assignments = query.all()
        return [assignment.to_dict() for assignment in assignments]

    def classify_email_by_keywords(
        self, email_id: int, force_reclassify: bool = False
    ) -> List[EmailTopic]:
        """Automatically classify an email based on topic keywords"""

        email = EmailThread.query.get(email_id)
        if not email:
            return []

        # Check if already classified
        if not force_reclassify and email.topic_assignments:
            return email.topic_assignments

        # Get email text content
        text_content = (
            f"{email.subject or ''} {email.body_full or email.body_preview or ''}"
        )
        text_content = text_content.lower()

        # Get all active topics with keywords
        topics_with_keywords = (
            db.session.query(Topic, TopicKeyword)
            .join(TopicKeyword)
            .filter(Topic.is_active == True)
            .all()
        )

        # Score each topic
        topic_scores = {}
        for topic, keyword in topics_with_keywords:
            if topic.id not in topic_scores:
                topic_scores[topic.id] = {"topic": topic, "score": 0.0, "matches": []}

            # Simple keyword matching
            if keyword.keyword.lower() in text_content:
                topic_scores[topic.id]["score"] += keyword.weight
                topic_scores[topic.id]["matches"].append(keyword.keyword)

        # Create assignments for topics with scores above threshold
        assignments = []
        threshold = 0.5  # Minimum score threshold

        for topic_data in topic_scores.values():
            if topic_data["score"] >= threshold:
                confidence = min(topic_data["score"] / 10.0, 1.0)  # Normalize to 0-1

                assignment = self.assign_topic_to_email(
                    email_id=email_id,
                    topic_id=topic_data["topic"].id,
                    confidence_score=confidence,
                    classification_method="keyword",
                    assigned_by="system",
                )
                assignments.append(assignment)

        return assignments

    def classify_emails_by_embeddings(
        self, email_ids: List[int], max_main_topics: int = 10, max_sub_topics: int = 20
    ) -> Dict:
        """Classify emails using embedding similarity and clustering"""

        # This is a simplified version - in a full implementation,
        # you'd use actual embedding vectors and clustering algorithms

        emails = EmailThread.query.filter(EmailThread.id.in_(email_ids)).all()

        results = {
            "classified_emails": 0,
            "new_topics": 0,
            "main_topics": [],
            "sub_topics": [],
        }

        # Group emails by existing embeddings (simplified)
        for email in emails:
            if email.has_embedding:
                # Use existing keyword classification as fallback
                assignments = self.classify_email_by_keywords(email.id)
                if assignments:
                    results["classified_emails"] += 1

        # Get topic statistics
        main_topics = self.get_topics_by_level(level=0)
        sub_topics = self.get_topics_by_level(level=1)

        results["main_topics"] = [
            {
                "name": topic.name,
                "count": topic.email_count,
                "emails": [a.email_id for a in topic.email_assignments],
            }
            for topic in main_topics[:max_main_topics]
        ]

        results["sub_topics"] = [
            {
                "name": topic.name,
                "count": topic.email_count,
                "emails": [a.email_id for a in topic.email_assignments],
            }
            for topic in sub_topics[:max_sub_topics]
        ]

        return results

    def add_keyword_to_topic(
        self, topic_id: int, keyword: str, weight: float = 1.0, created_by: str = None
    ) -> TopicKeyword:
        """Add a keyword to a topic for automatic classification"""

        # Check if keyword already exists
        existing = TopicKeyword.query.filter_by(
            topic_id=topic_id, keyword=keyword
        ).first()
        if existing:
            existing.weight = weight
            db.session.commit()
            return existing

        # Create new keyword
        topic_keyword = TopicKeyword(
            topic_id=topic_id, keyword=keyword, weight=weight, created_by=created_by
        )

        db.session.add(topic_keyword)
        db.session.commit()

        logger.info(f"Added keyword '{keyword}' to topic {topic_id}")
        return topic_keyword

    def remove_keyword_from_topic(self, topic_id: int, keyword: str) -> bool:
        """Remove a keyword from a topic"""

        topic_keyword = TopicKeyword.query.filter_by(
            topic_id=topic_id, keyword=keyword
        ).first()
        if topic_keyword:
            db.session.delete(topic_keyword)
            db.session.commit()
            logger.info(f"Removed keyword '{keyword}' from topic {topic_id}")
            return True

        return False

    def calculate_topic_similarity(
        self, topic1_id: int, topic2_id: int, method: str = "cooccurrence"
    ) -> float:
        """Calculate similarity between two topics"""

        if method == "cooccurrence":
            # Calculate based on email co-occurrence
            topic1_emails = set(
                a.email_id for a in EmailTopic.query.filter_by(topic_id=topic1_id).all()
            )
            topic2_emails = set(
                a.email_id for a in EmailTopic.query.filter_by(topic_id=topic2_id).all()
            )

            intersection = len(topic1_emails & topic2_emails)
            union = len(topic1_emails | topic2_emails)

            similarity = intersection / union if union > 0 else 0.0

        elif method == "keyword":
            # Calculate based on keyword overlap
            topic1_keywords = set(
                k.keyword
                for k in TopicKeyword.query.filter_by(topic_id=topic1_id).all()
            )
            topic2_keywords = set(
                k.keyword
                for k in TopicKeyword.query.filter_by(topic_id=topic2_id).all()
            )

            intersection = len(topic1_keywords & topic2_keywords)
            union = len(topic1_keywords | topic2_keywords)

            similarity = intersection / union if union > 0 else 0.0

        else:
            # Default to low similarity for unknown methods
            similarity = 0.0

        # Store similarity score
        self._store_similarity(topic1_id, topic2_id, similarity, method)

        return similarity

    def get_similar_topics(self, topic_id: int, threshold: float = 0.3) -> List[Dict]:
        """Get topics similar to the given topic"""

        similarities = (
            TopicSimilarity.query.filter(
                or_(
                    TopicSimilarity.topic1_id == topic_id,
                    TopicSimilarity.topic2_id == topic_id,
                ),
                TopicSimilarity.similarity_score >= threshold,
            )
            .order_by(desc(TopicSimilarity.similarity_score))
            .all()
        )

        results = []
        for sim in similarities:
            other_topic_id = (
                sim.topic2_id if sim.topic1_id == topic_id else sim.topic1_id
            )
            other_topic = Topic.query.get(other_topic_id)

            if other_topic:
                results.append(
                    {
                        "topic": other_topic.to_dict(),
                        "similarity_score": sim.similarity_score,
                        "calculation_method": sim.calculation_method,
                    }
                )

        return results

    def merge_topics(
        self, source_topic_id: int, target_topic_id: int, merged_by: str = None
    ) -> bool:
        """Merge one topic into another"""

        source_topic = Topic.query.get(source_topic_id)
        target_topic = Topic.query.get(target_topic_id)

        if not source_topic or not target_topic:
            return False

        # Move all email assignments
        EmailTopic.query.filter_by(topic_id=source_topic_id).update(
            {"topic_id": target_topic_id}
        )

        # Move all keywords
        TopicKeyword.query.filter_by(topic_id=source_topic_id).update(
            {"topic_id": target_topic_id}
        )

        # Update target topic email count
        target_topic.email_count = EmailTopic.query.filter_by(
            topic_id=target_topic_id
        ).count()

        # Deactivate source topic
        source_topic.is_active = False
        source_topic.updated_at = datetime.utcnow()

        db.session.commit()

        logger.info(f"Merged topic {source_topic_id} into {target_topic_id}")
        return True

    def delete_topic(self, topic_id: int, force: bool = False) -> bool:
        """Delete a topic and its relationships"""

        topic = Topic.query.get(topic_id)
        if not topic:
            return False

        # Check if topic has children
        if topic.children and not force:
            raise ValueError(
                "Cannot delete topic with children. Use force=True to delete hierarchy."
            )

        # Delete all relationships
        EmailTopic.query.filter_by(topic_id=topic_id).delete()
        TopicKeyword.query.filter_by(topic_id=topic_id).delete()
        TopicSimilarity.query.filter(
            or_(
                TopicSimilarity.topic1_id == topic_id,
                TopicSimilarity.topic2_id == topic_id,
            )
        ).delete()

        # Delete children if force
        if force:
            for child in topic.children:
                self.delete_topic(child.id, force=True)

        # Delete topic
        db.session.delete(topic)
        db.session.commit()

        logger.info(f"Deleted topic {topic_id}")
        return True

    def update_topic_statistics(self, topic_id: int = None) -> None:
        """Update email counts and last used dates for topics"""

        if topic_id:
            topics = [Topic.query.get(topic_id)]
        else:
            topics = Topic.query.all()

        for topic in topics:
            if topic:
                # Update email count
                topic.email_count = EmailTopic.query.filter_by(
                    topic_id=topic.id
                ).count()

                # Update last used
                last_assignment = (
                    EmailTopic.query.filter_by(topic_id=topic.id)
                    .order_by(desc(EmailTopic.assigned_at))
                    .first()
                )

                if last_assignment:
                    topic.last_used = last_assignment.assigned_at

        db.session.commit()

    def _generate_color_for_level(self, level: int) -> str:
        """Generate appropriate color for topic level"""

        colors = {
            0: [
                "#10B981",
                "#3B82F6",
                "#8B5CF6",
                "#F59E0B",
                "#EF4444",
                "#06B6D4",
                "#84CC16",
                "#EC4899",
            ],
            1: [
                "#6EE7B7",
                "#93C5FD",
                "#C4B5FD",
                "#FCD34D",
                "#FCA5A5",
                "#67E8F9",
                "#BEF264",
                "#F9A8D4",
            ],
            2: [
                "#A7F3D0",
                "#DBEAFE",
                "#E0E7FF",
                "#FEF3C7",
                "#FEE2E2",
                "#CFFAFE",
                "#ECFCCB",
                "#FCE7F3",
            ],
        }

        level_colors = colors.get(level, colors[0])
        return level_colors[hash(str(level)) % len(level_colors)]

    def _store_similarity(
        self, topic1_id: int, topic2_id: int, similarity_score: float, method: str
    ) -> None:
        """Store similarity score between topics"""

        # Ensure consistent ordering
        if topic1_id > topic2_id:
            topic1_id, topic2_id = topic2_id, topic1_id

        # Check if similarity already exists
        existing = TopicSimilarity.query.filter_by(
            topic1_id=topic1_id, topic2_id=topic2_id
        ).first()

        if existing:
            existing.similarity_score = similarity_score
            existing.calculation_method = method
            existing.calculated_at = datetime.utcnow()
        else:
            similarity = TopicSimilarity(
                topic1_id=topic1_id,
                topic2_id=topic2_id,
                similarity_score=similarity_score,
                calculation_method=method,
            )
            db.session.add(similarity)

        db.session.commit()


# Global instance
_topic_service = None


def get_topic_service() -> TopicService:
    """Get the global topic service instance"""
    global _topic_service
    if _topic_service is None:
        _topic_service = TopicService()
    return _topic_service
