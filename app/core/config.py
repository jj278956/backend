from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Neptune Shopping Backend"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://neptune:neptune@db:5432/neptune"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://neptune:neptune@db:5432/neptune"

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"

    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
