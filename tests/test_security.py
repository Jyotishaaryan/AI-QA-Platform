from app.core.security import create_access_token, hash_password, verify_password


def test_password_hash_round_trip():
    encoded = hash_password("correct horse battery staple")
    assert encoded != "correct horse battery staple"
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong", encoded)


def test_jwt_has_expiration(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "jwt_secret_key", "x" * 40)
    token = create_access_token("42", "USER")
    import jwt

    payload = jwt.decode(token, "x" * 40, algorithms=["HS256"])
    assert (
        payload["sub"] == "42"
        and payload["role"] == "USER"
        and "iat" in payload
        and "exp" in payload
    )


def test_production_rejects_placeholder_secret():
    import pytest
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError, match="Production requires"):
        Settings(
            app_env="production",
            jwt_secret_key="replace-with-a-random-secret-at-least-32-characters",
        )
