from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


LOGGER = logging.getLogger()
LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO"))

STAGE = os.environ.get("STAGE", "dev")
OPS_TABLE_NAME = os.environ.get("OPS_TABLE_NAME", "")

ORGANIZATION_ROLES = (
    "OWNER",
    "MANAGER",
    "WORKER",
)

ROLE_PRECEDENCE = ORGANIZATION_ROLES

_ops_table_instance = None


def _response(
    status: int,
    body: dict[str, Any],
) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json; charset=utf-8",
            "cache-control": "no-store",
            "x-content-type-options": "nosniff",
        },
        "body": json.dumps(
            body,
            ensure_ascii=False,
        ),
    }


def _ops_table():
    global _ops_table_instance

    if not OPS_TABLE_NAME:
        raise RuntimeError(
            "ops_table_not_configured"
        )

    if _ops_table_instance is None:
        _ops_table_instance = (
            boto3.resource("dynamodb")
            .Table(OPS_TABLE_NAME)
        )

    return _ops_table_instance


def _staff_record(
    subject: str,
) -> dict[str, Any] | None:
    response = _ops_table().get_item(
        Key={
            "PK": f"USER#{subject}",
            "SK": "PROFILE",
        },
        ConsistentRead=True,
    )

    item = response.get("Item")

    if not isinstance(item, dict):
        return None

    return item


def _claims(
    event: dict[str, Any],
) -> dict[str, Any]:
    request_context = (
        event.get("requestContext")
        or {}
    )

    authorizer = (
        request_context.get("authorizer")
        or {}
    )

    jwt = (
        authorizer.get("jwt")
        or {}
    )

    claims = (
        jwt.get("claims")
        or {}
    )

    if not isinstance(claims, dict):
        return {}

    return claims


def _groups(
    claims: dict[str, Any],
) -> set[str]:
    raw = claims.get(
        "cognito:groups",
        [],
    )

    if isinstance(raw, list):
        return {
            str(value).strip()
            for value in raw
            if str(value).strip()
        }

    if not isinstance(raw, str):
        return set()

    value = raw.strip()

    if not value:
        return set()

    if value.startswith("["):
        try:
            parsed = json.loads(value)

            if isinstance(parsed, list):
                return {
                    str(item).strip()
                    for item in parsed
                    if str(item).strip()
                }

        except json.JSONDecodeError:
            pass

    if (
        value.startswith("[")
        and value.endswith("]")
    ):
        value = value[1:-1].strip()

    return {
        item.strip().strip("\"'")
        for item in value.split(",")
        if item.strip().strip("\"'")
    }


def _effective_role(
    groups: set[str],
) -> str | None:
    for role in ROLE_PRECEDENCE:
        if role in groups:
            return role

    return None


def handler(
    event: dict[str, Any],
    context: Any,
) -> dict[str, Any]:
    request_context = (
        event.get("requestContext")
        or {}
    )

    http = (
        request_context.get("http")
        or {}
    )

    method = (
        http.get("method")
        or event.get("httpMethod")
        or ""
    )

    path = (
        http.get("path")
        or event.get("rawPath")
        or event.get("path")
        or ""
    )

    if (
        method != "GET"
        or not path.endswith(
            "/v1/admin/me"
        )
    ):
        return _response(
            404,
            {"error": "not_found"},
        )

    claims = _claims(event)

    subject = str(
        claims.get("sub")
        or ""
    ).strip()

    if not subject:
        return _response(
            401,
            {"error": "unauthorized"},
        )

    token_use = str(
        claims.get("token_use")
        or ""
    ).strip()

    if token_use != "access":
        return _response(
            401,
            {"error": "invalid_token_type"},
        )

    identity_role = _effective_role(
        _groups(claims)
    )

    if not identity_role:
        return _response(
            403,
            {"error": "staff_role_required"},
        )

    try:
        staff = _staff_record(subject)

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ) as exc:
        LOGGER.exception(
            "Staff lookup failed type=%s",
            type(exc).__name__,
        )

        return _response(
            503,
            {"error": "temporarily_unavailable"},
        )

    if not staff:
        return _response(
            403,
            {"error": "staff_profile_required"},
        )

    status = str(
        staff.get("status")
        or ""
    ).strip().upper()

    if status != "ACTIVE":
        return _response(
            403,
            {"error": "staff_disabled"},
        )

    # OpsTable is authoritative for current organization role.
    role = str(
        staff.get("organizationRole")
        or ""
    ).strip().upper()

    if role not in ORGANIZATION_ROLES:
        return _response(
            403,
            {"error": "invalid_staff_role"},
        )

    try:
        authz_version = int(
            staff.get("authzVersion")
            or 1
        )
    except (TypeError, ValueError):
        authz_version = 1

    username = str(
        claims.get("username")
        or claims.get("cognito:username")
        or ""
    ).strip()

    return _response(
        200,
        {
            "ok": True,
            "stage": STAGE,
            "user": {
                "id": subject,
                "username": username,
                "displayName": str(
                    staff.get("displayName")
                    or ""
                ),
                "email": str(
                    staff.get("email")
                    or ""
                ),
                "role": role,
                "status": status,
                "authzVersion": authz_version,
                "preferredLocale": str(
                    staff.get("preferredLocale")
                    or "en"
                ),
            },
        },
    )
