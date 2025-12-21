"""
Supabase Storage Utilities for PDF management using S3 API
"""
import io
import logging
import boto3
from botocore.client import Config
from typing import Optional, Tuple
from app.config import settings

logger = logging.getLogger(__name__)


class SupabaseStorage:
    """Supabase storage client using S3 API for PDF files"""

    def __init__(self):
        self.s3_client = None
        self.bucket_name = settings.s3_bucket_name

        if (settings.s3_access_key_id and settings.s3_secret_access_key and
            settings.s3_endpoint and settings.s3_region):

            try:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.s3_access_key_id,
                    aws_secret_access_key=settings.s3_secret_access_key,
                    endpoint_url=settings.s3_endpoint,
                    region_name=settings.s3_region,
                    config=Config(
                        signature_version='s3v4',
                        s3={'addressing_style': 'path'}
                    )
                )
                logger.info("S3 client initialized for Supabase storage")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}")
        else:
            logger.warning("S3 credentials not configured")

    def upload_pdf(self, file_content: bytes, filename: str) -> Optional[str]:
        """
        Upload PDF to Supabase storage via S3 API

        Args:
            file_content: PDF file content as bytes
            filename: Name of the file (e.g., 'invoice_123_acknowledged.pdf')

        Returns:
            Public URL of the uploaded file, or None if upload failed
        """
        if not self.s3_client:
            logger.error("S3 client not initialized")
            return None

        try:
            # Upload file to bucket
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=filename,
                Body=file_content,
                ContentType='application/pdf',
                ACL='public-read'  # Make the file publicly accessible
            )

            # Generate public URL
            public_url = f"{settings.s3_endpoint}/{self.bucket_name}/{filename}"
            logger.info(f"PDF uploaded successfully: {filename}")
            return public_url

        except Exception as e:
            logger.error(f"Error uploading PDF {filename}: {str(e)}")
            return None

    def download_pdf(self, filename: str) -> Optional[bytes]:
        """
        Download PDF from Supabase storage via S3 API

        Args:
            filename: Name of the file to download

        Returns:
            File content as bytes, or None if download failed
        """
        if not self.s3_client:
            logger.error("S3 client not initialized")
            return None

        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=filename
            )

            file_content = response['Body'].read()
            logger.info(f"PDF downloaded successfully: {filename}")
            return file_content

        except self.s3_client.exceptions.NoSuchKey:
            logger.error(f"PDF not found: {filename}")
            return None
        except Exception as e:
            logger.error(f"Error downloading PDF {filename}: {str(e)}")
            return None

    def delete_pdf(self, filename: str) -> bool:
        """
        Delete PDF from Supabase storage via S3 API

        Args:
            filename: Name of the file to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.s3_client:
            logger.error("S3 client not initialized")
            return False

        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=filename
            )
            logger.info(f"PDF deleted successfully: {filename}")
            return True

        except Exception as e:
            logger.error(f"Error deleting PDF {filename}: {str(e)}")
            return False

    def pdf_exists(self, filename: str) -> bool:
        """
        Check if PDF exists in Supabase storage via S3 API

        Args:
            filename: Name of the file to check

        Returns:
            True if file exists, False otherwise
        """
        if not self.s3_client:
            return False

        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=filename
            )
            return True

        except self.s3_client.exceptions.NoSuchKey:
            return False
        except Exception as e:
            logger.error(f"Error checking PDF existence {filename}: {str(e)}")
            return False


# Global instance
supabase_storage = SupabaseStorage()


def get_supabase_storage() -> SupabaseStorage:
    """Get the global Supabase storage instance"""
    return supabase_storage