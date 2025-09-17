import logging
import tempfile

import magic
from fastapi import HTTPException

from shared.config import shared_settings
from shared.data_processing.cloudflare import Cloudflare
from shared.schemas.document import DocumentRead
from shared.utils.logger import TsLogger

logger = TsLogger(__name__)


class DocumentRetriever:
    def __init__(self, document: DocumentRead):
        cloud_flare = Cloudflare()

        self.document = document
        self.cloud_flare_r2_client = cloud_flare.get_r2_client()

    def retrieve_file_content(self):
        try:
            response = self.cloud_flare_r2_client.get_object(
                Bucket=shared_settings.CR_R2_PRIVATE_BUCKET_NAME,
                Key=self.document.object_name
            )
            file_content = response['Body'].read()
            return file_content
        except Exception as e:
            logger.error(f"Failed to retrieve file content for document with object_name {self.document.object_name}: {str(e)}")
            raise HTTPException(status_code=500, detail="processing error")

    def prepare_file_for_download(self, document: DocumentRead):
        try:
            response = self.cloud_flare_r2_client.get_object(
                Bucket=shared_settings.CR_R2_PRIVATE_BUCKET_NAME,
                Key=document.object_name
            )
            file_content = response['Body'].read()

            # Determine the MIME type and extension
            mime = magic.Magic(mime=True)
            mime_type = mime.from_buffer(file_content)
            ext = mime_type.split('/')[-1]

            # Handling common cases for MIME types to file extensions
            common_extensions = {
                'text/plain': 'txt',
                'application/pdf': 'pdf',
                'application/msword': 'doc',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
                # Add more mappings as needed
            }

            ext = common_extensions.get(mime_type, ext)  # Use the mapped extension or fallback to guessed extension

            # Create a temporary file with the correct extension
            with tempfile.NamedTemporaryFile(suffix='.' + ext, delete=False) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name

            return temp_file_path

        except Exception as e:
            logger.error(f"Failed to prepare file for download for document with object_name {self.document.object_name}: {str(e)}")
            raise HTTPException(status_code=500, detail="error processing")

    async def delete_object(self):
        """
        Deletes the specified object from the Cloudflare R2 bucket.
        """
        try:
            self.cloud_flare_r2_client.delete_object(
                Bucket=shared_settings.CR_R2_PRIVATE_BUCKET_NAME,
                Key=self.document.object_name
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete object with object_name {self.document.object_name}: {str(e)}")
            raise HTTPException(status_code=500, detail="Error deleting the document")
