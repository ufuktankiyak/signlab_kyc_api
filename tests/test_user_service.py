"""Tests for user service."""

import pytest
from unittest.mock import MagicMock

from app.services.user_service import get_user_by_id


class TestGetUserById:
    def test_returns_user_when_found(self, mock_db):
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@test.com"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        result = get_user_by_id(mock_db, 1)
        assert result.id == 1
        assert result.email == "test@test.com"

    def test_returns_none_when_not_found(self, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = get_user_by_id(mock_db, 999)
        assert result is None
