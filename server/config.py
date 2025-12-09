"""Configuration management for Resume Roast application."""

from functools import lru_cache
from typing import List

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    # Environment
    environment: str = Field(default="development", description="Application environment")
    debug: bool = Field(default=False, description="Debug mode")
    secret_key: str = Field(description="Secret key for sessions")
    
    # Database
    database_url: str = Field(description="PostgreSQL database URL")
    database_pool_size: int = Field(default=10, description="Database connection pool size")
    database_echo: bool = Field(default=False, description="Echo SQL queries")
    
    # Azure OpenAI
    azure_openai_api_key: str = Field(description="Azure OpenAI API key")
    azure_openai_endpoint: str = Field(description="Azure OpenAI endpoint URL")
    azure_openai_api_version: str = Field(default="2024-02-15-preview", description="Azure OpenAI API version")
    azure_openai_deployment: str = Field(default="gpt-4", description="Azure OpenAI deployment name")
    openai_max_tokens: int = Field(
        default=4000, 
        ge=1000, 
        le=128000, 
        description="Max tokens per response"
    )
    resume_token_limit: int = Field(
        default=15000, 
        ge=1000, 
        le=100000, 
        description="Max tokens for resume"
    )
    job_description_token_limit: int = Field(
        default=5000, 
        ge=100, 
        le=50000, 
        description="Max tokens for job description"
    )
    
    # AWS
    aws_access_key_id: str = Field(description="AWS access key ID")
    aws_secret_access_key: str = Field(description="AWS secret access key")
    aws_region: str = Field(default="us-east-1", description="AWS region")
    s3_bucket_name: str = Field(description="S3 bucket for PDF storage")
    kms_key_id: str = Field(description="KMS key for encryption")
    
    # CORS
    cors_origins: List[str] = Field(default=["http://localhost:8080"], description="Allowed CORS origins")
    
    # Agent Memory
    memory_refresh_interval_hours: int = Field(
        default=1, 
        ge=1, 
        le=168, 
        description="Hours between memory refresh (1-168)"
    )
    agent_memory_max_entries: int = Field(
        default=100, 
        ge=10, 
        le=1000, 
        description="Max entries in agent memory (10-1000)"
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()