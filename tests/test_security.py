"""Tests for authentication and security module."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone
from jose import jwt

from app.core.exceptions import AppException, AuthException
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_role,
)


# ─── Password hashing ────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_returns_bcrypt_string(self):
        hashed = hash_password("testpassword")
        assert hashed.startswith("$2b$")

    def test_hash_is_not_plaintext(self):
        hashed = hash_password("testpassword")
        assert hashed != "testpassword"

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("testpassword")
        h2 = hash_password("testpassword")
        assert h1 != h2  # bcrypt uses random salt

    def test_verify_correct_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_verify_empty_password(self):
        hashed = hash_password("something")
        assert verify_password("", hashed) is False


# ─── JWT token creation ──────────────────────────────────────────────────────

class TestCreateAccessToken:
    @patch("app.core.security.settings")
    def test_token_contains_correct_claims(self, mock_settings):
        mock_settings.SECRET_KEY = "testsecret"
        mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 60

        token = create_access_token(user_id=42, role="admin")
        payload = jwt.decode(token, "testsecret", algorithms=["HS256"])

        assert payload["sub"] == "42"
        assert payload["role"] == "admin"
        assert "exp" in payload

    @patch("app.core.security.settings")
    def test_token_expiry_is_set(self, mock_settings):
        mock_settings.SECRET_KEY = "testsecret"
        mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 30

        token = create_access_token(user_id=1, role="operator")
        payload = jwt.decode(token, "testsecret", algorithms=["HS256"])

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        # Token should expire roughly 30 minutes from now
        diff = (exp - now).total_seconds()
        assert 1700 < diff < 1900  # ~30 min with some tolerance


# ─── get_current_user ─────────────────────────────────────────────────────────

class TestGetCurrentUser:
    @patch("app.core.security.settings")
    def test_valid_token_returns_user(self, mock_settings):
        mock_settings.SECRET_KEY = "testsecret"
        mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 60

        token = create_access_token(user_id=5, role="operator")

        mock_user = MagicMock()
        mock_user.id = 5
        mock_user.is_active = True

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        credentials = MagicMock()
        credentials.credentials = token

        user = get_current_user(credentials=credentials, db=mock_db)
        assert user.id == 5

    @patch("app.core.security.settings")
    def test_expired_token_raises_401(self, mock_settings):
        mock_settings.SECRET_KEY = "testsecret"
        mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 60

        payload = {
            "sub": "1",
            "role": "admin",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(payload, "testsecret", algorithm="HS256")

        credentials = MagicMock()
        credentials.credentials = token
        mock_db = MagicMock()

        with pytest.raises(AuthException) as exc_info:
            get_current_user(credentials=credentials, db=mock_db)
        assert exc_info.value.status_code == 401

    @patch("app.core.security.settings")
    def test_invalid_token_raises_401(self, mock_settings):
        mock_settings.SECRET_KEY = "testsecret"

        credentials = MagicMock()
        credentials.credentials = "not.a.valid.token"
        mock_db = MagicMock()

        with pytest.raises(AuthException) as exc_info:
            get_current_user(credentials=credentials, db=mock_db)
        assert exc_info.value.status_code == 401

    @patch("app.core.security.settings")
    def test_inactive_user_raises_401(self, mock_settings):
        mock_settings.SECRET_KEY = "testsecret"
        mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 60

        token = create_access_token(user_id=10, role="operator")

        mock_user = MagicMock()
        mock_user.is_active = False

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        credentials = MagicMock()
        credentials.credentials = token

        with pytest.raises(AuthException) as exc_info:
            get_current_user(credentials=credentials, db=mock_db)
        assert exc_info.value.status_code == 403

    @patch("app.core.security.settings")
    def test_user_not_found_raises_401(self, mock_settings):
        mock_settings.SECRET_KEY = "testsecret"
        mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 60

        token = create_access_token(user_id=999, role="admin")

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        credentials = MagicMock()
        credentials.credentials = token

        with pytest.raises(AuthException) as exc_info:
            get_current_user(credentials=credentials, db=mock_db)
        assert exc_info.value.status_code == 401

    @patch("app.core.security.settings")
    def test_token_without_sub_raises_401(self, mock_settings):
        mock_settings.SECRET_KEY = "testsecret"

        payload = {
            "role": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, "testsecret", algorithm="HS256")

        credentials = MagicMock()
        credentials.credentials = token
        mock_db = MagicMock()

        with pytest.raises(AuthException) as exc_info:
            get_current_user(credentials=credentials, db=mock_db)
        assert exc_info.value.status_code == 401


# ─── require_role ─────────────────────────────────────────────────────────────

class TestRequireRole:
    def test_allowed_role_passes(self):
        checker = require_role("admin", "operator")
        mock_user = MagicMock()
        mock_user.role = "admin"

        result = checker(current_user=mock_user)
        assert result == mock_user

    def test_disallowed_role_raises_403(self):
        checker = require_role("admin")
        mock_user = MagicMock()
        mock_user.role = "viewer"

        with pytest.raises(AuthException) as exc_info:
            checker(current_user=mock_user)
        assert exc_info.value.status_code == 403
