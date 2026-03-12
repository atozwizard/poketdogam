# Run: python app/config/settings.py
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    upstage_api_key: str = ""
    gemini_api_key: str = ""
    openai_api_key: str = ""
    openweathermap_api_key: str = ""

    llm_model: str = "solar-pro2"
    scan_primary_model: str = "gemini"
    scan_fallback_model: str = "gpt-4.1-mini"
    use_litellm: bool = True
    litellm_num_retries: int = 3
    litellm_timeout: int = 30

    supabase_url: str = ""
    supabase_key: str = ""
    supabase_connection_string: str = ""

    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def main() -> None:
    settings = get_settings()
    print(
        {
            "environment": settings.environment,
            "chat_model": settings.llm_model,
            "scan_primary_model": settings.scan_primary_model,
            "scan_fallback_model": settings.scan_fallback_model,
        }
    )


if __name__ == "__main__":
    main()
