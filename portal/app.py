from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

import boto3


OPS_TABLE_NAME = os.environ.get(
    "OPS_TABLE_NAME",
    "",
)

_ops_ddb = None

SHARE_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9_-]{24,80}$"
)


CLIENT_VISIBLE_VENDOR_STATUSES = {
    "ACTIVE",
    "PREFERRED",
}


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
            "referrer-policy":
                "no-referrer",
            "x-robots-tag":
                "noindex, nofollow, noarchive",
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


def _portal_share_partition_key(
    share_id: str,
) -> str:
    candidate = str(
        share_id or ""
    ).strip()

    if not SHARE_ID_PATTERN.fullmatch(
        candidate
    ):
        return ""

    digest = hashlib.sha256(
        candidate.encode("utf-8")
    ).hexdigest()

    return (
        "PORTAL#SHARE#"
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

    token_use = str(
        claims.get("token_use")
        or ""
    ).strip().lower()

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
        token_use != "id"
        or not email
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


def _safe_client_contact_email(
    value: Any,
) -> str:
    email = (
        str(value or "")
        .strip()
        .lower()
    )

    if (
        not email
        or not email.endswith(
            "@kasanecollective.com"
        )
    ):
        return ""

    return email


def _resolved_client_contact(
    project: dict[str, Any],
) -> dict[str, str]:
    project_id = str(
        project.get("projectId")
        or ""
    ).strip()

    user_id = str(
        project.get(
            "clientContactUserId"
        )
        or ""
    ).strip()

    role = str(
        project.get(
            "clientContactRole"
        )
        or ""
    ).strip()

    email = (
        _safe_client_contact_email(
            project.get(
                "clientContactEmail"
            )
        )
    )

    empty = {
        "userId": "",
        "name": "",
        "role": "",
        "email": "",
    }

    if (
        not project_id
        or not user_id
    ):
        return empty

    membership_result = (
        _ops_table().get_item(
            Key={
                "PK":
                    f"PROJECT#{project_id}",
                "SK":
                    f"MEMBER#{user_id}",
            },
            ConsistentRead=True,
        )
    )

    membership = (
        membership_result.get(
            "Item"
        )
    )

    if (
        not isinstance(
            membership,
            dict,
        )
        or membership.get(
            "recordType"
        )
        != "PROJECT_MEMBERSHIP"
        or str(
            membership.get(
                "membershipStatus"
            )
            or ""
        ).upper()
        != "ACTIVE"
    ):
        return empty

    staff_result = (
        _ops_table().get_item(
            Key={
                "PK":
                    f"USER#{user_id}",
                "SK":
                    "PROFILE",
            },
            ConsistentRead=True,
        )
    )

    staff = staff_result.get(
        "Item"
    )

    if (
        not isinstance(
            staff,
            dict,
        )
        or str(
            staff.get("status")
            or ""
        ).upper()
        != "ACTIVE"
    ):
        return empty

    return {
        "userId":
            user_id,
        "name":
            str(
                staff.get(
                    "displayName"
                )
                or ""
            ).strip(),
        "role":
            role,
        "email":
            email,
    }


def _public_client_project(
    item: dict[str, Any],
    *,
    resolve_contact: bool = False,
    resolve_vendors: bool = False,
) -> dict[str, Any]:
    contact = (
        _resolved_client_contact(
            item
        )
        if resolve_contact
        else {
            "userId": "",
            "name": "",
            "role": "",
            "email": "",
        }
    )

    vendors = (
        _client_visible_vendors(
            str(
                item.get("projectId")
                or ""
            )
        )
        if resolve_vendors
        else []
    )

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
        "createdAt": str(
            item.get("createdAt")
            or ""
        ),
        "updatedAt": str(
            item.get("updatedAt")
            or ""
        ),
        "clientContact":
            contact,
        "clientVendors":
            vendors,
        "musubiClientVisible": (
            item.get(
                "musubiClientVisible"
            )
            is True
        ),
        "musubiReviewStatus": str(
            item.get(
                "musubiReviewStatus"
            )
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


def _portal_share_record(
    share_id: str,
) -> dict[str, Any] | None:
    partition_key = (
        _portal_share_partition_key(
            share_id
        )
    )

    if not partition_key:
        return None

    result = _ops_table().get_item(
        Key={
            "PK": partition_key,
            "SK": "META",
        },
        ConsistentRead=True,
    )

    item = result.get("Item")

    if (
        not isinstance(item, dict)
        or item.get("recordType")
            != "PORTAL_SHARE"
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


def _client_visible_vendors(
    project_id: str,
) -> list[dict[str, str]]:
    if not project_id:
        return []

    response = _ops_table().query(
        KeyConditionExpression=(
            "PK = :pk AND "
            "begins_with(SK, :prefix)"
        ),
        ExpressionAttributeValues={
            ":pk":
                f"PROJECT#{project_id}",
            ":prefix":
                "VENDOR#",
        },
        ConsistentRead=True,
    )

    result = []

    for relation in (
        response.get("Items")
        or []
    ):
        if (
            not isinstance(
                relation,
                dict,
            )
            or relation.get(
                "recordType"
            )
                != "PROJECT_VENDOR"
            or str(
                relation.get(
                    "relationshipStatus"
                )
                or ""
            ).upper()
                != "ACTIVE"
            or relation.get(
                "clientVisible"
            )
                is not True
        ):
            continue

        vendor_id = str(
            relation.get("vendorId")
            or ""
        ).strip()

        if not vendor_id:
            continue

        vendor_result = (
            _ops_table().get_item(
                Key={
                    "PK":
                        f"VENDOR#{vendor_id}",
                    "SK":
                        "PROFILE",
                },
                ConsistentRead=True,
            )
        )

        vendor = vendor_result.get(
            "Item"
        )

        if (
            not isinstance(
                vendor,
                dict,
            )
            or vendor.get(
                "recordType"
            )
                != "VENDOR"
            or str(
                vendor.get("status")
                or "ACTIVE"
            ).upper()
                not in CLIENT_VISIBLE_VENDOR_STATUSES
        ):
            continue

        name = str(
            vendor.get("name")
            or ""
        ).strip()

        if not name:
            continue

        category = str(
            relation.get("category")
            or vendor.get("category")
            or ""
        ).strip()

        result.append(
            {
                "vendorId":
                    vendor_id,
                "name":
                    name,
                "category":
                    category,
            }
        )

    return sorted(
        result,
        key=lambda item: (
            item["category"],
            item["name"].casefold(),
            item["vendorId"],
        ),
    )


def _shared_project(
    share_id: str,
) -> dict[str, Any] | None:
    share = _portal_share_record(
        share_id
    )

    if not share:
        return None

    project_id = str(
        share.get("projectId")
        or ""
    ).strip()

    if not project_id:
        return None

    project = _project_record(
        project_id
    )

    if not project:
        return None

    if str(
        project.get("status")
        or ""
    ).strip().upper() != "ACTIVE":
        return None

    if str(
        project.get(
            "portalShareStatus"
        )
        or ""
    ).strip().upper() != "ACTIVE":
        return None

    current_share_id = str(
        project.get(
            "portalShareId"
        )
        or ""
    ).strip()

    if (
        not current_share_id
        or current_share_id
        != str(
            share_id or ""
        ).strip()
    ):
        return None

    return project


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
                project,
                resolve_contact=True,
            )
        )

    projects.sort(
        key=lambda item: (
            item.get("createdAt")
            or "",
            item.get("projectId")
            or "",
        ),
        reverse=True,
    )

    return projects


def handler(
    event: dict[str, Any],
    context: Any,
) -> dict[str, Any]:
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

    # ========================================================
    # PUBLIC-BY-LINK VIEW
    #
    # No Cognito is required to VIEW.
    # The share ID itself is an unguessable bearer capability.
    # ========================================================

    if (
        method == "GET"
        and "/v1/portal/share/"
            in path
    ):
        parameters = (
            event.get(
                "pathParameters"
            )
            or {}
        )

        share_id = str(
            parameters.get("shareId")
            or ""
        ).strip()

        # Always return the same 404 for an invalid,
        # revoked, disabled or nonexistent link.
        project = _shared_project(
            share_id
        )

        if not project:
            return _response(
                404,
                {
                    "error":
                        "portal_not_found"
                },
            )

        return _response(
            200,
            {
                "project":
                    _public_client_project(
                        project,
                        resolve_contact=True,
                        resolve_vendors=True,
                    )
            },
        )

    # ========================================================
    # VERIFIED CLIENT AREA
    #
    # Retained for future protected actions such as:
    # MUSUBI approval / request changes.
    # It is no longer the portal front door.
    # ========================================================

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
                        project,
                        resolve_contact=True,
                        resolve_vendors=True,
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
