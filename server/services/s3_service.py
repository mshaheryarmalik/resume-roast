"""S3 service for managing PDF file uploads and storage."""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from config import get_settings

logger = logging.getLogger(__name__)


class S3Service:
    """Service responsible for S3 operations.
    
    Handles PDF uploads to S3 or local storage (for development),
    with proper error handling and file management.
    """
    
    def __init__(self) -> None:
        """Initialize the S3 service."""
        self.settings = get_settings()
        self._client: Optional[boto3.client] = None
        # Local storage for development
        self.local_storage_dir = Path("/app/local_s3")
        if self.settings.environment == "development":
            self.local_storage_dir.mkdir(parents=True, exist_ok=True)
    
    def _use_local_storage(self) -> bool:
        """Check if we should use local storage instead of S3."""
        return self.settings.environment == "development"
    
    @property
    def client(self) -> boto3.client:
        """Get or create S3 client with lazy initialization."""
        if self._client is None:
            try:
                # For development with LocalStack
                if self.settings.aws_endpoint_url:
                    self._client = boto3.client(
                        's3',
                        aws_access_key_id=self.settings.aws_access_key_id,
                        aws_secret_access_key=self.settings.aws_secret_access_key,
                        region_name=self.settings.aws_region,
                        endpoint_url=self.settings.aws_endpoint_url
                    )
                else:
                    self._client = boto3.client(
                        's3',
                        aws_access_key_id=self.settings.aws_access_key_id,
                        aws_secret_access_key=self.settings.aws_secret_access_key,
                        region_name=self.settings.aws_region
                    )
            except NoCredentialsError:
                raise RuntimeError("AWS credentials not configured properly")
        return self._client
    
    async def upload_pdf(
        self, 
        pdf_content: bytes, 
        original_filename: str
    ) -> str:
        """
        Upload PDF to S3 and return the URL.
        
        Args:
            pdf_content: PDF file as bytes
            original_filename: Original filename from upload
            
        Returns:
            S3 URL of the uploaded file
            
        Raises:
            ValueError: If upload parameters are invalid
            RuntimeError: If upload fails
        """
        if not pdf_content:
            raise ValueError("PDF content cannot be empty")
        
        if not original_filename or not original_filename.strip():
            raise ValueError("Original filename cannot be empty")
            
        if len(pdf_content) > 50 * 1024 * 1024:  # 50MB limit
            raise ValueError("PDF file too large (limit: 50MB)")
            
        if not original_filename.lower().endswith('.pdf'):
            raise ValueError("Only PDF files are allowed")
        
        try:
            # Generate unique filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            safe_filename = self._sanitize_filename(original_filename)
            s3_key = f"resumes/{timestamp}_{unique_id}_{safe_filename}"
            
            if self._use_local_storage():
                # Use local file storage for development
                logger.info("Using local storage for development: %s", s3_key)
                
                # Create resumes subdirectory
                local_file_path = self.local_storage_dir / s3_key
                local_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write file to local storage
                with open(local_file_path, 'wb') as f:
                    f.write(pdf_content)
                
                logger.info("File saved locally at: %s", local_file_path)
                
                # Return a mock S3 URL for development
                s3_url = f"http://localhost:4566/{self.settings.s3_bucket_name}/{s3_key}"
            else:
                # Upload to real S3/LocalStack
                logger.info(
                    "Uploading to S3: bucket=%s, key=%s", 
                    self.settings.s3_bucket_name, 
                    s3_key
                )
                
                self.client.put_object(
                    Bucket=self.settings.s3_bucket_name,
                    Key=s3_key,
                    Body=pdf_content,
                    ContentType="application/pdf",
                    Metadata={
                        "original_filename": original_filename,
                        "upload_timestamp": timestamp,
                    }
                )
                
                # Generate S3 URL
                if self.settings.aws_endpoint_url:
                    # LocalStack URL
                    s3_url = f"{self.settings.aws_endpoint_url}/{self.settings.s3_bucket_name}/{s3_key}"
                else:
                    # Real AWS S3 URL
                    s3_url = f"https://{self.settings.s3_bucket_name}.s3.{self.settings.aws_region}.amazonaws.com/{s3_key}"
            return s3_url
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(
                "S3 ClientError during upload: %s - %s", 
                error_code, 
                str(e)
            )
            raise RuntimeError(f"S3 upload failed ({error_code}): {str(e)}")
        except OSError as e:
            logger.error("File system error during local upload: %s", str(e))
            raise RuntimeError(f"Local file upload failed: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error during upload: %s", str(e))
            raise RuntimeError(f"Unexpected error during upload: {str(e)}")
    
    async def delete_pdf(self, s3_url: str) -> bool:
        """
        Delete PDF from S3.
        
        Args:
            s3_url: S3 URL of the file to delete
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            # Extract S3 key from URL
            s3_key = self._extract_s3_key(s3_url)
            if not s3_key:
                return False
            
            self.client.delete_object(
                Bucket=self.settings.s3_bucket_name,
                Key=s3_key
            )
            return True
            
        except ClientError as e:
            # Log error but don't raise - deletion failures shouldn't break the app
            logger.warning("Failed to delete S3 object %s: %s", s3_url, str(e))
            return False
        except Exception as e:
            logger.warning("Unexpected error deleting S3 object %s: %s", s3_url, str(e))
            return False
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename for S3 storage.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename safe for S3
        """
        # Remove or replace unsafe characters
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_"
        sanitized = "".join(c if c in safe_chars else "_" for c in filename)
        
        # Ensure it doesn't start with a dot or dash
        if sanitized.startswith(('.', '-')):
            sanitized = 'file_' + sanitized
        
        # Limit length
        if len(sanitized) > 100:
            name_part, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
            sanitized = name_part[:95] + ('.' + ext if ext else '')
        
        return sanitized or "resume.pdf"
    
    def _extract_s3_key(self, s3_url: str) -> Optional[str]:
        """
        Extract S3 key from full S3 URL.
        
        Args:
            s3_url: Full S3 URL
            
        Returns:
            S3 key or None if URL is invalid
        """
        try:
            # Handle both s3:// and https:// URLs
            if s3_url.startswith(f"https://{self.settings.s3_bucket_name}.s3."):
                # Extract from https URL
                parts = s3_url.split(f"{self.settings.s3_bucket_name}.s3.{self.settings.aws_region}.amazonaws.com/")
                return parts[1] if len(parts) > 1 else None
            elif s3_url.startswith("s3://"):
                # Extract from s3:// URL
                return s3_url.replace(f"s3://{self.settings.s3_bucket_name}/", "")
            return None
        except Exception:
            return None