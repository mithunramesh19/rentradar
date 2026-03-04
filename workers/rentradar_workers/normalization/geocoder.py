"""Geocoding service — Google Maps API with Redis cache and NYC bounds validation."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass

import requests
from redis import Redis

from rentradar_common.geo import is_valid_nyc_coordinate

logger = logging.getLogger(__name__)

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_GEOCODE_API_KEY", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


@dataclass
class GeoResult:
    """Geocoding result."""

    lat: float
    lng: float
    formatted_address: str
    neighborhood: str
    borough: str
    zip_code: str
    valid_nyc: bool


class Geocoder:
    """Google Maps geocoder with Redis caching and NYC validation."""

    def __init__(
        self,
        api_key: str = "",
        redis_client: Redis | None = None,
    ) -> None:
        self.api_key = api_key or GOOGLE_MAPS_API_KEY
        self._redis = redis_client

    @property
    def redis(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    def geocode(self, address: str) -> GeoResult | None:
        """Geocode an address. Returns cached result if available."""
        if not address:
            return None

        cache_key = self._cache_key(address)

        # Check cache
        cached = self._cache_get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for %s", address)
            return cached

        # Call Google Maps
        result = self._call_api(address)
        if result is not None:
            self._cache_set(cache_key, result)

        return result

    def _call_api(self, address: str) -> GeoResult | None:
        """Call Google Maps Geocoding API."""
        if not self.api_key:
            logger.warning("No Google Maps API key configured")
            return None

        params = {
            "address": address,
            "key": self.api_key,
            "components": "country:US",
        }

        try:
            resp = requests.get(GEOCODE_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException:
            logger.exception("Geocode API request failed for %s", address)
            return None

        if data.get("status") != "OK" or not data.get("results"):
            logger.warning("Geocode returned status=%s for %s", data.get("status"), address)
            return None

        top = data["results"][0]
        location = top["geometry"]["location"]
        lat = location["lat"]
        lng = location["lng"]

        # Extract address components
        components = {c["types"][0]: c for c in top.get("address_components", []) if c["types"]}
        neighborhood = components.get("neighborhood", {}).get("long_name", "")
        borough = components.get("sublocality_level_1", {}).get("long_name", "")
        zip_code = components.get("postal_code", {}).get("long_name", "")

        return GeoResult(
            lat=lat,
            lng=lng,
            formatted_address=top.get("formatted_address", ""),
            neighborhood=neighborhood,
            borough=borough,
            zip_code=zip_code,
            valid_nyc=is_valid_nyc_coordinate(lat, lng),
        )

    def _cache_key(self, address: str) -> str:
        h = hashlib.md5(address.lower().strip().encode()).hexdigest()  # noqa: S324
        return f"geocode:{h}"

    def _cache_get(self, key: str) -> GeoResult | None:
        try:
            raw = self.redis.get(key)
        except Exception:
            logger.debug("Redis cache read failed", exc_info=True)
            return None
        if raw is None:
            return None
        try:
            d = json.loads(raw)
            return GeoResult(**d)
        except (json.JSONDecodeError, TypeError):
            return None

    def _cache_set(self, key: str, result: GeoResult) -> None:
        try:
            payload = json.dumps(
                {
                    "lat": result.lat,
                    "lng": result.lng,
                    "formatted_address": result.formatted_address,
                    "neighborhood": result.neighborhood,
                    "borough": result.borough,
                    "zip_code": result.zip_code,
                    "valid_nyc": result.valid_nyc,
                }
            )
            self.redis.setex(key, CACHE_TTL_SECONDS, payload)
        except Exception:
            logger.debug("Redis cache write failed", exc_info=True)
