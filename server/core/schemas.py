"""Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ResumeUpload(BaseModel):
    """Schema for resume upload request."""
    
    job_description: str = Field(
        ..., 
        description="Job description to match resume against",
        min_length=10,
        max_length=10000
    )


class AgentResponseSchema(BaseModel):
    """Schema for agent response.
    
    Attributes:
        id: Unique identifier for the response
        agent_name: Name of the agent (Critic, Advocate, Realist)
        response_text: Full response text from the agent
        order: Order of response in the debate sequence
        thumbs_up: User feedback (True=liked, False=disliked, None=no feedback)
        feedback_text: Optional user feedback text
        created_at: When the response was created
    """
    
    id: UUID
    agent_name: str = Field(..., min_length=1, max_length=50)
    response_text: str = Field(..., min_length=1)
    order: int = Field(..., ge=0)
    thumbs_up: Optional[bool] = None
    feedback_text: Optional[str] = Field(None, max_length=500)
    created_at: datetime
    
    model_config = {"from_attributes": True}


class FeedbackSessionSchema(BaseModel):
    """Schema for feedback session.
    
    Attributes:
        id: Unique identifier for the session
        resume_id: ID of associated resume
        status: Current status (in_progress, completed, failed)
        created_at: When the session was created
        completed_at: When the session was completed (if applicable)
        agent_responses: List of agent responses in this session
    """
    
    id: UUID
    resume_id: UUID
    status: str = Field(..., pattern=r'^(in_progress|completed|failed)$')
    created_at: datetime
    completed_at: Optional[datetime] = None
    agent_responses: List[AgentResponseSchema] = []
    
    model_config = {"from_attributes": True}


class ResumeSchema(BaseModel):
    """Schema for resume."""
    
    id: UUID
    filename: str
    text_content: str
    s3_url: str
    job_description: str
    uploaded_at: datetime
    feedback_sessions: List[FeedbackSessionSchema] = []
    
    model_config = {"from_attributes": True}


class AgentFeedbackRequest(BaseModel):
    """Schema for agent feedback submission.
    
    Attributes:
        session_id: ID of the feedback session
        agent_name: Name of the agent (must be Critic, Advocate, or Realist)
        thumbs_up: Whether user liked the response
        feedback_text: Optional detailed feedback text
    """
    
    session_id: UUID = Field(..., description="ID of the feedback session")
    agent_name: str = Field(
        ..., 
        pattern=r'^(Critic|Advocate|Realist)$',
        description="Name of the agent (Critic, Advocate, Realist)"
    )
    thumbs_up: bool = Field(..., description="Whether user liked the response")
    feedback_text: Optional[str] = Field(
        None, 
        description="Optional text feedback",
        max_length=500
    )


class HealthCheckResponse(BaseModel):
    """Schema for health check response."""
    
    status: str = "healthy"
    timestamp: datetime
    version: str = "0.1.0"


class AgentStreamResponse(BaseModel):
    """Schema for streaming agent responses."""
    
    agent_name: str
    chunk: str
    is_complete: bool = False
    order: int