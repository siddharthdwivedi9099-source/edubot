"""
Role-Based Access Control (RBAC) for EduBot.

Defines:
  • Six roles (student, parent, teacher, principal, admin, super_admin)
  • A permission matrix mapping each role to allowed resources & operations
  • Row-level scoping rules — what records each role can SEE
  • Topic scoping rules — what TYPES of questions each role can ask

Other modules (agent, erp_connector, guardrails) consult this module to
enforce access. Auth context flows in via FastAPI dependency `current_user`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Set, Dict, Optional

Role = Literal["student", "parent", "teacher", "principal", "admin", "super_admin"]


# ─────────────────────────────────────────────────────────────────────────────
# Permission matrix
# ─────────────────────────────────────────────────────────────────────────────
# A "permission" is a verb on a resource: 'read:attendance', 'read:fees', etc.
# We don't model write permissions because EduBot is read-only.

# Resources: attendance, fees/payments, marks/exams/progress, assignments,
# discipline, profile, events, kb (knowledge base), policies, schedule.
# Modifiers: 'self', 'children', 'class', 'school', 'all'.

PERMISSIONS: Dict[Role, Set[str]] = {
    "student": {
        # Student sees only their own data + general info
        "read:attendance:self",
        "read:marks:self",
        "read:assignments:self",
        "read:progress:self",
        "read:profile:self",
        "read:fees:self",
        "read:schedule:self",
        "read:events:school",       # school-wide events visible
        "read:kb:student",
        "read:policies:public",
        # Explicitly NOT: discipline (only via parent), other students' data
    },
    "parent": {
        # Parent sees own children's data + general info
        "read:attendance:children",
        "read:marks:children",
        "read:assignments:children",
        "read:progress:children",
        "read:profile:children",
        "read:fees:children",
        "read:payments:children",
        "read:discipline:children",
        "read:schedule:children",
        "read:events:school",
        "read:kb:parent",
        "read:policies:public",
    },
    "teacher": {
        # Teacher sees their assigned classes' data + school info
        "read:attendance:class",
        "read:marks:class",
        "read:assignments:class",
        "read:progress:class",
        "read:profile:class",
        "read:discipline:class",
        "read:schedule:self",
        "read:schedule:class",
        "read:events:school",
        "read:kb:teacher",
        "read:policies:internal",
        # Explicitly NOT: fees (admin domain), HR data on other staff
    },
    "principal": {
        # Principal sees everything in their own school
        "read:attendance:school",
        "read:marks:school",
        "read:assignments:school",
        "read:progress:school",
        "read:profile:school",
        "read:discipline:school",
        "read:fees:school",
        "read:payments:school",
        "read:schedule:school",
        "read:events:school",
        "read:teacher_performance:school",
        "read:kb:admin",
        "read:policies:internal",
        # NOT cross-school
    },
    "admin": {
        # School admin (registrar/accounts/operations) — operational data
        "read:attendance:school",
        "read:profile:school",
        "read:fees:school",
        "read:payments:school",
        "read:schedule:school",
        "read:events:school",
        "read:kb:admin",
        "read:policies:internal",
        # NOT marks/discipline (academic, not operational)
    },
    "super_admin": {
        # Cross-school for the group of schools
        "read:attendance:all",
        "read:marks:all",
        "read:assignments:all",
        "read:progress:all",
        "read:profile:all",
        "read:discipline:all",
        "read:fees:all",
        "read:payments:all",
        "read:schedule:all",
        "read:events:all",
        "read:teacher_performance:all",
        "read:kb:admin",
        "read:policies:internal",
    },
}


def has_permission(role: Role, permission: str) -> bool:
    """Exact-match check. Use this for fine-grained gates."""
    return permission in PERMISSIONS.get(role, set())


def can_read(role: Role, resource: str, scope: str | None = None) -> bool:
    """Check if role can read `resource` at any scope (or specific scope)."""
    perms = PERMISSIONS.get(role, set())
    if scope:
        return f"read:{resource}:{scope}" in perms
    return any(p.startswith(f"read:{resource}:") for p in perms)


def allowed_scopes(role: Role, resource: str) -> Set[str]:
    """What scopes can this role read for this resource?"""
    perms = PERMISSIONS.get(role, set())
    prefix = f"read:{resource}:"
    return {p[len(prefix):] for p in perms if p.startswith(prefix)}


# ─────────────────────────────────────────────────────────────────────────────
# Auth context
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AuthContext:
    """The decoded JWT — passed through every request."""
    user_id: str
    school_id: str
    role: Role
    linked_id: Optional[str]    # student_id, teacher_id, parent_id, ...
    full_name: Optional[str] = None
    email: Optional[str] = None

    @property
    def is_super_admin(self) -> bool:
        return self.role == "super_admin"

    @property
    def is_school_scoped(self) -> bool:
        """Most roles only see one school."""
        return self.role != "super_admin"


# ─────────────────────────────────────────────────────────────────────────────
# SQL row-level scoping
# ─────────────────────────────────────────────────────────────────────────────
# These are SQL-fragment WHERE clauses we attach to the LLM-generated SQL
# to enforce row-level security. The fragments are OR-able with empty.

def school_scope_clause(ctx: AuthContext, table_alias: str = "") -> str:
    """Return a SQL fragment restricting rows to the user's school."""
    if ctx.is_super_admin:
        return ""
    col = f"{table_alias}.school_id" if table_alias else "school_id"
    return f"{col} = '{ctx.school_id}'"


