import asyncio
import base64
import io
import tempfile
import time
import traceback
import uuid
from typing import Optional

import magic
from fastapi import UploadFile, HTTPException

from shared import shared_settings
from shared.data_processing.cloudflare import Cloudflare
from shared.enums import MongoDBChatMessageType, CloudFlareR2Buckets, CloudFlareFileSource
from shared.errors.core import CoreErrors
from shared.users_sync.schema import UserRead


class FilesUtils:
    def __init__(
            self,
            file_type: MongoDBChatMessageType,
            file: Optional[UploadFile],
            user: UserRead,
            file_source: CloudFlareFileSource,
            bucket: CloudFlareR2Buckets = CloudFlareR2Buckets.PRIVATE,
    ):
        self.file = file
        self.user = user
        self.file_type = file_type
        self.bucket_type = bucket
        self.bucket_name = self.get_bucket_name(bucket)
        self.cloud_flare_r2_client = self.get_cloudflare_r2_client()
        self.file_content = None
        self.mimetype = None
        self.prepared_file = False

        if self.file:
            file_extension = self.file.filename.split('.')[-1] if '.' in self.file.filename else 'bin'
            unique_id = str(uuid.uuid4())
            file_type_for_name = file_type if not isinstance(file_type, type) else file_type.value
            self.cf_r2_object_name = (
                f"{self.user.user_id}/private/{file_source}/{file_type_for_name}/{unique_id}.{file_extension}"
            )
        else:
            self.cf_r2_object_name = None

    def get_cloudflare_r2_client(self):
        cloud_flare = Cloudflare(bucket=self.bucket_type)
        return cloud_flare.get_r2_client()

    @staticmethod
    def get_bucket_name(bucket: CloudFlareR2Buckets):
        if bucket == CloudFlareR2Buckets.PRIVATE:
            return shared_settings.CR_R2_PRIVATE_BUCKET_NAME
        elif bucket == CloudFlareR2Buckets.PUBLIC:
            return shared_settings.CR_R2_PUBLIC_BUCKET_NAME
        else:
            raise ValueError('Invalid bucket name')

    @staticmethod
    def validate_object_name_format(object_name):
        parts = object_name.split('/')
        if len(parts) < 4:
            raise HTTPException(status_code=400, detail=CoreErrors.INVALID_OBJECT_NAME_FORMATE)
        return parts

    @staticmethod
    def validate_object_ownership(object_name, user_id):
        file_owner_user_id = FilesUtils.validate_object_name_format(object_name)[1]
        if str(user_id) != str(file_owner_user_id):
            raise HTTPException(status_code=403, detail=CoreErrors.UNAUTHORIZED_MEDIA_ACCESS)

    async def prepare_file(self):
        await self.check_file_type()
        self.prepared_file = True

    async def check_file_type(self):
        contents = await self.file.read()
        self.file_content = contents
        mime = magic.Magic(mime=True)
        self.mimetype = mime.from_buffer(contents)

        if self.file_type == MongoDBChatMessageType.audio and self.file.content_type != "audio/mpeg" and self.mimetype != "audio/mpeg":
            raise HTTPException(status_code=422, detail=CoreErrors.UNSUPPORTED_MEDIA_TYPE)

        supported_image_types = ["image/png", "image/jpeg", "image/webp"]
        if (self.file_type == MongoDBChatMessageType.image
                and self.file.content_type not in supported_image_types
                and self.mimetype not in supported_image_types):
            raise HTTPException(status_code=422, detail=CoreErrors.UNSUPPORTED_MEDIA_TYPE)

        supported_document_types = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "text/markdown"
        ]
        if (self.file_type == MongoDBChatMessageType.document
                and self.file.content_type not in supported_document_types
                and self.mimetype not in supported_document_types):
            raise HTTPException(status_code=422, detail=CoreErrors.UNEXPECTED_ERROR)

    async def store_raw_file(self):
        """Uploads file to R2 with proper verification"""
        if not self.prepared_file:
            await self.prepare_file()

        try:
            # Ensure we're at the start of the file
            if hasattr(self.file.file, 'seek'):
                self.file.file.seek(0)

            # Upload the file
            self.cloud_flare_r2_client.upload_fileobj(
                Fileobj=self.file.file,
                Bucket=self.bucket_name,
                Key=self.cf_r2_object_name.lstrip('/')  # Remove leading slash
            )

            # Add more robust verification
            await self._verify_upload_completion()

        except Exception as e:
            print(f"Failed to upload file: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"{CoreErrors.ERROR_UPLOADING_FILE}: {str(e)}"
            )

    async def _verify_upload_completion(self, max_attempts=5, delay=1.0):
        """Verifies the file exists and is accessible"""
        for attempt in range(max_attempts):
            try:
                response = self.cloud_flare_r2_client.head_object(
                    Bucket=self.bucket_name,
                    Key=self.cf_r2_object_name.lstrip('/')
                )
                if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
                    return True
            except Exception as e:
                if attempt == max_attempts - 1:  # Last attempt
                    print(f"Final upload verification failed: {str(e)}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Upload verification failed after {max_attempts} attempts"
                    )
                await asyncio.sleep(delay)
        return False

    def retrieve_file(self, object_name: str = None, max_retries=5, initial_delay=1.0):
        """Retrieves file with exponential backoff"""
        object_name = object_name or self.cf_r2_object_name
        object_name = object_name.lstrip('/')  # Ensure no leading slash

        delay = initial_delay
        last_exception = None

        for attempt in range(max_retries):
            try:
                response = self.cloud_flare_r2_client.get_object(
                    Bucket=self.bucket_name,
                    Key=object_name
                )
                return response['Body'].read()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    sleep_time = min(delay * (2 ** attempt), 10)  # Exponential backoff with max 10s
                    time.sleep(sleep_time)
                    continue

        print(f"Failed to retrieve file after {max_retries} attempts: {last_exception}")
        raise HTTPException(
            status_code=500,
            detail=f"File not available after {max_retries} retries. Please try again later."
        )

    def prepare_file_for_download(self, object_name: str, bucket: CloudFlareR2Buckets = CloudFlareR2Buckets.PRIVATE):
        try:
            client = self.get_cloudflare_r2_client()
            response = client.get_object(Bucket=self.bucket_name, Key=object_name)
            file_content = response['Body'].read()

            # Determine the MIME type and extension
            mime = magic.Magic(mime=True)
            mime_type = mime.from_buffer(file_content)
            ext = mime_type.split('/')[-1]

            # Handling common cases for MIME types to file extensions
            common_extensions = {
                'audio/mpeg': 'mp3',
                'text/plain': 'txt',
                'application/pdf': 'pdf',
                'application/msword': 'doc',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
                'image/png': 'png',
                'image/webp': 'webp',
                'image/jpeg': 'jpg',
                # Add more mappings as needed
            }

            ext = common_extensions.get(mime_type, ext)  # Use the mapped extension or fallback to guessed extension

            # Create a temporary file with the correct extension
            with tempfile.NamedTemporaryFile(suffix='.' + ext, delete=False) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name

            return temp_file_path

        except Exception as e:
            # log_error(exception=e, service_name="FilesUtils.retrieve_file")
            if shared_settings.ENVIRONMENT != 'production':
                traceback.print_exc()
                print(f"Error preparing file for download: {e}")
            raise HTTPException(status_code=500, detail=CoreErrors.ERROR_PROCESSING_FILE)

    async def get_image_data_64(self):
        if not self.prepared_file:
            await self.prepare_file()
        if self.file_type != MongoDBChatMessageType.image:
            raise HTTPException(status_code=400, detail=CoreErrors.INVALID_MEDIA_TYPE)
        if not self.file:
            raise HTTPException(status_code=400, detail=CoreErrors.NO_MEDIA_FILE_PROVIDED)
        try:
            file_content = self.file_content or await self.file.read()
            self.file_content = file_content  # In case it wasn't set before
            if not file_content:
                raise HTTPException(status_code=400, detail=CoreErrors.NO_MEDIA_FILE_PROVIDED)
            image_data_64 = base64.b64encode(file_content).decode('utf-8')
            return image_data_64
        except Exception as e:
            # log_error(exception=e, service_name="FilesUtils.get_image_data_64")
            if shared_settings.ENVIRONMENT != 'production':
                traceback.print_exc()
                print(f"Error preparing file for download: {e}")
            raise HTTPException(status_code=500, detail=CoreErrors.ERROR_PROCESSING_FILE)

        # ✨ NEW ✨  store image under /<user_id>/chat_images/<thread_id>/<uuid>.<ext>

    async def store_chat_image_and_get_object_name(
            self, *, thread_id: uuid.UUID
    ) -> str:
        if not self.prepared_file:
            await self.prepare_file()

        ext = self.file.filename.split('.')[-1] if '.' in self.file.filename else 'bin'
        if shared_settings.ENVIRONMENT == 'local':
            object_name = f"local/{self.user.user_id}/chat_images/{thread_id}/{uuid.uuid4()}.{ext}"
        else:
            object_name = f"{self.user.user_id}/chat_images/{thread_id}/{uuid.uuid4()}.{ext}"

        try:
            # Upload from memory instead of the closed file
            file_stream = io.BytesIO(self.file_content)
            self.cloud_flare_r2_client.upload_fileobj(
                Fileobj=file_stream,
                Bucket=self.bucket_name,
                Key=object_name
            )
            return object_name
        except Exception as e:
            if shared_settings.ENVIRONMENT != 'production':
                traceback.print_exc()
                print(f"Error preparing file for upload: {e}")
            raise HTTPException(status_code=500, detail=CoreErrors.ERROR_UPLOADING_FILE) from e

    @staticmethod
    def generate_presigned_url(object_name: str, expires_in: int = 900) -> str:
        """
        Returns a time-limited URL pointing to Cloudflare R2 object.
        """
        cf = Cloudflare()
        url = cf.generate_pre_signed_url(object_name, expiration=expires_in)
        if not url:
            raise HTTPException(status_code=500, detail=CoreErrors.ERROR_PROCESSING_FILE)
        return url

    async def delete_file(self, object_name: Optional[str] = None):
        """
        Deletes a file from Cloudflare R2 storage.
        """
        if object_name is None:
            object_name = self.cf_r2_object_name
        self.cloud_flare_r2_client.delete_object(Bucket=self.bucket_name, Key=object_name)

    async def store_public_image_and_get_object_name(self, object_name: Optional[str] = None) -> str:
        if not self.prepared_file:
            await self.prepare_file()

        # Extract the file extension from the filename
        ext = self.file.filename.split('.')[-1] if '.' in self.file.filename else 'bin'

        # Set object name
        if not object_name:
            object_name = f"{self.file.filename}"
        else:
            object_name = f"{object_name}.{ext}"

        file_stream = io.BytesIO(self.file_content)
        self.cloud_flare_r2_client.upload_fileobj(file_stream, self.bucket_name, object_name)
        return object_name
