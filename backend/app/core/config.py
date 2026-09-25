"""Core configuration — everything is env-driven (see .env.example)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    # 5173 = Flutter web dev server; 8080 = the nginx web front end in
    # infra/docker-compose.yml (same-origin proxy, so 8080 only matters if the
    # PWA is built to call the API directly instead).
    cors_origins: str = (
        "http://localhost:8000,http://localhost:3000,http://localhost:5173,http://localhost:8080"
    )

    # Rate limiting (Phase 6) — Redis fixed window per client IP. Fails open:
    # without Redis (the default demo setup) requests are never rejected.
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # IMD — official IMD API Management Platform (https://api.imd.gov.in)
    # Access requires an API key (verified 2026-09-06: live endpoint returns
    # {"error": "API key missing"}) and, per IMD docs, IP whitelisting.
    # See docs/IMD-ACCESS.md for the application checklist.
    imd_base_url: str = "https://api.imd.gov.in"
    imd_api_key: str = ""
    imd_enabled: bool = True

    # Open-Meteo — free, keyless, GFS-derived (resilience / fallback layer)
    open_meteo_base_url: str = "https://api.open-meteo.com"

    # SACHET — NDMA National Disaster Alert Portal (public CAP feed, ETag caching)
    sachet_base_url: str = "https://sachet.ndma.gov.in"
    sachet_feed_path: str = "cap_public_website/rss/rss_india.xml"

    # Station snapshot fallback for the IMD nearest-station index
    # (sample data until a live cityforecast_mapping capture is stored)
    station_snapshot_path: str = "data/stations_sample.json"

    # Geocoding (Phase 3) — Open-Meteo forward geocoding (keyless) and
    # BigDataCloud reverse geocoding (keyless, free tier). Both verified
    # live on 2026-09-06; see docs/DATA-SOURCES.md.
    geocoding_base_url: str = "https://geocoding-api.open-meteo.com"
    reverse_geocoding_base_url: str = "https://api.bigdatacloud.net"
    cities_seed_path: str = "data/cities_seed.json"

    # LLM — modular providers; "fallback" is the deterministic no-LLM
    # responder (implemented in Phase 5). Keys are optional for the prototype.
    llm_provider: str = "fallback"
    openai_api_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""

    # Deployment (optional): a built Flutter web bundle to serve from this same
    # process. Empty = API only (the default, and what the Docker `web` profile
    # replaces with nginx). Set it to publish the PWA and the API on ONE origin —
    # the browser then makes no cross-origin call, which is what makes a single
    # public URL (a tunnel, a free host) possible. Path is relative to the CWD
    # the server starts in, e.g. WEB_DIR=../frontend/build/web.
    web_dir: str = ""

    # Infra (consumed from Phase 3 onwards)
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://weathergpt:weathergpt@localhost:5432/weathergpt"

    @property
    def imd_configured(self) -> bool:
        """True when the IMD provider may actually be called."""
        return self.imd_enabled and bool(self.imd_api_key.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def rate_limit_config(self) -> tuple[int, int]:
        """(requests, window_seconds) with sane floors."""
        return max(1, self.rate_limit_requests), max(1, self.rate_limit_window_seconds)


@lru_cache
def get_settings() -> Settings:
    return Settings()