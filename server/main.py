"""Main FastAPI application for Resume Roast."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import router
from config import get_settings
from database import get_db_session
from repositories import FeedbackRepository

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()

# Global agent memory for all analyses
AGENT_MEMORY: list[str] = []


async def refresh_agent_memory() -> None:
    """Background task to refresh agent memory with aggregated learnings."""
    global AGENT_MEMORY
    try:
        async with get_db_session() as session:
            feedback_repo = FeedbackRepository(session)
            
            # Get recent learnings
            learnings = await feedback_repo.get_aggregated_learnings(limit=50)
            
            # Extract descriptions and store in global memory
            AGENT_MEMORY = [learning.description for learning in learnings]
            
            logger.info(
                "Memory refresh completed: Found %d learning patterns", 
                len(AGENT_MEMORY)
            )
            
            # Log top patterns for visibility
            for i, pattern in enumerate(AGENT_MEMORY[:5], 1):
                logger.debug("  Pattern %d: %s", i, pattern)
            
    except Exception as e:
        logger.error("Error during memory refresh: %s", str(e))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan management."""
    # Startup
    logger.info("Starting Resume Roast application...")
    logger.info("Note: Database tables should be created using 'alembic upgrade head'")
    
    # Start background scheduler
    scheduler.add_job(
        refresh_agent_memory,
        trigger=IntervalTrigger(hours=settings.memory_refresh_interval_hours),
        id="memory_refresh",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Background memory refresh scheduled")
    
    # Run initial memory refresh
    await refresh_agent_memory()
    
    yield
    
    # Shutdown
    # Application shutdown
    scheduler.shutdown()


# Create FastAPI app
app = FastAPI(
    title="Resume Roast",
    description="AI-powered resume critique platform with multi-agent debate system",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1", tags=["resume-roast"])


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "Welcome to Resume Roast API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug"
    )