from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Core
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key")
    ENVIRONMENT: str | None = Field(default=None, description="App environment")
    DATABASE_URL: str | None = Field(default=None, description="Database DSN")
    USE_SQLITE: int | None = Field(default=None, description="Use SQLite when 1")

    # Auth/JWT
    JWT_AT_SECRET: str = Field("dev-at-secret", description="JWT secret for access tokens")
    JWT_RT_SECRET: str = Field("dev-rt-secret", description="JWT secret for refresh tokens")
    ACCESS_TOKEN_MINUTES: int = Field(60, description="Access token expiry in minutes")
    REFRESH_TOKEN_DAYS: int = Field(30, description="Refresh token expiry in days")
    AUTH_DEBUG: int = Field(0, description="Enable verbose auth errors when 1")
    MAX_LOGIN_ATTEMPTS: int = Field(5, description="Maximum failed login attempts before lockout")
    LOCKOUT_DURATION_MINS: int = Field(15, description="Lockout duration in minutes after max attempts")

    # Email is handled exclusively by the shared module. Configure email in shared/.env

    # Frontend URLs
    RESET_PASSWORD_URL: str | None = Field(
        default=None,
        description="Absolute URL for password reset page. If contains {token}, it will be replaced; otherwise ?token=... will be appended.",
    )

    # pydantic-settings configuration
    model_config = SettingsConfigDict(
        env_file="pyserver/.env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore extra env vars not modeled
    )


# Singleton pattern
settings = Settings()
