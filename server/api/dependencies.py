"""FastAPI route dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agents import AgentOrchestrator
from database import get_db
from repositories import FeedbackRepository, ResumeRepository
from services import LLMService, PDFService, S3Service


def get_resume_repository(
    db: AsyncSession = Depends(get_db)
) -> ResumeRepository:
    """Get resume repository instance."""
    return ResumeRepository(db)


def get_feedback_repository(
    db: AsyncSession = Depends(get_db)
) -> FeedbackRepository:
    """Get feedback repository instance."""
    return FeedbackRepository(db)


def get_pdf_service() -> PDFService:
    """Get PDF service instance."""
    return PDFService()


def get_s3_service() -> S3Service:
    """Get S3 service instance."""
    return S3Service()


def get_llm_service() -> LLMService:
    """Get LLM service instance."""
    return LLMService()


def get_agent_orchestrator(
    llm_service: LLMService = Depends(get_llm_service)
) -> AgentOrchestrator:
    """Get agent orchestrator instance."""
    return AgentOrchestrator(llm_service)