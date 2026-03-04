"""Tests for API endpoint route registration and schema validation."""

from rentradar.main import app
from rentradar.routers.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)


class TestRouteRegistration:
    """Verify all expected routes are registered on the app."""

    def _paths(self) -> set[str]:
        return {r.path for r in app.routes}

    def test_health(self):
        assert "/health" in self._paths()

    def test_listings_search(self):
        assert "/listings" in self._paths()

    def test_listings_detail(self):
        assert "/listings/{listing_id}" in self._paths()

    def test_listings_similar(self):
        assert "/listings/{listing_id}/similar" in self._paths()

    def test_listings_stats(self):
        assert "/listings/stats" in self._paths()

    def test_auth_register(self):
        assert "/auth/register" in self._paths()

    def test_auth_login(self):
        assert "/auth/login" in self._paths()

    def test_auth_refresh(self):
        assert "/auth/refresh" in self._paths()

    def test_saved_searches(self):
        paths = self._paths()
        assert "/searches" in paths
        assert "/searches/{search_id}" in paths
        assert "/searches/{search_id}/test" in paths

    def test_notifications(self):
        paths = self._paths()
        assert "/notifications" in paths
        assert "/notifications/{notification_id}/read" in paths
        assert "/notifications/read-all" in paths


class TestAuthHelpers:
    def test_password_hashing(self):
        hashed = hash_password("testpassword")
        assert verify_password("testpassword", hashed)
        assert not verify_password("wrong", hashed)

    def test_create_access_token(self):
        token = create_access_token(user_id=42)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self):
        token = create_refresh_token(user_id=42)
        assert isinstance(token, str)

    def test_token_contains_user_id(self):
        from jose import jwt
        from rentradar.config import settings

        token = create_access_token(user_id=99)
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "99"

    def test_refresh_token_has_type(self):
        from jose import jwt
        from rentradar.config import settings

        token = create_refresh_token(user_id=99)
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["type"] == "refresh"
