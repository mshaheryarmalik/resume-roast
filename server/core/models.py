"""SQLAlchemy models for the Resume Roast application."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Resume(Base):
    """Resume model for storing uploaded resumes."""
    
    __tablename__ = "resumes"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    s3_url: Mapped[str] = mapped_column(String(500), nullable=False)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    
    # Relationships
    feedback_sessions: Mapped[list["FeedbackSession"]] = relationship(
        "FeedbackSession", 
        back_populates="resume",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        """String representation of Resume."""
        return f"<Resume(id={self.id}, filename='{self.filename}')>"


class FeedbackSession(Base):
    """Feedback session model for tracking agent debates."""
    
    __tablename__ = "feedback_sessions"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    resume_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("resumes.id"), 
        nullable=False,
        index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), 
        nullable=False, 
        default="in_progress"
    )  # in_progress, completed, failed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
        nullable=True
    )
    
    # Relationships
    resume: Mapped["Resume"] = relationship("Resume", back_populates="feedback_sessions")
    agent_responses: Mapped[list["AgentResponse"]] = relationship(
        "AgentResponse", 
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AgentResponse.order"
    )
    
    def __repr__(self) -> str:
        """String representation of FeedbackSession."""
        return f"<FeedbackSession(id={self.id}, status='{self.status}')>"


class AgentResponse(Base):
    """Agent response model for storing individual agent critiques."""
    
    __tablename__ = "agent_responses"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    session_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("feedback_sessions.id"), 
        nullable=False,
        index=True
    )
    agent_name: Mapped[str] = mapped_column(
        String(50), 
        nullable=False
    )  # critic, advocate, realist
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    thumbs_up: Mapped[Optional[bool]] = mapped_column(nullable=True)
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    
    # Relationships
    session: Mapped["FeedbackSession"] = relationship(
        "FeedbackSession", 
        back_populates="agent_responses"
    )
    
    def __repr__(self) -> str:
        """String representation of AgentResponse."""
        return f"<AgentResponse(id={self.id}, agent='{self.agent_name}', order={self.order})>"


class AggregatedLearning(Base):
    """Aggregated learning model for storing feedback patterns."""
    
    __tablename__ = "aggregated_learnings"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    pattern_type: Mapped[str] = mapped_column(
        String(100), 
        nullable=False
    )  # positive_feedback, negative_feedback, skill_gap, etc.
    description: Mapped[str] = mapped_column(Text, nullable=False)
    frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    confidence_score: Mapped[float] = mapped_column(
        Float, 
        nullable=False, 
        default=0.5
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now()
    )
    
    def __repr__(self) -> str:
        return f"<AggregatedLearning(pattern_type='{self.pattern_type}', agent='{self.agent_name}')>"