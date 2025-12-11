"""FastAPI routes for Resume Roast application."""

import json
import logging
from datetime import datetime, UTC
from typing import Any, AsyncGenerator, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.schemas import (
    HealthCheckResponse,
    ResumeSchema,
    FeedbackSessionSchema,
    AgentFeedbackRequest,
    AgentStreamResponse,
)
from database import get_db
from repositories import ResumeRepository, FeedbackRepository
from services import PDFService, S3Service
from agents import AgentOrchestrator
from .dependencies import (
    get_pdf_service,
    get_s3_service,
    get_agent_orchestrator,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    return HealthCheckResponse(
        status="healthy",
        timestamp=datetime.now(UTC),
        version="0.1.0"
    )


@router.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(..., description="PDF resume file"),
    job_description: str = Form(..., min_length=10, max_length=10000),
    pdf_service: PDFService = Depends(get_pdf_service),
    s3_service: S3Service = Depends(get_s3_service),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Upload resume and job description, then start agent analysis.
    Returns session_id for streaming the agent responses.
    """
    try:
        # Create repositories with shared session
        resume_repo = ResumeRepository(db)
        feedback_repo = FeedbackRepository(db)
        
        # Validate file type
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400, 
                detail="Only PDF files are allowed. Please upload a .pdf file."
            )
        
        # Validate content type
        if file.content_type and not file.content_type.startswith('application/pdf'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Please upload a PDF file."
            )
        
        # Validate job description
        pdf_service.validate_job_description(job_description)
        
        # Read and parse PDF
        pdf_content = await file.read()
        if not pdf_content:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty. Please upload a valid PDF."
            )
        
        pdf_data = await pdf_service.extract_text_from_pdf(pdf_content)
        
        # Upload to S3
        s3_url = await s3_service.upload_pdf(pdf_content, file.filename)
        
        # Create resume record
        resume = await resume_repo.create_resume(
            filename=file.filename,
            text_content=pdf_data["text_content"],
            s3_url=s3_url,
            job_description=job_description
        )
        # Create feedback session
        try:
            feedback_session = await feedback_repo.create_feedback_session(resume.id)
            logger.info(
                "Created session %s for resume %s", 
                feedback_session.id, 
                resume.id
            )
        except Exception as e:
            logger.error("Failed to create feedback session: %s", str(e))
            raise HTTPException(
                status_code=500, 
                detail="Failed to create feedback session"
            )
        
        # Explicitly commit the transaction
        try:
            await db.commit()
            logger.info("Resume upload transaction committed successfully")
        except Exception as e:
            logger.error("Transaction failed: %s", str(e))
            await db.rollback()
            raise HTTPException(
                status_code=500, 
                detail="Database transaction failed"
            )
        
        return {
            "session_id": str(feedback_session.id),
            "resume_id": str(resume.id),
            "message": "Resume uploaded successfully. Use session_id to stream agent responses.",
            "metadata": pdf_data["metadata"]
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get("/stream-analysis/{session_id}")
async def stream_analysis(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    agent_orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
) -> StreamingResponse:
    """
    Stream agent analysis responses for a given session.
    Returns Server-Sent Events with agent responses.
    """
    try:
        # Create repositories with shared session
        feedback_repo = FeedbackRepository(db)
        resume_repo = ResumeRepository(db)
        
        # Get feedback session and resume
        feedback_session = await feedback_repo.get_feedback_session_by_id(session_id)
        if not feedback_session:
            raise HTTPException(status_code=404, detail="Feedback session not found")

        resume = await resume_repo.get_resume_by_id(feedback_session.resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        # Get memory context
        memory_learnings = await feedback_repo.get_aggregated_learnings(limit=10)
        memory_context = [learning.description for learning in memory_learnings]
        
        # Log agent memory context - essential for system monitoring
        logger.info(
            "Session %s: Using %d memory patterns", 
            session_id, 
            len(memory_context)
        )
        for i, context in enumerate(memory_context[:3]):  # Show first 3 patterns
            logger.info("  Pattern %d: %s", i + 1, context)
        
        async def generate_stream() -> AsyncGenerator[str, None]:
            """Generate Server-Sent Events stream."""
            try:
                agent_responses = {}
                
                async for response_data in agent_orchestrator.execute_debate(
                    resume.text_content,
                    resume.job_description,
                    memory_context
                ):
                    # Store complete responses for database
                    if response_data["is_complete"] and response_data["agent_name"] != "Workflow":
                        agent_name = response_data["agent_name"]
                        if agent_name in agent_responses:
                            # Save to database
                            await feedback_repo.add_agent_response(
                                session_id=session_id,
                                agent_name=agent_name,
                                response_text=agent_responses[agent_name],
                                order=response_data["order"]
                            )
                    
                    # Accumulate responses
                    if not response_data["is_complete"]:
                        agent_name = response_data["agent_name"]
                        if agent_name not in agent_responses:
                            agent_responses[agent_name] = ""
                        agent_responses[agent_name] += response_data["chunk"]
                    
                    # Stream to client
                    event_data = json.dumps(response_data, default=str)
                    yield f"data: {event_data}\n\n"
                
                # Mark session as completed
                await feedback_repo.complete_feedback_session(session_id)
                
            except Exception as e:
                error_data = {
                    "error": True,
                    "message": str(e)
                }
                yield f"data: {json.dumps(error_data)}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Streaming error: {str(e)}")


@router.post("/submit-feedback")
async def submit_feedback(
    feedback_request: AgentFeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    """Submit user feedback for an agent response."""
    try:
        feedback_repo = FeedbackRepository(db)
        
        # Find the agent response by session_id and agent_name
        agent_response = await feedback_repo.get_agent_response_by_session_and_name(
            session_id=feedback_request.session_id,
            agent_name=feedback_request.agent_name
        )
        
        if not agent_response:
            raise HTTPException(
                status_code=404, 
                detail=(
                    f"Agent response not found for {feedback_request.agent_name} "
                    f"in session {feedback_request.session_id}"
                )
            )
        
        updated_response = await feedback_repo.update_agent_feedback(
            response_id=agent_response.id,
            thumbs_up=feedback_request.thumbs_up,
            feedback_text=feedback_request.feedback_text
        )
        
        if not updated_response:
            raise HTTPException(status_code=404, detail="Failed to update agent response")
        
        # Always process feedback for learning - convert like/dislike to pattern
        pattern_type = "positive_feedback" if feedback_request.thumbs_up else "negative_feedback"
        confidence_score = 0.8 if feedback_request.thumbs_up else 0.3
        
        # Use feedback text as description if provided, otherwise use default message
        if feedback_request.feedback_text:
            description = feedback_request.feedback_text[:200]
            feedback_preview = (
                feedback_request.feedback_text[:50] + "..." 
                if len(feedback_request.feedback_text) > 50 
                else feedback_request.feedback_text
            )
        else:
            description = f"User gave {'positive' if feedback_request.thumbs_up else 'negative'} feedback"
            feedback_preview = description
        
        logger.info(
            "Learning: %s feedback for %s - '%s'",
            pattern_type,
            feedback_request.agent_name,
            feedback_preview
        )
        
        await feedback_repo.create_or_update_learning(
            pattern_type=pattern_type,
            description=description,
            agent_name=updated_response.agent_name,
            confidence_score=confidence_score
        )
        
        return {
            "message": "Feedback submitted successfully",
            "response_id": str(updated_response.id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feedback submission error: {str(e)}")



@router.get("/session/{session_id}", response_model=FeedbackSessionSchema)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get feedback session with all agent responses."""
    feedback_repo = FeedbackRepository(db)
    feedback_session = await feedback_repo.get_feedback_session_by_id(session_id)
    if not feedback_session:
        raise HTTPException(status_code=404, detail="Feedback session not found")
    
    return feedback_session


@router.get("/resume/{resume_id}", response_model=ResumeSchema)
async def get_resume(
    resume_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get resume with all feedback sessions."""
    resume_repo = ResumeRepository(db)
    resume = await resume_repo.get_resume_by_id(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    return resume