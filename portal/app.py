from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import boto3


OPS_TABLE_NAME = os.environ.get(
    "OPS_TABLE_NAME",
    "",
)

_ops_ddb = None


def _ops_table():
    global _ops_ddb

    if not OPS_TABLE_NAME:
        raise RuntimeError(
            "OPS_TABLE_NAME is not configured"
        )

    if _ops_ddb is None:
        _ops_ddb = (
            boto3.resource("dynamodb")
            .Table(OPS_TABLE_NAME)
        )

    return _ops_ddb


def _response(
    status: int,
    body: dict[str, Any],
) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "content-type":
                "application/json; charset=utf-8",
            "cache-control":
                "no-store",
            "x-content-type-options":
                "nosniff",
        },
        "body": json.dumps(
            body,
            ensure_ascii=False,
        ),
    }


def _normalize_email(
    value: Any,
) -> str:
    return str(
        value or ""
    ).strip().lower()


def _client_partition_key(
    email: str,
) -> str:
    normalized = _normalize_email(
        email
    )

    if not normalized:
        raise ValueError(
            "client_email_required"
        )

    digest = hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()

    return (
        "CLIENT#EMAIL#"
        f"{digest}"
    )


def _client_identity(
    event: dict[str, Any],
) -> dict[str, str] | None:
    claims = (
        (
            (
                event
                .get("requestContext")
                or {}
            )
            .get("authorizer")
            or {}
        )
        .get("jwt")
        or {}
    ).get(
        "claims"
    ) or {}

    email = _normalize_email(
        claims.get("email")
    )

    verified = claims.get(
        "email_verified"
    )

    email_verified = (
        verified is True
        or str(
            verified
        ).strip().lower()
        == "true"
    )

    if (
        not email
        or not email_verified
    ):
        return None

    return {
        "subject": str(
            claims.get("sub")
            or ""
        ),
        "email": email,
    }


def _public_client_project(
    item: dict[str, Any],
) -> dict[str, Any]:
    return {
        "projectId": str(
            item.get("projectId")
            or ""
        ),
        "name": str(
            item.get("name")
            or ""
        ),
        "status": str(
            item.get("status")
            or ""
        ),
        "phase": str(
            item.get("phase")
            or ""
        ),
        "eventType": str(
            item.get("eventType")
            or ""
        ),
        "eventDate": str(
            item.get("eventDate")
            or ""
        ),
        "city": str(
            item.get("city")
            or ""
        ),
        "guests": str(
            item.get("guests")
            or ""
        ),
        "clientBrief": str(
            item.get("clientBrief")
            or ""
        ),
        "package": str(
            item.get("package")
            or ""
        ),
        "product": str(
            item.get("product")
            or ""
        ),
        "direction": str(
            item.get("direction")
            or ""
        ),
        "updatedAt": str(
            item.get("updatedAt")
            or ""
        ),
    }


def _client_access_record(
    email: str,
    project_id: str,
) -> dict[str, Any] | None:
    result = _ops_table().get_item(
        Key={
            "PK":
                _client_partition_key(
                    email
                ),
            "SK":
                f"PROJECT#{project_id}",
        },
        ConsistentRead=True,
    )

    item = result.get("Item")

    if (
        not isinstance(item, dict)
        or item.get("recordType")
            != "CLIENT_PROJECT_ACCESS"
        or str(
            item.get("status")
            or ""
        ).upper()
            != "ACTIVE"
    ):
        return None

    return item


def _project_record(
    project_id: str,
) -> dict[str, Any] | None:
    if (
        not project_id
        or not project_id.startswith(
            "KAS-"
        )
        or len(project_id) > 40
    ):
        return None

    result = _ops_table().get_item(
        Key={
            "PK":
                f"PROJECT#{project_id}",
            "SK":
                "META",
        },
        ConsistentRead=True,
    )

    item = result.get("Item")

    if (
        not isinstance(item, dict)
        or item.get("recordType")
            != "PROJECT"
    ):
        return None

    return item


def _list_client_access(
    email: str,
) -> list[dict[str, Any]]:
    result = _ops_table().query(
        KeyConditionExpression=(
            "PK = :pk AND "
            "begins_with(SK, :prefix)"
        ),
        ExpressionAttributeValues={
            ":pk":
                _client_partition_key(
                    email
                ),
            ":prefix":
                "PROJECT#",
        },
        ConsistentRead=True,
    )

    return [
        item
        for item in (
            result.get("Items")
            or []
        )
        if (
            isinstance(item, dict)
            and item.get(
                "recordType"
            )
            == "CLIENT_PROJECT_ACCESS"
            and str(
                item.get("status")
                or ""
            ).upper()
            == "ACTIVE"
        )
    ]


def _list_client_projects(
    email: str,
) -> list[dict[str, Any]]:
    projects = []

    for access in (
        _list_client_access(
            email
        )
    ):
        project_id = str(
            access.get("projectId")
            or ""
        )

        project = _project_record(
            project_id
        )

        if not project:
            continue

        projects.append(
            _public_client_project(
                project
            )
        )

    projects.sort(
        key=lambda item: (
            item.get("eventDate")
            or "9999-12-31",
            item.get("projectId")
            or "",
        )
    )

    return projects


def handler(
    event: dict[str, Any],
    context: Any,
) -> dict[str, Any]:
    identity = _client_identity(
        event
    )

    if not identity:
        return _response(
            401,
            {
                "error":
                    "client_auth_required"
            },
        )

    request_context = (
        event.get(
            "requestContext"
        )
        or {}
    )

    http = (
        request_context.get("http")
        or {}
    )

    method = str(
        http.get("method")
        or event.get("httpMethod")
        or ""
    ).upper()

    path = str(
        http.get("path")
        or event.get("rawPath")
        or event.get("path")
        or ""
    )

    if (
        method == "GET"
        and path.endswith(
            "/v1/client/me"
        )
    ):
        return _response(
            200,
            {
                "client": {
                    "email":
                        identity["email"],
                }
            },
        )

    if (
        method == "GET"
        and path.endswith(
            "/v1/client/projects"
        )
    ):
        return _response(
            200,
            {
                "projects":
                    _list_client_projects(
                        identity["email"]
                    )
            },
        )

    if (
        method == "GET"
        and "/v1/client/projects/"
            in path
    ):
        project_id = str(
            (
                event.get(
                    "pathParameters"
                )
                or {}
            ).get("projectId")
            or ""
        ).strip()

        if not project_id:
            return _response(
                400,
                {
                    "error":
                        "project_id_required"
                },
            )

        access = (
            _client_access_record(
                identity["email"],
                project_id,
            )
        )

        # Return 404 rather than revealing that
        # another client's project exists.
        if not access:
            return _response(
                404,
                {
                    "error":
                        "project_not_found"
                },
            )

        project = _project_record(
            project_id
        )

        if not project:
            return _response(
                404,
                {
                    "error":
                        "project_not_found"
                },
            )

        return _response(
            200,
            {
                "project":
                    _public_client_project(
                        project
                    )
            },
        )

    return _response(
        404,
        {
            "error":
                "not_found"
        },
    )
