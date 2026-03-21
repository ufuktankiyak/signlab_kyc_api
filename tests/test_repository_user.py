"""Repository-level tests for User service — real in-memory SQLite DB."""

import pytest
from app.models.user import User
from app.services.user_service import get_user_by_id


class TestGetUserByIdRepo:
    def _create_user(self, db_session, **kwargs):
        defaults = {
            "email": "test@signlab.com",
            "password_hash": "$2b$12$fakehash",
            "role": "operator",
            "is_active": True,
        }
        defaults.update(kwargs)
        user = User(**defaults)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    def test_returns_user_by_id(self, db_session):
        user = self._create_user(db_session, email="john@test.com")
        result = get_user_by_id(db_session, user.id)

        assert result is not None
        assert result.id == user.id
        assert result.email == "john@test.com"

    def test_returns_none_for_nonexistent_id(self, db_session):
        result = get_user_by_id(db_session, 9999)
        assert result is None

    def test_returns_correct_user_among_many(self, db_session):
        u1 = self._create_user(db_session, email="a@test.com")
        u2 = self._create_user(db_session, email="b@test.com")
        u3 = self._create_user(db_session, email="c@test.com")

        result = get_user_by_id(db_session, u2.id)
        assert result.email == "b@test.com"

    def test_returns_inactive_user(self, db_session):
        user = self._create_user(db_session, email="inactive@test.com", is_active=False)
        result = get_user_by_id(db_session, user.id)

        assert result is not None
        assert result.is_active is False

    def test_returns_user_with_all_fields(self, db_session):
        user = self._create_user(
            db_session,
            email="admin@signlab.com",
            role="admin",
            is_active=True,
        )
        result = get_user_by_id(db_session, user.id)

        assert result.email == "admin@signlab.com"
        assert result.role == "admin"
        assert result.is_active is True
        assert result.password_hash == "$2b$12$fakehash"
