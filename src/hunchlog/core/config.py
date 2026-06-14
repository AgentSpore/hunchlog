"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings sourced from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_path: str = "hunchlog.db"
    cors_origins: str = "*"
    frontend_dir: str = "frontend"

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list; '*' stays a single wildcard entry."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
