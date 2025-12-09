"""Test configuration and fixtures."""

import pytest
import asyncio
from typing import AsyncGenerator
from unittest.mock import Mock, AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient

from database import Base
from main import app
from services import PDFService, S3Service, LLMService
from repositories import ResumeRepository, FeedbackRepository
from unittest.mock import patch


# Test database URL (use in-memory SQLite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""
    from httpx import ASGITransport
    
    # Mock services to avoid filesystem and external operations
    with patch('services.s3_service.S3Service.__init__', return_value=None), \
         patch('services.s3_service.S3Service.upload_pdf', new_callable=AsyncMock) as mock_s3_upload, \
         patch('services.pdf_service.PDFService.extract_text_from_pdf', new_callable=AsyncMock) as mock_pdf_extract, \
         patch('services.pdf_service.PDFService.validate_job_description') as mock_pdf_validate:
        
        mock_s3_upload.return_value = "https://test-bucket.s3.amazonaws.com/test.pdf"
        mock_pdf_extract.return_value = {
            "text_content": "Mock resume text content",
            "metadata": {"page_count": 1, "estimated_tokens": 50}
        }
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
def mock_pdf_service():
    """Mock PDF service for testing."""
    service = Mock(spec=PDFService)
    service.extract_text_from_pdf = AsyncMock(return_value={
        "text_content": "Sample resume text content with experience and skills.",
        "metadata": {
            "page_count": 1,
            "text_length": 52,
            "estimated_tokens": 12
        }
    })
    service.validate_job_description = Mock()
    return service


@pytest.fixture
def mock_s3_service():
    """Mock S3 service for testing."""
    service = Mock(spec=S3Service)
    service.upload_pdf = AsyncMock(return_value="https://test-bucket.s3.amazonaws.com/test-resume.pdf")
    service.delete_pdf = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    service = Mock(spec=LLMService)
    
    async def mock_stream_response(*args, **kwargs):
        chunks = ["This ", "is ", "a ", "test ", "response."]
        for chunk in chunks:
            yield chunk
    
    service.generate_agent_response = mock_stream_response
    service.generate_complete_response = AsyncMock(return_value="Complete test response from agent.")
    
    return service


@pytest.fixture
def resume_repository(test_session):
    """Create resume repository with test session."""
    return ResumeRepository(test_session)


@pytest.fixture
def feedback_repository(test_session):
    """Create feedback repository with test session."""
    return FeedbackRepository(test_session)


@pytest.fixture
def sample_resume_data():
    """Sample resume data for testing."""
    return {
        "filename": "john_doe_resume.pdf",
        "text_content": "John Doe\nSoftware Engineer\n\nExperience:\n- 3 years Python development\n- FastAPI and React experience",
        "job_description": "Looking for a Senior Python Developer with FastAPI experience and 3+ years of backend development.",
        "s3_url": "https://test-bucket.s3.amazonaws.com/john_doe_resume.pdf"
    }