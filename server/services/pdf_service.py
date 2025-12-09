"""PDF parsing service for extracting text from uploaded PDFs."""

import logging
from io import BytesIO
from typing import Dict, Any

from pypdf import PdfReader

from config import get_settings

logger = logging.getLogger(__name__)


class PDFService:
    """Service responsible for PDF parsing operations.
    
    This service handles PDF text extraction and validation,
    ensuring that PDFs meet size and content requirements.
    """
    
    def __init__(self) -> None:
        """Initialize the PDF service."""
        self.settings = get_settings()
    
    async def extract_text_from_pdf(self, pdf_content: bytes) -> Dict[str, Any]:
        """
        Extract text content from PDF bytes.
        
        Args:
            pdf_content: PDF file as bytes
            
        Returns:
            Dictionary containing extracted text and metadata
            
        Raises:
            ValueError: If PDF is invalid or corrupted
            RuntimeError: If text extraction fails
        """
        # Input validation
        if not pdf_content:
            raise ValueError("PDF content cannot be empty")
        
        if len(pdf_content) > 50 * 1024 * 1024:  # 50MB limit
            raise ValueError("PDF file too large (limit: 50MB)")
            
        try:
            pdf_stream = BytesIO(pdf_content)
            reader = PdfReader(pdf_stream)
            
            # Validate PDF
            if len(reader.pages) == 0:
                raise ValueError("PDF contains no pages")
            
            # Extract text from all pages
            text_content = []
            for page_num, page in enumerate(reader.pages, 1):
                try:
                    page_text = page.extract_text()
                    if page_text.strip():
                        text_content.append(f"Page {page_num}:\n{page_text}")
                except Exception as e:
                    # Log warning but continue with other pages
                    logger.warning(
                        "Could not extract text from page %d: %s", 
                        page_num, 
                        str(e)
                    )
            
            if not text_content:
                raise ValueError("No text content could be extracted from PDF")
            
            full_text = "\n\n".join(text_content)
            
            # Check token limits with better estimation
            estimated_tokens = self._estimate_tokens(full_text)
            if estimated_tokens > self.settings.resume_token_limit:
                raise ValueError(
                    f"Resume text too long: {estimated_tokens} tokens "
                    f"(limit: {self.settings.resume_token_limit})"
                )
            
            # Extract metadata
            metadata = {
                "page_count": len(reader.pages),
                "text_length": len(full_text),
                "estimated_tokens": estimated_tokens,
            }
            
            # Add PDF metadata if available
            if reader.metadata:
                metadata.update({
                    "title": reader.metadata.get("/Title", ""),
                    "author": reader.metadata.get("/Author", ""),
                    "creator": reader.metadata.get("/Creator", ""),
                })
            
            return {
                "text_content": full_text,
                "metadata": metadata,
            }
            
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from PDF: {str(e)}")
    
    def validate_job_description(self, job_description: str) -> None:
        """
        Validate job description length.
        
        Args:
            job_description: Job description text
            
        Raises:
            ValueError: If job description is invalid
        """
        if not job_description or not job_description.strip():
            raise ValueError("Job description cannot be empty")
        
        estimated_tokens = len(job_description.split())
        estimated_tokens = self._estimate_tokens(job_description)
        if estimated_tokens > self.settings.job_description_token_limit:
            raise ValueError(
                f"Job description too long: {estimated_tokens} tokens "
                f"(limit: {self.settings.job_description_token_limit})"
            )
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        # More accurate estimation: ~0.75 words per token
        return int(len(text.split()) * 1.33)