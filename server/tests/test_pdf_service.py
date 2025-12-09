"""Tests for PDF service."""

import pytest
from unittest.mock import patch, mock_open

from services import PDFService


class TestPDFService:
    """Test cases for PDF service."""
    
    def test_init(self):
        """Test PDF service initialization."""
        service = PDFService()
        assert service.settings is not None
    
    @pytest.mark.asyncio
    async def test_extract_text_from_pdf_success(self):
        """Test successful PDF text extraction."""
        service = PDFService()
        
        # Mock PDF content
        mock_pdf_content = b"%PDF-1.4 mock content"
        
        with patch('services.pdf_service.PdfReader') as mock_reader:
            # Mock PDF reader and pages
            mock_page = type('MockPage', (), {})()
            mock_page.extract_text = lambda: "Sample resume text with experience and skills."
            
            mock_reader.return_value.pages = [mock_page]
            mock_reader.return_value.metadata = {
                "/Title": "Resume",
                "/Author": "John Doe"
            }
            
            result = await service.extract_text_from_pdf(mock_pdf_content)
            
            assert "text_content" in result
            assert "metadata" in result
            assert "Page 1:" in result["text_content"]
            assert result["metadata"]["page_count"] == 1
            assert result["metadata"]["title"] == "Resume"
            assert result["metadata"]["author"] == "John Doe"
    
    @pytest.mark.asyncio
    async def test_extract_text_empty_pdf(self):
        """Test PDF with no pages raises error."""
        service = PDFService()
        
        with patch('services.pdf_service.PdfReader') as mock_reader:
            mock_reader.return_value.pages = []
            
            with pytest.raises(ValueError, match="PDF contains no pages"):
                await service.extract_text_from_pdf(b"mock content")
    
    @pytest.mark.asyncio 
    async def test_extract_text_no_extractable_text(self):
        """Test PDF with no extractable text raises error."""
        service = PDFService()
        
        with patch('services.pdf_service.PdfReader') as mock_reader:
            mock_page = type('MockPage', (), {})()
            mock_page.extract_text = lambda: ""  # Empty text
            
            mock_reader.return_value.pages = [mock_page]
            
            with pytest.raises(ValueError, match="No text content could be extracted"):
                await service.extract_text_from_pdf(b"mock content")
    
    @pytest.mark.asyncio
    async def test_extract_text_token_limit_exceeded(self):
        """Test PDF exceeding token limit raises error."""
        service = PDFService()
        
        with patch('services.pdf_service.PdfReader') as mock_reader:
            # Create very long text that exceeds token limit
            long_text = " ".join(["word"] * 20000)  # Exceeds 15k token limit
            
            mock_page = type('MockPage', (), {})()
            mock_page.extract_text = lambda: long_text
            
            mock_reader.return_value.pages = [mock_page]
            mock_reader.return_value.metadata = None
            
            with pytest.raises(ValueError, match="Resume text too long"):
                await service.extract_text_from_pdf(b"mock content")
    
    def test_validate_job_description_success(self):
        """Test successful job description validation."""
        service = PDFService()
        
        job_desc = "Looking for a Python developer with 3+ years experience."
        service.validate_job_description(job_desc)  # Should not raise
    
    def test_validate_job_description_empty(self):
        """Test empty job description raises error."""
        service = PDFService()
        
        with pytest.raises(ValueError, match="Job description cannot be empty"):
            service.validate_job_description("")
        
        with pytest.raises(ValueError, match="Job description cannot be empty"):
            service.validate_job_description("   ")
    
    def test_validate_job_description_too_long(self):
        """Test job description exceeding token limit raises error.""" 
        service = PDFService()
        
        # Create long job description that exceeds 5k token limit
        long_desc = " ".join(["requirement"] * 8000)
        
        with pytest.raises(ValueError, match="Job description too long"):
            service.validate_job_description(long_desc)