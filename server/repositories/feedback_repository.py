"""Repository for feedback-related database operations."""

from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, desc, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.models import FeedbackSession, AgentResponse, AggregatedLearning


class FeedbackRepository:
    """Repository for feedback database operations following repository pattern.
    
    This repository handles all database operations related to feedback sessions,
    agent responses, and learning patterns.
    """
    
    def __init__(self, db_session: AsyncSession) -> None:
        """Initialize the repository with a database session."""
        self.db_session = db_session
    
    async def create_feedback_session(self, resume_id: UUID) -> FeedbackSession:
        """
        Create a new feedback session.
        
        Args:
            resume_id: UUID of the associated resume
            
        Returns:
            Created FeedbackSession instance
            
        Raises:
            ValueError: If resume_id is invalid
        """
        if not resume_id:
            raise ValueError("Resume ID is required")
        session = FeedbackSession(
            resume_id=resume_id,
            status="in_progress"
        )
        
        self.db_session.add(session)
        await self.db_session.flush()
        await self.db_session.refresh(session)
        
        return session
    
    async def add_agent_response(
        self,
        session_id: UUID,
        agent_name: str,
        response_text: str,
        order: int
    ) -> AgentResponse:
        """
        Add an agent response to a feedback session.
        
        Args:
            session_id: UUID of the feedback session
            agent_name: Name of the agent (Critic, Advocate, Realist)
            response_text: Full response text
            order: Order in the debate sequence
            
        Returns:
            Created AgentResponse instance
            
        Raises:
            ValueError: If inputs are invalid
        """
        # Validate inputs
        if not session_id:
            raise ValueError("Session ID is required")
        if not agent_name or not agent_name.strip():
            raise ValueError("Agent name is required")
        if not response_text or not response_text.strip():
            raise ValueError("Response text is required")
        if order < 0:
            raise ValueError("Order must be non-negative")
        response = AgentResponse(
            session_id=session_id,
            agent_name=agent_name.lower(),
            response_text=response_text,
            order=order
        )
        
        self.db_session.add(response)
        await self.db_session.flush()
        await self.db_session.refresh(response)
        
        return response
    
    async def complete_feedback_session(self, session_id: UUID) -> Optional[FeedbackSession]:
        """
        Mark feedback session as completed.
        
        Args:
            session_id: UUID of the feedback session
            
        Returns:
            Updated FeedbackSession or None if not found
        """
        session = await self.get_feedback_session_by_id(session_id)
        if not session:
            return None
        
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        
        return session
    
    async def get_feedback_session_by_id(self, session_id: UUID) -> Optional[FeedbackSession]:
        """
        Get feedback session by ID with all agent responses.
        
        Args:
            session_id: UUID of the feedback session
            
        Returns:
            FeedbackSession instance or None if not found
        """
        stmt = (
            select(FeedbackSession)
            .options(selectinload(FeedbackSession.agent_responses))
            .where(FeedbackSession.id == session_id)
        )
        
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def update_agent_feedback(
        self,
        response_id: UUID,
        thumbs_up: bool,
        feedback_text: Optional[str] = None
    ) -> Optional[AgentResponse]:
        """
        Update agent response with user feedback.
        
        Args:
            response_id: UUID of the agent response
            thumbs_up: Whether user liked the response
            feedback_text: Optional text feedback
            
        Returns:
            Updated AgentResponse or None if not found
        """
        stmt = select(AgentResponse).where(AgentResponse.id == response_id)
        result = await self.db_session.execute(stmt)
        response = result.scalar_one_or_none()
        
        if not response:
            return None
        
        response.thumbs_up = thumbs_up
        response.feedback_text = feedback_text
        
        return response
    
    async def get_agent_response_by_session_and_name(
        self,
        session_id: UUID,
        agent_name: str
    ) -> Optional[AgentResponse]:
        """
        Get agent response by session ID and agent name.
        
        Args:
            session_id: UUID of the feedback session
            agent_name: Name of the agent (Critic, Advocate, Realist)
            
        Returns:
            AgentResponse or None if not found
        """
        stmt = select(AgentResponse).where(
            AgentResponse.session_id == session_id,
            AgentResponse.agent_name == agent_name.lower()
        )
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_aggregated_learnings(
        self, 
        agent_name: Optional[str] = None,
        limit: int = 100
    ) -> List[AggregatedLearning]:
        """
        Get aggregated learning patterns for agent memory.
        
        Args:
            agent_name: Optional filter by agent name
            limit: Maximum number of learnings to return
            
        Returns:
            List of AggregatedLearning instances ordered by frequency and last_updated
        """
        stmt = (
            select(AggregatedLearning)
            .order_by(desc(AggregatedLearning.frequency), desc(AggregatedLearning.last_updated))
            .limit(limit)
        )
        
        if agent_name:
            stmt = stmt.where(AggregatedLearning.agent_name == agent_name.lower())
        
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())
    
    async def create_or_update_learning(
        self,
        pattern_type: str,
        description: str,
        agent_name: str,
        confidence_score: float = 0.5
    ) -> AggregatedLearning:
        """
        Create new learning or update existing one by incrementing frequency.
        
        Args:
            pattern_type: Type of pattern (e.g., 'positive_feedback', 'negative_feedback')
            description: Description of the learning pattern
            agent_name: Name of the agent this applies to
            confidence_score: Confidence score for this pattern
            
        Returns:
            Created or updated AggregatedLearning instance
        """
        # Try to find existing learning with same pattern and description
        stmt = select(AggregatedLearning).where(
            and_(
                AggregatedLearning.pattern_type == pattern_type,
                AggregatedLearning.description == description,
                AggregatedLearning.agent_name == agent_name.lower()
            )
        )
        
        result = await self.db_session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing learning
            existing.frequency += 1
            existing.confidence_score = max(
                existing.confidence_score, 
                min(confidence_score, 0.95)  # Cap at 0.95
            )
            existing.last_updated = datetime.utcnow()
            return existing
        else:
            # Create new learning
            learning = AggregatedLearning(
                pattern_type=pattern_type,
                description=description,
                agent_name=agent_name.lower(),
                confidence_score=confidence_score,
                frequency=1
            )
            
            self.db_session.add(learning)
            await self.db_session.flush()
            await self.db_session.refresh(learning)
            
            return learning