def student_scope_clause(ctx: AuthContext, table_alias: str = "") -> str:
    """For student-level data — what student_ids can the user see?"""
    col_student = f"{table_alias}.student_id" if table_alias else "student_id"
    col_school = f"{table_alias}.school_id" if table_alias else "school_id"

    if ctx.role == "student":
        return f"{col_student} = '{ctx.linked_id}'"

    if ctx.role == "parent":
        # Parent → their children (via student_parent_map)
        return (
            f"{col_student} IN ("
            f"  SELECT student_id FROM student_parent_map "
            f"  WHERE parent_id = '{ctx.linked_id}' AND status = 'Active'"
            f")"
        )

    if ctx.role == "teacher":
        # Teacher → students in their assigned classes
        return (
            f"{col_student} IN ("
            f"  SELECT s.student_id FROM students s "
            f"  JOIN teacher_class_assignments tca "
            f"    ON s.school_id = tca.school_id "
            f"   AND s.grade_level = tca.grade_level "
            f"   AND s.section = tca.section "
            f"  WHERE tca.teacher_id = '{ctx.linked_id}' "
            f"    AND tca.status = 'Active'"
            f")"
        )

    if ctx.role in ("principal", "admin"):
        return f"{col_school} = '{ctx.school_id}'"

    if ctx.role == "super_admin":
        return ""

    # Unknown / restricted
    return "1 = 0"


# ─────────────────────────────────────────────────────────────────────────────
# Topic scoping — what TYPE of question can each role ask
# ─────────────────────────────────────────────────────────────────────────────

# Topics each role is allowed to ask about. Used by guardrails to refuse
# off-role questions BEFORE we even hit the LLM.

