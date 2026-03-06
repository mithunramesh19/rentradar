"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://rentradar:rentradar@localhost:5433/rentradar"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # Google Maps
    google_maps_api_key: str = ""

    # SendGrid
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "alerts@rentradar.app"

    # Firebase
    firebase_credentials_path: str = "./firebase-credentials.json"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
