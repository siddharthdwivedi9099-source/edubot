from app.auth.rbac import (
    AuthContext, Role, has_permission, can_read, allowed_scopes,
    school_scope_clause, student_scope_clause,
    topic_allowed, visible_tables,
    PERMISSIONS, ROLE_TOPICS, ROLE_FORBIDDEN_TOPICS,
)
from app.auth.jwt_handler import (
    current_user, current_user_optional,
    authenticate, issue_token, decode_token,
    update_last_login, TokenResponse,
)

__all__ = [
    "AuthContext", "Role",
    "has_permission", "can_read", "allowed_scopes",
    "school_scope_clause", "student_scope_clause",
    "topic_allowed", "visible_tables",
    "PERMISSIONS", "ROLE_TOPICS", "ROLE_FORBIDDEN_TOPICS",
    "current_user", "current_user_optional",
    "authenticate", "issue_token", "decode_token",
    "update_last_login", "TokenResponse",
]
