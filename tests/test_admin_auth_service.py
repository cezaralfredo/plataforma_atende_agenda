from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.admin.auth_service import (
    authenticate_admin,
    bootstrap_admin_account,
    change_admin_password,
    hash_password,
    record_failed_login,
    verify_password,
)
from app.config import Settings


@pytest.fixture
def admin_settings() -> Settings:
    return Settings(
        admin_username="admin-fixture",
        admin_bootstrap_password="fixture-password-only-123",  # noqa: S106
    )


def test_hash_does_not_expose_password_and_verifies_only_the_original_value():
    password = "fixture-password-only-123"  # noqa: S105

    encoded_hash = hash_password(password)

    assert password not in encoded_hash
    assert verify_password(password, encoded_hash)
    assert not verify_password("wrong-fixture-password", encoded_hash)


def test_bootstrap_creates_the_single_account_once(
    db_session: Session, admin_settings: Settings
):
    first_account = bootstrap_admin_account(db_session, admin_settings)
    second_account = bootstrap_admin_account(db_session, admin_settings)

    assert first_account.id == 1
    assert second_account.id == first_account.id
    assert first_account.username == "admin-fixture"
    assert db_session.query(type(first_account)).count() == 1


def test_five_failed_logins_lock_the_account_for_fifteen_minutes(
    db_session: Session, admin_settings: Settings
):
    account = bootstrap_admin_account(db_session, admin_settings)
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)

    for _ in range(5):
        assert authenticate_admin(
            db_session,
            account.username,
            "wrong-fixture-password",
            now,
        ) is None

    db_session.refresh(account)
    assert account.failed_login_count == 5
    assert account.locked_until is not None
    assert account.locked_until.replace(tzinfo=UTC) == now + timedelta(minutes=15)

    db_session.expire_all()
    assert authenticate_admin(
        db_session,
        account.username,
        "wrong-fixture-password",
        now,
    ) is None


def test_record_failed_login_sets_the_lock_on_the_fifth_attempt(
    db_session: Session, admin_settings: Settings
):
    account = bootstrap_admin_account(db_session, admin_settings)
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)

    for _ in range(5):
        record_failed_login(account, now)

    assert account.failed_login_count == 5
    assert account.locked_until == now + timedelta(minutes=15)


def test_bootstrap_requires_a_password_only_before_the_account_exists(
    db_session: Session, admin_settings: Settings
):
    missing_password_settings = Settings(admin_username="admin-fixture")

    with pytest.raises(RuntimeError, match="has not been initialized"):
        bootstrap_admin_account(db_session, missing_password_settings)

    created = bootstrap_admin_account(db_session, admin_settings)
    reused = bootstrap_admin_account(db_session, missing_password_settings)

    assert reused.id == created.id


def test_successful_authentication_clears_failures_and_password_change_revokes_sessions(
    db_session: Session, admin_settings: Settings
):
    account = bootstrap_admin_account(db_session, admin_settings)
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    record_failed_login(account, now)
    db_session.commit()

    authenticated = authenticate_admin(
        db_session, account.username, "fixture-password-only-123", now
    )
    assert authenticated is not None
    assert authenticated.failed_login_count == 0
    assert authenticated.locked_until is None

    change_admin_password(db_session, authenticated, "new-fixture-password-456")

    assert authenticated.auth_version == 2
    assert verify_password("new-fixture-password-456", authenticated.password_hash)
