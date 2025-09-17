# document_creator.py

import io
import logging
import uuid

import magic
from fastapi import UploadFile, HTTPException

from shared.config import shared_settings
from shared.data_processing.cloudflare import Cloudflare
from shared.users_sync.schema import UserRead
from shared.utils.logger import TsLogger

logger = TsLogger(__name__)

class DocumentCreator:
    def __init__(self, file: UploadFile, user: UserRead, user_profile_assets = False):
        cloud_flare = Cloudflare()
        self.user = user

        self._cloud_flare_r2_client = cloud_flare.get_r2_client()
        self.file: UploadFile = file

        # Determine the file extension
        self.file_extension = self.file.filename.split('.')[-1].lower() if '.' in self.file.filename else 'bin'
        # Generate a unique id for the file
        self.unique_id = str(uuid.uuid4())
        # Get the file name without the extension
        self.file_name = self.file.filename.rsplit('.', 1)[0] if '.' in self.file.filename else self.file.filename
        # Construct the object name using the unique id
        self.cf_r2_object_name = ''
        if shared_settings.ENVIRONMENT == 'development':
            self.cf_r2_object_name = "dev/"
        elif shared_settings.ENVIRONMENT == 'local':
            self.cf_r2_object_name = "local/"
        self.cf_r2_object_name += f"ts-users-pdf/{self.user.user_id}/{self.unique_id}/{self.file_name}.{self.file_extension}"

        self.file_content: bytes = b''  # To store the file content in memory

        self.file_size = 0  # Initialize file size to 0, will set after reading

    async def read_file_content(self):
        try:
            self.file_content = await self.file.read()
            self.file_size = len(self.file_content)  # Calculate file size after content is read
        except Exception as e:
            logger.error("DocumentCreator.read_file_content " + str(e))
            raise HTTPException(status_code=500, detail="Error reading file content")

    async def check_file_type(self):
        await self.read_file_content()
        # Create a magic object
        mime = magic.Magic(mime=True)
        file_type = mime.from_buffer(self.file_content)

        # Supported document types
        supported_document_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
            "text/plain"
        ]
        if (self.file.content_type not in supported_document_types
                and file_type not in supported_document_types):
            raise HTTPException(
                status_code=422,
                detail="Document file is not supported, please upload a supported file type (pdf, docx, txt)"
            )

    def store_raw_file(self):
        try:
            # Create a BytesIO buffer from the content
            buffer = io.BytesIO(self.file_content)
            self._cloud_flare_r2_client.upload_fileobj(
                buffer,
                shared_settings.CR_R2_PRIVATE_BUCKET_NAME,
                self.cf_r2_object_name
            )
        except Exception as e:
            logger.error("DocumentCreator.store_raw_file: " + str(e))
            raise HTTPException(status_code=500, detail="Error uploading file to storage")
