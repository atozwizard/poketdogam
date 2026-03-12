# Run: python app/config/providers.py
from dataclasses import dataclass
from typing import Any

import httpx

from app.config.settings import get_settings


@dataclass(slots=True)
class ProviderBundle:
    settings: Any
    http_client: httpx.Client
    models: dict[str, str]


def build_providers() -> ProviderBundle:
    settings = get_settings()
    models = {
        "chat": settings.llm_model,
        "scan_primary": settings.scan_primary_model,
        "scan_fallback": settings.scan_fallback_model,
    }
    return ProviderBundle(
        settings=settings,
        http_client=httpx.Client(timeout=settings.litellm_timeout),
        models=models,
    )


def main() -> None:
    bundle = build_providers()
    print(bundle.models)
    bundle.http_client.close()


if __name__ == "__main__":
    main()
