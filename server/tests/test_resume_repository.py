"""Tests for resume repository."""

import pytest
from uuid import uuid4

from repositories import ResumeRepository
from core.models import Resume


class TestResumeRepository:
    """Test cases for resume repository."""
    
    @pytest.mark.asyncio
    async def test_create_resume_success(self, resume_repository, sample_resume_data):
        """Test successful resume creation."""
        resume = await resume_repository.create_resume(
            filename=sample_resume_data["filename"],
            text_content=sample_resume_data["text_content"],
            s3_url=sample_resume_data["s3_url"],
            job_description=sample_resume_data["job_description"]
        )
        
        assert resume.id is not None
        assert resume.filename == sample_resume_data["filename"]
        assert resume.text_content == sample_resume_data["text_content"]
        assert resume.s3_url == sample_resume_data["s3_url"]
        assert resume.job_description == sample_resume_data["job_description"]
        assert resume.uploaded_at is not None
    
    @pytest.mark.asyncio
    async def test_create_resume_missing_fields(self, resume_repository):
        """Test resume creation with missing fields raises error."""
        with pytest.raises(ValueError, match="Filename is required"):
            await resume_repository.create_resume("", "text", "url", "job")
        
        with pytest.raises(ValueError, match="Text content is required"):
            await resume_repository.create_resume("file", "", "url", "job")
    
    @pytest.mark.asyncio
    async def test_get_resume_by_id_success(self, resume_repository, sample_resume_data):
        """Test successful resume retrieval by ID."""
        # Create resume
        created_resume = await resume_repository.create_resume(**sample_resume_data)
        
        # Retrieve resume
        found_resume = await resume_repository.get_resume_by_id(created_resume.id)
        
        assert found_resume is not None
        assert found_resume.id == created_resume.id
        assert found_resume.filename == sample_resume_data["filename"]
    
    @pytest.mark.asyncio
    async def test_get_resume_by_id_not_found(self, resume_repository):
        """Test resume retrieval with non-existent ID returns None."""
        non_existent_id = uuid4()
        result = await resume_repository.get_resume_by_id(non_existent_id)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_recent_resumes(self, resume_repository, sample_resume_data):
        """Test retrieval of recent resumes."""
        # Create multiple resumes
        resume1 = await resume_repository.create_resume(**sample_resume_data)
        
        sample_resume_data["filename"] = "second_resume.pdf"
        resume2 = await resume_repository.create_resume(**sample_resume_data)
        
        # Get recent resumes
        recent = await resume_repository.get_recent_resumes(limit=5)
        
        assert len(recent) == 2
        # Should contain both resumes (order may vary due to timestamp precision)
        resume_ids = {r.id for r in recent}
        assert resume1.id in resume_ids
        assert resume2.id in resume_ids
    
    @pytest.mark.asyncio
    async def test_delete_resume_success(self, resume_repository, sample_resume_data):
        """Test successful resume deletion."""
        # Create resume
        resume = await resume_repository.create_resume(**sample_resume_data)
        
        # Delete resume
        result = await resume_repository.delete_resume(resume.id)
        assert result is True
        
        # Verify deletion
        found = await resume_repository.get_resume_by_id(resume.id)
        assert found is None
    
    @pytest.mark.asyncio
    async def test_delete_resume_not_found(self, resume_repository):
        """Test deletion of non-existent resume returns False."""
        non_existent_id = uuid4()
        result = await resume_repository.delete_resume(non_existent_id)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_search_resumes_by_text(self, resume_repository, sample_resume_data):
        """Test resume search by text content."""
        # Create resume with specific content
        sample_resume_data["text_content"] = "Python developer with Django and FastAPI experience"
        resume = await resume_repository.create_resume(**sample_resume_data)
        
        # Search for 'Python'
        results = await resume_repository.search_resumes_by_text("Python")
        assert len(results) == 1
        assert results[0].id == resume.id
        
        # Search for 'Django'
        results = await resume_repository.search_resumes_by_text("Django")
        assert len(results) == 1
        
        # Search for non-existent term
        results = await resume_repository.search_resumes_by_text("Java")
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_search_resumes_empty_term(self, resume_repository):
        """Test search with empty term returns empty list."""
        results = await resume_repository.search_resumes_by_text("")
        assert results == []
        
        results = await resume_repository.search_resumes_by_text("   ")
        assert results == []