ROLE_TOPICS: Dict[Role, Set[str]] = {
    "student": {
        "attendance", "marks", "exam", "result", "homework", "assignment",
        "grade", "progress", "report", "schedule", "timetable", "subject",
        "teacher", "library", "event", "holiday", "kb", "policy", "explain",
        "study", "fee", "uniform", "lunch", "transport",
    },
    "parent": {
        "attendance", "marks", "exam", "result", "homework", "assignment",
        "grade", "progress", "report", "schedule", "timetable",
        "fee", "payment", "due", "outstanding", "receipt", "discipline",
        "behavior", "incident", "ptm", "meeting", "event", "holiday",
        "kb", "policy", "transport", "uniform", "child", "children",
    },
    "teacher": {
        "attendance", "marks", "exam", "homework", "assignment",
        "grade", "progress", "class", "student", "discipline", "behavior",
        "schedule", "timetable", "syllabus", "lesson", "report",
        "event", "kb", "policy", "subject", "professional",
    },
    "principal": {
        "attendance", "marks", "exam", "homework", "assignment",
        "grade", "progress", "class", "student", "discipline", "behavior",
        "fee", "payment", "due", "outstanding", "teacher", "performance",
        "school", "operations", "schedule", "event", "kb", "policy",
        "report", "audit", "compliance", "admission",
    },
    "admin": {
        "fee", "payment", "due", "outstanding", "receipt", "transport",
        "admission", "registration", "documentation", "schedule", "event",
        "kb", "policy", "operations", "facility",
    },
    "super_admin": {
        # Allowed across the board
        "*",
    },
}

# Topics explicitly forbidden per role (overrides allowed). Used to enforce
# negative permissions like "students cannot ask about salary/HR".

ROLE_FORBIDDEN_TOPICS: Dict[Role, Set[str]] = {
    "student": {"salary", "hr", "discipline_record", "other_student"},
    "parent": {"salary", "hr", "other_child", "teacher_personal"},
    "teacher": {"salary", "fee_collection", "other_teacher_hr"},
    "admin": {"marks", "exam", "discipline"},   # admin is not academic
    "principal": set(),
    "super_admin": set(),
}


def topic_allowed(role: Role, topic_keywords: Set[str]) -> tuple[bool, str | None]:
    """
    Returns (allowed, reason_if_blocked).
    `topic_keywords` is the set of keywords detected in the user's question.
    """
    forbidden = ROLE_FORBIDDEN_TOPICS.get(role, set())
    overlap = topic_keywords & forbidden
    if overlap:
        return False, f"role {role} cannot ask about {sorted(overlap)[0]}"

    allowed = ROLE_TOPICS.get(role, set())
    if "*" in allowed:
        return True, None
    if not topic_keywords:
        # No specific topic detected — allow general queries
        return True, None
    if topic_keywords & allowed:
        return True, None
    # No overlap with allowed topics
    return False, f"this question doesn't seem to be in scope for a {role}"


# ─────────────────────────────────────────────────────────────────────────────
# Tables visible per role (column-level allowlist for ERP connector)
# ─────────────────────────────────────────────────────────────────────────────

TABLES_BY_ROLE: Dict[Role, Set[str]] = {
    "student": {
        "students",
        "student_academic_records",
        "assignments", "assignment_submissions",
        "progress_reports",
        "attendance_log",
        "events", "schools",
        "teacher_class_assignments",   # for "who teaches my class"
    },
    "parent": {
        "students", "parents", "student_parent_map",
        "student_academic_records",
        "assignments", "assignment_submissions",
        "progress_reports",
        "attendance_log",
        "discipline_records",
        "payments",
        "events", "schools",
        "teacher_class_assignments",
    },
    "teacher": {
        "students",
        "student_academic_records",
        "assignments", "assignment_submissions",
        "progress_reports",
        "attendance_log",
        "discipline_records",
        "teachers",                     # self-info
        "teacher_class_assignments",
        "events", "schools",
    },
    "principal": {
        # Everything except cross-school
        "students", "parents", "teachers", "admins",
        "student_academic_records", "progress_reports",
        "assignments", "assignment_submissions",
        "discipline_records", "payments",
        "attendance_log", "events",
        "teacher_class_assignments",
        "schools",
    },
    "admin": {
        "students", "parents",
        "payments", "attendance_log", "events",
        "schools",
    },
    "super_admin": {
        "students", "parents", "teachers", "admins", "principals",
        "student_academic_records", "progress_reports",
        "assignments", "assignment_submissions",
        "discipline_records", "payments",
        "attendance_log", "events", "schools",
        "teacher_class_assignments", "student_parent_map",
        "users",
    },
}


def visible_tables(role: Role) -> Set[str]:
    return TABLES_BY_ROLE.get(role, set())
