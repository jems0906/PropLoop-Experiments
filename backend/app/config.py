from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PropLoop Experiments"
    database_url: str = "sqlite:///./proploop.db"
    ai_provider: str = "mock"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    github_token: str | None = None
    github_repository: str | None = None
    github_base_branch: str = "main"
    coding_agent_model: str = "gpt-4o-mini"
    quality_ingest_token: str | None = None
    frontend_url: str = "http://localhost:5173"
    bootstrap_token: str | None = None
    cookie_secure: bool = False
    session_ttl_seconds: int = 43200
    invite_ttl_seconds: int = 172800

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
