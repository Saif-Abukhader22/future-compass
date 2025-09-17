import logging

import boto3
from botocore.client import Config

from shared import shared_settings
from shared.enums import CloudFlareR2Buckets
from shared.utils.logger import TsLogger

logger = TsLogger(__name__)


class Cloudflare:

    def __init__(self, bucket: CloudFlareR2Buckets = CloudFlareR2Buckets.PRIVATE):
        self.r2_client_session = None
        if bucket == CloudFlareR2Buckets.PUBLIC:
            self.bucket = shared_settings.CR_R2_PUBLIC_BUCKET_NAME
            self.aws_access_key_id = shared_settings.CF_R2_PUBLIC_ASSETS_S3_ACCESS_KEY
            self.aws_secret_access_key = shared_settings.CF_R2_PUBLIC_ASSETS_S3_SECRET_KEY
            self.endpoint_url = shared_settings.CF_R2_PUBLIC_ASSETS_S3_JUR_ENDPOINT
        elif bucket == CloudFlareR2Buckets.PRIVATE:
            self.bucket = shared_settings.CR_R2_PRIVATE_BUCKET_NAME
            self.aws_access_key_id = shared_settings.CF_R2_PRIVATE_ASSETS_S3_ACCESS_KEY
            self.aws_secret_access_key = shared_settings.CF_R2_PRIVATE_ASSETS_S3_SECRET_KEY
            self.endpoint_url = shared_settings.CF_R2_PRIVATE_ASSETS_S3_JUR_ENDPOINT
        else:
            raise ValueError('Invalid bucket name')

    def get_r2_client(self):
        session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key
        )
        return session.client(
            's3',
            endpoint_url=self.endpoint_url,
            config=Config(signature_version='s3v4')
        )

    def generate_pre_signed_url(self, object_name, expiration=3600):
        r2_client = self.get_r2_client()
        try:
            response = r2_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': shared_settings.CR_R2_PRIVATE_BUCKET_NAME, 'Key': object_name},
                ExpiresIn=expiration
            )
            return response
        except Exception as e:
            logger.error(f"Error generating pre-signed URL: {str(e)}")
            return None

    def empty_bucket(self):
        """
        Deletes all objects in the specified bucket.
        """
        r2_client = self.get_r2_client()
        try:
            paginator = r2_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=shared_settings.CR_R2_PRIVATE_BUCKET_NAME)

            objects_to_delete = []
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects_to_delete.append({'Key': obj['Key']})

                # Delete in batches of 1000 (S3 API limit)
                if len(objects_to_delete) >= 1000:
                    r2_client.delete_objects(
                        Bucket=shared_settings.CR_R2_PRIVATE_BUCKET_NAME,
                        Delete={'Objects': objects_to_delete}
                    )
                    objects_to_delete = []

            # Delete any remaining objects
            if objects_to_delete:
                r2_client.delete_objects(
                    Bucket=shared_settings.CR_R2_PRIVATE_BUCKET_NAME,
                    Delete={'Objects': objects_to_delete}
                )

            return True
        except Exception as e:
            logger.error(f"Error emptying bucket: {str(e)}")
            return False
