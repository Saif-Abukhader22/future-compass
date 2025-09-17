from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.config import load_env_variables

version = load_env_variables('identity')


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra='ignore'
    )

    APP_STATUS: str
    APP_VERSION: str = version
    CURRENT_MICRO_SERVICE_NAME: str

    DATABASE_URL: str
    POOL_SIZE: str
    MAX_OVERFLOW: str
    POOL_TIMEOUT: str
    POOL_RECYCLE: str

    # Auth
    ACCESS_TOKEN_EXPIRY: int
    REFRESH_TOKEN_EXPIRY_PC: int
    REFRESH_TOKEN_EXPIRY_MO: int

    JWT_RT_SECRET: str
    RATE_LIMIT: str

    # reCaption Vars
    RECAPTCHA_SECRET_KEY: str
    RECAPTCHA_SITE_KEY: str
    RECAPTCHA_DISABLED: bool = False

    # Auth wrong login vars
    LOCKOUT_DURATION_MINS: int
    MAX_LOGIN_ATTEMPTS: int

    # MAIN_HOST_NAME: str
    # LOCAL_DEBUG_PORT: str

    #AuthProviders
    GOOGLE_CLIENT_ID: str
    FACEBOOK_APP_ID: str
    FACEBOOK_APP_SECRET: str


settings = Settings()
