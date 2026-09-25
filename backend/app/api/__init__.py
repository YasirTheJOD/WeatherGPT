"""API layer — public HTTP surface. Routers are mounted under /api/v1."""

from app.api.routes import alerts, health, locations, weather

__all__ = ["alerts", "health", "locations", "weather"]