from __future__ import annotations

from datetime import UTC
from datetime import datetime
from datetime import timedelta
import json
import logging
from sqlite3 import Row

from app.api.errors import ApiError
from app.core.security import generate_session_token
from app.core.security import hash_password
from app.core.security import hash_session_token
from app.core.security import summarize_client_value
from app.core.security import verify_password
from app.repositories.admin_auth_repository import AdminAuthRepository
from app.schemas.admin_auth import AdminAuthenticatedUser
from app.schemas.admin_auth import AdminLoginData
from app.schemas.admin_auth import AdminPasswordChangeData
from app.schemas.admin_auth import AdminSessionContext

logger = logging.getLogger(__name__)


class AdminAuthService:
    def __init__(
        self,
        repository: AdminAuthRepository,
        *,
        session_secret: str,
        session_ttl_hours: int,
    ) -> None:
        self.repository = repository
        self.session_secret = session_secret
        self.session_ttl_hours = session_ttl_hours

    def login(
        self,
        *,
        username: str,
        password: str,
        trace_id: str,
        client_ip: str | None,
        user_agent: str | None,
    ) -> AdminLoginData:
        user_row = self.repository.get_admin_user_by_username(username=username)
        if user_row is None or not self._is_login_allowed(user_row, password=password):
            logger.warning("Admin login rejected for username=%s", username)
            raise ApiError(
                status_code=401,
                error_code="ADMIN_AUTH_INVALID_CREDENTIALS",
                message="用户名或密码错误",
            )

        issued_at = utc_now()
        expires_at = issued_at + timedelta(hours=self.session_ttl_hours)
        session_token = generate_session_token()
        session_token_hash = hash_session_token(session_token, secret=self.session_secret)
        request_source = build_request_source(
            client_ip=client_ip,
            user_agent=user_agent,
            secret=self.session_secret,
        )
        session_id = self.repository.create_session(
            admin_user_id=int(user_row["id"]),
            session_token_hash=session_token_hash,
            session_version=1,
            issued_at_utc=to_utc_string(issued_at),
            expires_at_utc=to_utc_string(expires_at),
            client_ip=summarize_client_value(client_ip, secret=self.session_secret),
            user_agent=summarize_client_value(user_agent, secret=self.session_secret),
        )
        self.repository.update_admin_last_login(
            admin_user_id=int(user_row["id"]),
            logged_in_at_utc=to_utc_string(issued_at),
        )
        self.repository.insert_audit_log(
            admin_user_id=int(user_row["id"]),
            action_type="admin_login",
            target_type="admin_session",
            target_id=str(session_id),
            before_state_json=None,
            after_state_json=json.dumps(
                {
                    "session_id": session_id,
                    "expires_at_utc": to_utc_string(expires_at),
                },
                ensure_ascii=False,
            ),
            request_source=request_source,
            trace_id=trace_id,
            created_at_utc=to_utc_string(issued_at),
        )
        logger.info("Admin login succeeded for username=%s session_id=%s", username, session_id)
        return AdminLoginData(
            session_token=session_token,
            expires_at_utc=to_utc_string(expires_at),
            user=AdminAuthenticatedUser(
                id=int(user_row["id"]),
                username=str(user_row["username"]),
                role_name=str(user_row["role_name"]),
            ),
        )

    def authenticate_session(self, *, session_token: str) -> AdminSessionContext:
        session_row = self.repository.get_session_with_user(
            session_token_hash=hash_session_token(session_token, secret=self.session_secret)
        )
        if session_row is None:
            raise ApiError(
                status_code=401,
                error_code="ADMIN_AUTH_UNAUTHORIZED",
                message="未登录或会话无效",
            )

        if str(session_row["status"]) != "enabled":
            logger.warning(
                "Admin session rejected because account is disabled: admin_user_id=%s",
                session_row["admin_user_id"],
            )
            raise ApiError(
                status_code=401,
                error_code="ADMIN_AUTH_UNAUTHORIZED",
                message="未登录或会话无效",
            )

        if session_row["revoked_at_utc"] is not None:
            raise ApiError(
                status_code=401,
                error_code="ADMIN_AUTH_UNAUTHORIZED",
                message="未登录或会话无效",
            )

        expires_at = parse_utc_string(str(session_row["expires_at_utc"]))
        if expires_at <= utc_now():
            logger.info("Admin session expired: session_id=%s", session_row["session_id"])
            raise ApiError(
                status_code=401,
                error_code="ADMIN_AUTH_SESSION_EXPIRED",
                message="会话已过期，请重新登录",
            )

        seen_at_utc = to_utc_string(utc_now())
        self.repository.touch_session(
            session_id=int(session_row["session_id"]),
            seen_at_utc=seen_at_utc,
        )
        return AdminSessionContext(
            session_id=int(session_row["session_id"]),
            admin_user_id=int(session_row["admin_user_id"]),
            username=str(session_row["username"]),
            role_name=str(session_row["role_name"]),
            session_version=int(session_row["session_version"]),
            expires_at_utc=str(session_row["expires_at_utc"]),
        )

    def logout(
        self,
        *,
        session: AdminSessionContext,
        trace_id: str,
        client_ip: str | None,
        user_agent: str | None,
    ) -> None:
        revoked_at = utc_now()
        self.repository.revoke_session(
            session_id=session.session_id,
            revoked_at_utc=to_utc_string(revoked_at),
        )
        self.repository.insert_audit_log(
            admin_user_id=session.admin_user_id,
            action_type="admin_logout",
            target_type="admin_session",
            target_id=str(session.session_id),
            before_state_json=json.dumps({"revoked": False}, ensure_ascii=False),
            after_state_json=json.dumps(
                {"revoked": True, "revoked_at_utc": to_utc_string(revoked_at)},
                ensure_ascii=False,
            ),
            request_source=build_request_source(
                client_ip=client_ip,
                user_agent=user_agent,
                secret=self.session_secret,
            ),
            trace_id=trace_id,
            created_at_utc=to_utc_string(revoked_at),
        )
        logger.info(
            "Admin logout succeeded for username=%s session_id=%s",
            session.username,
            session.session_id,
        )

    def change_password(
        self,
        *,
        session: AdminSessionContext,
        current_password: str,
        new_password: str,
        confirm_new_password: str,
        trace_id: str,
        client_ip: str | None,
        user_agent: str | None,
    ) -> AdminPasswordChangeData:
        user_row = self.repository.get_admin_user_by_id(admin_user_id=session.admin_user_id)
        if user_row is None or str(user_row["status"]) != "enabled":
            raise ApiError(
                status_code=401,
                error_code="ADMIN_AUTH_UNAUTHORIZED",
                message="未登录或会话无效",
            )

        if not verify_password(current_password, str(user_row["password_hash"])):
            logger.warning(
                "Admin password change rejected because current password is invalid: username=%s",
                session.username,
            )
            raise ApiError(
                status_code=401,
                error_code="ADMIN_AUTH_INVALID_CURRENT_PASSWORD",
                message="当前密码错误",
            )

        if new_password != confirm_new_password:
            raise ApiError(
                status_code=422,
                error_code="ADMIN_AUTH_PASSWORD_CONFIRMATION_MISMATCH",
                message="两次输入的新密码不一致",
            )

        if current_password == new_password:
            raise ApiError(
                status_code=422,
                error_code="ADMIN_AUTH_PASSWORD_REUSE_NOT_ALLOWED",
                message="新密码不能与当前密码相同",
            )

        changed_at = utc_now()
        changed_at_utc = to_utc_string(changed_at)
        self.repository.update_admin_password(
            admin_user_id=session.admin_user_id,
            password_hash=hash_password(new_password),
            updated_at_utc=changed_at_utc,
        )
        revoked_session_count = self.repository.revoke_sessions_for_admin(
            admin_user_id=session.admin_user_id,
            revoked_at_utc=changed_at_utc,
        )
        self.repository.insert_audit_log(
            admin_user_id=session.admin_user_id,
            action_type="admin_password_changed",
            target_type="admin_user",
            target_id=str(session.admin_user_id),
            before_state_json=json.dumps(
                {"password_changed": False},
                ensure_ascii=False,
            ),
            after_state_json=json.dumps(
                {
                    "password_changed": True,
                    "relogin_required": True,
                    "revoked_session_count": revoked_session_count,
                },
                ensure_ascii=False,
            ),
            request_source=build_request_source(
                client_ip=client_ip,
                user_agent=user_agent,
                secret=self.session_secret,
            ),
            trace_id=trace_id,
            created_at_utc=changed_at_utc,
        )
        logger.info(
            "Admin password changed for username=%s revoked_session_count=%s",
            session.username,
            revoked_session_count,
        )
        return AdminPasswordChangeData(
            relogin_required=True,
            revoked_session_count=max(revoked_session_count, 1),
        )

    def _is_login_allowed(self, user_row: Row, *, password: str) -> bool:
        return str(user_row["status"]) == "enabled" and verify_password(
            password,
            str(user_row["password_hash"]),
        )


def build_request_source(
    *, client_ip: str | None, user_agent: str | None, secret: str
) -> str | None:
    parts: list[str] = []
    ip_digest = summarize_client_value(client_ip, secret=secret)
    user_agent_digest = summarize_client_value(user_agent, secret=secret)
    if ip_digest is not None:
        parts.append(f"ip_hash={ip_digest}")
    if user_agent_digest is not None:
        parts.append(f"user_agent_hash={user_agent_digest}")
    if not parts:
        return None
    return ";".join(parts)


def utc_now() -> datetime:
    return datetime.now(tz=UTC).replace(microsecond=0)


def to_utc_string(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def parse_utc_string(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
