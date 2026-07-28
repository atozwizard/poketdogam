# Run: python app/config/settings.py
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    llm_model: str = "template"
    local_llm_provider: str = "ollama"
    local_llm_model: str = "llama3.2:1b"
    ollama_base_url: str = "http://127.0.0.1:11434"
    local_llm_timeout: int = 20
    scan_primary_model: str = "os-ocr"
    scan_fallback_model: str = "manual-search"
    request_timeout: int = 30

    dex_sqlite_path: str = "data/dex.sqlite"
    dex_meta_path: str = "data/dex.meta.json"
    local_match_top_k: int = 3
    local_match_threshold: float = 0.72

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
            "local_llm_provider": settings.local_llm_provider,
            "local_llm_model": settings.local_llm_model,
            "scan_primary_model": settings.scan_primary_model,
            "scan_fallback_model": settings.scan_fallback_model,
            "dex_sqlite_path": settings.dex_sqlite_path,
        }
    )


if __name__ == "__main__":
    main()
