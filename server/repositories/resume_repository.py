"""Repository for resume-related database operations."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.models import Resume


class ResumeRepository:
    """Repository for resume database operations following repository pattern.
    
    This repository handles all database operations related to resumes,
    including CRUD operations and search functionality.
    """
    
    def __init__(self, db_session: AsyncSession) -> None:
        """Initialize the repository with a database session."""
        self.db_session = db_session
    
    async def create_resume(
        self, 
        filename: str, 
        text_content: str, 
        s3_url: str, 
        job_description: str
    ) -> Resume:
        """
        Create a new resume record.
        
        Args:
            filename: Original filename of the uploaded PDF
            text_content: Extracted text from the PDF
            s3_url: S3 URL where PDF is stored
            job_description: Job description provided by user
            
        Returns:
            Created Resume instance
            
        Raises:
            ValueError: If required fields are missing
        """
        # Validate inputs
        if not filename or not filename.strip():
            raise ValueError("Filename is required")
        if not text_content or not text_content.strip():
            raise ValueError("Text content is required")
        if not s3_url or not s3_url.strip():
            raise ValueError("S3 URL is required")
        if not job_description or not job_description.strip():
            raise ValueError("Job description is required")
        
        resume = Resume(
            filename=filename.strip(),
            text_content=text_content.strip(),
            s3_url=s3_url.strip(),
            job_description=job_description.strip()
        )
        
        self.db_session.add(resume)
        await self.db_session.flush()  # Get the ID without committing
        await self.db_session.refresh(resume)
        
        return resume
    
    async def get_resume_by_id(self, resume_id: UUID) -> Optional[Resume]:
        """
        Get resume by ID with all related feedback sessions.
        
        Args:
            resume_id: UUID of the resume
            
        Returns:
            Resume instance or None if not found
        """
        stmt = (
            select(Resume)
            .options(selectinload(Resume.feedback_sessions))
            .where(Resume.id == resume_id)
        )
        
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_recent_resumes(self, limit: int = 10) -> List[Resume]:
        """
        Get most recently uploaded resumes.
        
        Args:
            limit: Maximum number of resumes to return (1-100)
            
        Returns:
            List of Resume instances ordered by upload time (newest first)
            
        Raises:
            ValueError: If limit is invalid
        """
        if limit < 1 or limit > 100:
            raise ValueError("Limit must be between 1 and 100")
        stmt = (
            select(Resume)
            .options(selectinload(Resume.feedback_sessions))
            .order_by(desc(Resume.uploaded_at))
            .limit(limit)
        )
        
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())
    
    async def delete_resume(self, resume_id: UUID) -> bool:
        """
        Delete resume and all associated feedback sessions.
        
        Args:
            resume_id: UUID of the resume to delete
            
        Returns:
            True if deletion successful, False if resume not found
        """
        resume = await self.get_resume_by_id(resume_id)
        if not resume:
            return False
        
        await self.db_session.delete(resume)
        return True
    
    async def search_resumes_by_text(self, search_term: str, limit: int = 10) -> List[Resume]:
        """
        Search resumes by text content or job description.
        
        Args:
            search_term: Text to search for
            limit: Maximum number of results
            
        Returns:
            List of matching Resume instances
        """
        if not search_term.strip():
            return []
        
        search_pattern = f"%{search_term.strip()}%"
        
        stmt = (
            select(Resume)
            .where(
                Resume.text_content.ilike(search_pattern) |
                Resume.job_description.ilike(search_pattern) |
                Resume.filename.ilike(search_pattern)
            )
            .order_by(desc(Resume.uploaded_at))
            .limit(limit)
        )
        
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())