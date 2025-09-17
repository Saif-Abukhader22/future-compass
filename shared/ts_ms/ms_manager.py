import logging
import os
from datetime import datetime
from typing import Optional, List
from uuid import UUID

import httpx
from fastapi import HTTPException
from httpx import Response
from pydantic import BaseModel

from shared.config import shared_settings
from shared.enums import MicroServiceName
from shared.utils.logger import TsLogger

logger = TsLogger(__name__)


class MicroServiceInfo(BaseModel):
    name: MicroServiceName
    url_prefix: str
    local_development_url: Optional[str] = ''
    timeout: Optional[int] = 30
    retries: Optional[int] = 3
    active: Optional[bool] = False
    create_async_user: Optional[bool] = False


class MsManager:
    _instance = None
    _services = {
        MicroServiceName.CORE_SERVICE.snake(): MicroServiceInfo(
            name=MicroServiceName.CORE_SERVICE,
            url_prefix="/core",
            local_development_url=shared_settings.CORE_SERVICE_DEVELOPMENT_URL,
            active=shared_settings.CORE_SERVICE_ACTIVE,
            create_async_user= shared_settings.CORE_SERVICE_ACTIVE
        ),
        MicroServiceName.IDENTITY_SERVICE.snake(): MicroServiceInfo(
            name=MicroServiceName.IDENTITY_SERVICE,
            url_prefix="/auth",
            local_development_url=shared_settings.IDENTITY_SERVICE_DEVELOPMENT_URL,
            active=shared_settings.IDENTITY_SERVICE_ACTIVE,
            create_async_user=shared_settings.IDENTITY_SERVICE_CREATE_ASYNC_USER
        ),
        MicroServiceName.SUBSCRIPTION_SERVICE.snake(): MicroServiceInfo(
            name=MicroServiceName.SUBSCRIPTION_SERVICE,
            url_prefix="/subscription",
            local_development_url=shared_settings.SUBSCRIPTION_SERVICE_DEVELOPMENT_URL,
            active=shared_settings.SUBSCRIPTION_SERVICE_ACTIVE,
            create_async_user=shared_settings.SUBSCRIPTION_SERVICE_CREATE_ASYNC_USER
        ),
        MicroServiceName.COMMUNITY_SERVICE.snake(): MicroServiceInfo(
            name=MicroServiceName.COMMUNITY_SERVICE,
            url_prefix="/community",
            local_development_url=shared_settings.COMMUNITY_SERVICE_DEVELOPMENT_URL,
            active=shared_settings.COMMUNITY_SERVICE_ACTIVE,
            create_async_user=shared_settings.COMMUNITY_SERVICE_CREATE_ASYNC_USER
        ),
        MicroServiceName.DOC_CHATTING_SERVICE.snake(): MicroServiceInfo(
            name=MicroServiceName.DOC_CHATTING_SERVICE,
            url_prefix="/doc-chatting",
            local_development_url=shared_settings.DOC_CHATTING_SERVICE_DEVELOPMENT_URL,
            active=shared_settings.DOC_CHATTING_SERVICE_ACTIVE,
            create_async_user=shared_settings.DOC_CHATTING_SERVICE_CREATE_ASYNC_USER
        ),
        MicroServiceName.BIBLE_SERVICE.snake(): MicroServiceInfo(
            name=MicroServiceName.BIBLE_SERVICE,
            url_prefix="/bible",
            local_development_url=shared_settings.BIBLE_SERVICE_DEVELOPMENT_URL,
            active=shared_settings.BIBLE_SERVICE_ACTIVE,
            create_async_user= shared_settings.BIBLE_SERVICE_CREATE_ASYNC_USER
        ),
        MicroServiceName.ASSESSMENTS_SERVICE.snake(): MicroServiceInfo(
            name=MicroServiceName.ASSESSMENTS_SERVICE,
            url_prefix="/assessments",
            local_development_url=shared_settings.ASSESSMENTS_SERVICE_DEVELOPMENT_URL,
            active=shared_settings.ASSESSMENTS_SERVICE_ACTIVE,
            create_async_user=shared_settings.ASSESSMENTS_SERVICE_CREATE_ASYNC_USER

        ),
        MicroServiceName.NOTIFICATIONS_SERVICE.snake(): MicroServiceInfo(
            name=MicroServiceName.NOTIFICATIONS_SERVICE,
            url_prefix="/notifications",
            local_development_url=shared_settings.NOTIFICATIONS_SERVICE_DEVELOPMENT_URL,
            active=shared_settings.NOTIFICATIONS_SERVICE_ACTIVE,
            create_async_user=shared_settings.NOTIFICATIONS_SERVICE_CREATE_ASYNC_USER
        ),
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MsManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        # Use getattr to safely check if '_initialized' exists
        if getattr(self, '_initialized', False):
            return

        import shared.users_sync  # !!!! keep this line to initialize this module
        self._initialized = True

    @staticmethod
    def serialize_json(data):
        """
        Recursively convert UUIDs and datetime objects to serializable forms.
        """
        if isinstance(data, dict):
            return {k: MsManager.serialize_json(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [MsManager.serialize_json(i) for i in data]
        elif isinstance(data, UUID):
            return str(data)
        elif isinstance(data, datetime):
            return data.isoformat()
        return data

    @classmethod
    def get_service(cls, service_name: str) -> Optional[MicroServiceInfo]:
        return cls._services.get(service_name, None)

    @classmethod
    def get_services(cls) -> dict[str, MicroServiceInfo]:
        return cls._services

    @classmethod
    def get_service_url_prefix(cls, service_name: str) -> str:
        service_info = cls.get_service(service_name)
        return service_info.url_prefix if service_info else ''

    @classmethod
    def get_service_name(cls, service_prefix: str) -> str:
        for service_name, service_info in cls._services.items():
            if service_info.url_prefix == service_prefix:
                return service_name
        return ""

    @classmethod
    def get_internal_service_domainname(cls, service_name: str) -> str:
        service_info = cls.get_service(service_name)
        # return f"{service_info.name.value}.default.svc.cluster.local" if service_info else ""
        return f"{service_info.name.value}.{shared_settings.K8S_NAMESPACE}.svc.cluster.local" if service_info else ""

    @classmethod
    async def make_request(
            cls,
            method: str,
            service_name: str,
            endpoint: str,
            base_error_message: str = "Error",
            params: Optional[dict] = None,
            json: Optional[dict] = None,
            headers: Optional[dict] = None
    ) -> httpx.Response:
        """
        Makes an HTTP request to a specific microservice with the given method and data.
        """
        service_info = cls.get_service(service_name)
        if not service_info:
            raise ValueError(f"Invalid service name: {service_name}")

        if not service_info.active:
            logger.warning(f"Service {service_name} is not active, skipping request")
            raise HTTPException(status_code=404, detail=f"{base_error_message}: service not active")

        # Construct the URL with the provided base URL and endpoint
        # Replace placeholders with actual values (e.g., service domain name)
        # Note: Make sure to handle placeholders and escape special characters as needed
        # Example: http://<internal_service_domain_name>/<endpoint>
        domain_name = cls.get_internal_service_domainname(service_name)

        if headers is None:
            headers = {
                shared_settings.SERVICES_API_KEY_NAME: shared_settings.SERVICES_API_KEY
            }
        if service_info.local_development_url:
            url = f"{service_info.local_development_url}{endpoint}"
        else:
            url = f"http://{domain_name}{endpoint}"

        if json is not None:
            json = cls.serialize_json(json)  # Apply UUID serialization

        # Set a custom timeout (for example, 30 seconds)
        timeout = httpx.Timeout(30.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json,
                )
            except httpx.ReadTimeout as exc:
                logger.error(f"Timeout error for {url}: {exc}")
                # Raise an HTTPException with a 504 Gateway Timeout status code
                raise HTTPException(
                    status_code=504,
                    detail=f"{base_error_message}: request timed out"
                ) from exc

            # Consider any 2xx status code as successful
            if not (200 <= response.status_code < 300):
                try:
                    # Attempt to parse JSON, or fallback to text if there's no content
                    response_text = response.json() if response.content else response.text
                except Exception:
                    response_text = response.text

                if isinstance(response_text, dict) and "detail" in response_text:
                    response_text = response_text.get("detail")
                logger.error(f"Error from {url}: {response_text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"{base_error_message}: {response_text}"
                )

        return response

    @classmethod
    async def get(cls, endpoint: str, base_error_message: str, service_name: Optional[str] = None,
                  params: Optional[dict] = None) -> Response:
        return await cls.make_request("GET", service_name, endpoint, base_error_message=base_error_message,
                                      params=params)

    @classmethod
    async def post(cls, endpoint: str, base_error_message: str, service_name: Optional[str] = None,
                   json: Optional[dict] = None, params: Optional[dict] = None,
                   headers: Optional[dict] = None) -> Response:
        return await cls.make_request("POST", service_name, endpoint, base_error_message=base_error_message, json=json,
                                      params=params, headers=headers)

    @classmethod
    async def put(cls, endpoint: str, base_error_message: str, service_name: Optional[str] = None,
                  json: Optional[dict] = None, params: Optional[dict] = None,
                  headers: Optional[dict] = None) -> Response:
        return await cls.make_request("PUT", service_name, endpoint, base_error_message=base_error_message, json=json,
                                      params=params, headers=headers)

    @classmethod
    async def delete(cls, endpoint: str, base_error_message: str, service_name: Optional[str] = None,
                     params: Optional[dict] = None) -> Response:
        return await cls.make_request("DELETE", service_name, endpoint, base_error_message=base_error_message,
                                      params=params)

    @classmethod
    def get_login_url(cls) -> Optional[str]:
        auth_service = cls.get_service(MicroServiceName.IDENTITY_SERVICE.snake())
        if not auth_service:
            return None
        if auth_service.local_development_url and shared_settings.ENVIRONMENT == 'local':
            return f"{auth_service.local_development_url}/login"
        else:
            host_name = os.getenv('MAIN_HOST_NAME')
            protocol = 'http' if shared_settings.ENVIRONMENT == 'local' else 'https'
            if host_name:
                return f"{protocol}://{host_name}{shared_settings.API_V1_STR}{auth_service.url_prefix}/login"
            else:
                return None
