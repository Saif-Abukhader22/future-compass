import os

import pathlib
from typing import List, Union

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def load_env_variables(service_name: str) -> str | None:
    # check if KUBERNETES_PORT env var exists
    service_dir = str(
        pathlib.Path(__file__).resolve().parent.parent
    ) + f"/{service_name if service_name == 'shared' else service_name + '_service'}"
    if 'KUBERNETES_PORT' not in os.environ:
        load_dotenv(os.path.join(service_dir, '.env'))
    if service_name != 'shared':
        version_file = os.path.join(service_dir, 'version')
        if not os.path.isfile(version_file):
            raise FileNotFoundError(f'No version file found at {version_file}')
        with open(version_file, 'r') as file:
            version = file.read().strip()

        if not version:
            raise ValueError('No version provided in version')


        print(f'Version: {version}')
        return version


load_env_variables('shared')


class SharedSettings(BaseSettings):
    model_config = SettingsConfigDict(
        extra='ignore'
    )

    ENVIRONMENT: str = 'development'  # Default value
    K8S_NAMESPACE: str

    BACKEND_CORS_ORIGINS: Union[str, List[str], None] = None  # initially raw

    ENCRYPTION_KEY: str
    # SECRET_TOKEN_ENCRYPTION_KEY: str

    SYSTEM_ID: str
    API_V1_STR: str = '/api/v1'
    API_KEY_NAME: str = 'X-API-KEY'  # for external use
    API_KEY: str  # for external use
    SERVICES_API_KEY_NAME: str = 'X-API-KEY'  # for internal use between microservices to increase security
    SERVICES_API_KEY: str  # for internal use between microservices to increase security if the external API key was exposed

    JWT_ALGORITHM: str
    JWT_AT_SECRET: str

    # Email Service
    ZOHO_SMTP_SERVER: str
    ZOHO_SMTP_PORT: str
    ZOHO_EMAIL: str
    ZOHO_PASSWORD: str

    THEOSUMMA_CDN_HOST: str = ''

    CR_R2_PUBLIC_BUCKET_NAME: str = ''
    CF_R2_PUBLIC_ASSETS_S3_SECRET_KEY: str = ''
    CF_R2_PUBLIC_ASSETS_S3_JUR_ENDPOINT: str = ''
    CF_R2_PUBLIC_ASSETS_API_ACCESS_TOKEN: str = ''
    CF_R2_PUBLIC_ASSETS_S3_ACCESS_KEY: str = ''
    CF_R2_PUBLIC_ASSETS_DIR: str = ""

    CR_R2_PRIVATE_BUCKET_NAME: str = ''
    CF_R2_PRIVATE_ASSETS_S3_SECRET_KEY: str = ''
    CF_R2_PRIVATE_ASSETS_S3_JUR_ENDPOINT: str = ''
    CF_R2_PRIVATE_ASSETS_API_ACCESS_TOKEN: str = ''
    CF_R2_PRIVATE_ASSETS_S3_ACCESS_KEY: str = ''
    OPENAI_API_KEY: str
    OPENAI_PROJECT_ID: str
    OPENAI_ORG_ID: str

    THEOSUMMA_ES_INDEX: str
    ES_HOST: str = ''
    ES_USER: str = ''
    ES_PASSWORD: str = ''
    ES_PORT: int = 9200

    TS_REDIS_HOST: str = ''
    TS_REDIS_PORT: str = ''

    ALLOW_MONITORING: bool = False

    CORE_SERVICE_ACTIVE: bool
    CORE_SERVICE_CREATE_ASYNC_USER: bool
    IDENTITY_SERVICE_ACTIVE: bool
    IDENTITY_SERVICE_CREATE_ASYNC_USER: bool
    SUBSCRIPTION_SERVICE_ACTIVE: bool
    SUBSCRIPTION_SERVICE_CREATE_ASYNC_USER: bool
    COMMUNITY_SERVICE_ACTIVE: bool
    COMMUNITY_SERVICE_CREATE_ASYNC_USER: bool
    DOC_CHATTING_SERVICE_ACTIVE: bool
    DOC_CHATTING_SERVICE_CREATE_ASYNC_USER: bool
    BIBLE_SERVICE_ACTIVE: bool
    BIBLE_SERVICE_CREATE_ASYNC_USER: bool
    ASSESSMENTS_SERVICE_ACTIVE: bool
    ASSESSMENTS_SERVICE_CREATE_ASYNC_USER: bool
    NOTIFICATIONS_SERVICE_ACTIVE: bool
    NOTIFICATIONS_SERVICE_CREATE_ASYNC_USER: bool



    CORE_SERVICE_DEVELOPMENT_URL: str = ''
    IDENTITY_SERVICE_DEVELOPMENT_URL: str = ''
    SUBSCRIPTION_SERVICE_DEVELOPMENT_URL: str = ''
    COMMUNITY_SERVICE_DEVELOPMENT_URL: str = ''
    DOC_CHATTING_SERVICE_DEVELOPMENT_URL: str = ''
    BIBLE_SERVICE_DEVELOPMENT_URL: str = ''
    ASSESSMENTS_SERVICE_DEVELOPMENT_URL: str = ''
    NOTIFICATIONS_SERVICE_DEVELOPMENT_URL: str = ''
    LOGO_URL: str

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str], None]) -> List[str]:
        cors_origins = []
        if v:
            if isinstance(v, str):
                cors_origins.extend([i.strip() for i in v.split(",") if i.strip()])

        cors_origins.append('http://theosumma.com')
        cors_origins.append('https://theosumma.com')
        ts_live_cors = os.environ.get("TS_LIVE_CORS_ORIGINS", None)
        if ts_live_cors and isinstance(ts_live_cors, str):
            ts_live_cors = [i.strip() for i in ts_live_cors.split(",") if i.strip()]
            for cors_origin in ts_live_cors:
                cors_origins.append(f"http://{cors_origin}.theosumma.com")
                cors_origins.append(f"https://{cors_origin}.theosumma.com")

        cors_origins = list(set(cors_origins))
        return cors_origins


shared_settings = SharedSettings()

def add_origins_to_cors(ms_manager):
    global shared_settings
    current_service = os.environ["CURRENT_MICRO_SERVICE_NAME"]
    current_service = current_service.lower().replace('-', '_')
    services = ms_manager.get_services()

    for service_name, service_info in services.items():
        if service_name == current_service:
            continue
        origins = [
            f'http://{ms_manager.get_internal_service_domainname(service_name)}',
            f'https://{ms_manager.get_internal_service_domainname(service_name)}'
        ]
        if shared_settings.ENVIRONMENT == 'local' and service_info.local_development_url:
            origins.append(service_info.local_development_url)
        shared_settings.BACKEND_CORS_ORIGINS.extend(origins)