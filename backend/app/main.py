"""WeatherGPT backend application factory."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.routes import alerts, chat, health, locations, sources, weather
from app.core.cache import CacheService
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, log_event
from app.core.middleware import RateLimitMiddleware, RequestContextMiddleware
from app.core.rate_limit import RateLimiter
from app.providers.alerts.sachet import SachetAlertProvider
from app.providers.base import ProviderRegistry
from app.providers.llm import build_llm_provider
from app.providers.weather.imd import IMDProvider
from app.providers.weather.met_norway import MetNorwayProvider
from app.providers.weather.open_meteo import OpenMeteoProvider
from app.services.location.alias_index import AliasIndex
from app.services.location.geocoder import BigDataCloudReverseGeocoder, OpenMeteoGeocoder
from app.services.location.imd_mapping import IMDMappingLoader
from app.services.location.resolver import LocationResolver
from app.services.location.station_index import StationIndex
from app.services.orchestrator import ChatOrchestrator
from app.services.query_understanding import QueryUnderstandingService
from app.services.validation.validator import ValidationService

logger = logging.getLogger("app.web")


def build_registry(
    settings: Settings, station_index: StationIndex | None = None
) -> ProviderRegistry:
    """Provider chain: IMD (authoritative) first, then Open-Meteo and MET Norway
    as keyless fallbacks, with the validation gate + Redis cache attached.
    Ordering is the preference policy — swap or extend here, not in callers.

    Two fallbacks is deliberate, not belt-and-braces: a single vendor's rate
    limiter must not be able to take the weather down (see met_norway.py).
    """
    return ProviderRegistry(
        [
            IMDProvider(settings, station_index=station_index),
            OpenMeteoProvider(settings),
            MetNorwayProvider(settings),
        ],
        validator=ValidationService(),
        cache=CacheService(settings.redis_url),
    )


def build_location_resolver(
    settings: Settings, station_index: StationIndex | None = None
) -> LocationResolver:
    """Aliases first (offline, deterministic), Open-Meteo geocoding second,
    BigDataCloud reverse as fallback for reverse lookups."""
    return LocationResolver(
        alias_index=AliasIndex.load_seed(settings.cities_seed_path),
        geocoder=OpenMeteoGeocoder(settings),
        reverse_geocoder=BigDataCloudReverseGeocoder(settings),
        station_index=station_index,
    )


class SpaStaticFiles(StaticFiles):
    """Static files with an SPA fallback: an unknown path serves `index.html`.

    Flutter web routes are client-side, so `/map` is a 404 on disk — a deep link
    or a refresh on one has to return the shell and let the router take over.
    `/api/v1/**` and `/docs` are matched by earlier routes and never reach here.
    """

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            # Missing file: it is a client-side route, so serve the shell. If the
            # shell is missing too this raises 404 again — a bundle that was never
            # built should look broken, not blank.
            return await super().get_response("index.html", scope)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Station index: live cityforecast_mapping when keyed, sample snapshot
        # otherwise (see docs/IMD-ACCESS.md). Built here because it is async.
        loader = IMDMappingLoader(settings)
        index = await loader.build_index(snapshot_path=settings.station_snapshot_path)
        app.state.station_index = index
        app.state.registry = build_registry(settings, index)
        app.state.location_resolver = build_location_resolver(settings, index)
        yield

    app = FastAPI(
        title="WeatherGPT API",
        description="Conversational weather intelligence — SIH 2026 prototype",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Phase 6 hardening: rate limit inside the request-context middleware so
    # 429 responses still carry X-Request-ID and get an access log line.
    # Starlette wraps in reverse, so the last middleware added is outermost.
    limit, window = settings.rate_limit_config
    app.state.rate_limiter = RateLimiter(
        redis_url=settings.redis_url,
        limit=limit,
        window_seconds=window,
        enabled=settings.rate_limit_enabled,
    )
    app.add_middleware(
        RateLimitMiddleware,
        limiter=app.state.rate_limiter,
        prefix="/api/v1",
        exempt_paths={"/api/v1/health"},
    )
    app.add_middleware(RequestContextMiddleware)

    app.state.settings = settings
    app.state.station_index = StationIndex([])
    app.state.registry = build_registry(settings)
    app.state.alerts = SachetAlertProvider(settings)
    app.state.sachet_etag = None
    app.state.location_resolver = build_location_resolver(settings)
    app.state.llm = build_llm_provider(settings)
    app.state.chat_orchestrator = ChatOrchestrator(QueryUnderstandingService())

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(weather.router, prefix="/api/v1")
    app.include_router(alerts.router, prefix="/api/v1")
    app.include_router(locations.router, prefix="/api/v1")
    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(sources.router, prefix="/api/v1")

    # Optional single-origin deployment: serve the built Flutter PWA from this
    # same app, so a public URL needs no second host and the browser makes no
    # cross-origin call. Mounted last, so every /api route keeps priority.
    web_dir = Path(settings.web_dir) if settings.web_dir else None
    if web_dir is not None and web_dir.is_dir():
        app.mount("/", SpaStaticFiles(directory=str(web_dir), html=True), name="web")
    else:
        if settings.web_dir:
            # Loud but non-fatal: a typo'd path must not look like a working deploy.
            log_event(logger, event="web_dir_missing", path=settings.web_dir)

        @app.get("/")
        async def root() -> dict:
            return {
                "service": "WeatherGPT",
                "docs": "/docs",
                "health": "/api/v1/health",
            }

    return app


app = create_app()