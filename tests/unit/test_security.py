from app.core.security import generate_session_token
from app.core.security import hash_password
from app.core.security import hash_session_token
from app.core.security import summarize_client_value
from app.core.security import verify_password


def test_hash_password_and_verify_password_cover_success_and_failure() -> None:
    password_hash = hash_password("secret-password")

    assert password_hash != "secret-password"
    assert verify_password("secret-password", password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_verify_password_returns_false_for_malformed_hash() -> None:
    assert verify_password("secret-password", "invalid-format") is False


def test_session_token_hash_and_client_summary_are_stable() -> None:
    session_token = generate_session_token()
    secret = "0123456789abcdef0123456789abcdef"

    assert len(session_token) >= 32
    assert hash_session_token(session_token, secret=secret) == hash_session_token(
        session_token,
        secret=secret,
    )
    assert summarize_client_value("127.0.0.1", secret=secret) == summarize_client_value(
        "127.0.0.1",
        secret=secret,
    )
