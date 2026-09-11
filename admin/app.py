from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import BotoCoreError, ClientError


LOGGER = logging.getLogger()
LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO"))

STAGE = os.environ.get("STAGE", "dev")
OPS_TABLE_NAME = os.environ.get("OPS_TABLE_NAME", "")
LEADS_TABLE_NAME = os.environ.get("LEADS_TABLE_NAME", "")
STAFF_USER_POOL_ID = os.environ.get(
    "STAFF_USER_POOL_ID",
    "",
)

PREVIEW_TOKEN_SECRET_ARN = os.environ.get(
    "PREVIEW_TOKEN_SECRET_ARN",
    "",
).strip()

PREVIEW_BASE_URL = os.environ.get(
    "PREVIEW_BASE_URL",
    "",
).strip()

PREVIEW_TOKEN_TTL_SECONDS = 900

_preview_token_secret_value = None

ORGANIZATION_ROLES = (
    "OWNER",
    "MANAGER",
    "WORKER",
)

ROLE_PRECEDENCE = ORGANIZATION_ROLES

STAFF_STATUSES = (
    "ACTIVE",
    "DISABLED",
)

LEAD_STATUSES = (
    "NEW",
    "CONTACTED",
    "QUALIFIED",
    "PROPOSAL",
    "NEGOTIATION",
    "WON",
    "LOST",
    "ON_HOLD",
)

PROJECT_ROLES = (
    "PROJECT_LEAD",
    "COORDINATOR",
    "WORKER",
    "FINANCE",
    "VIEWER",
    "PRODUCTION",
    "CREATIVE",
    "LOGISTICS",
    "VENDOR_LIAISON",
)

PROJECT_STATUSES = (
    "ACTIVE",
    "COMPLETED",
    "CANCELLED",
    "ARCHIVED",
)


TASK_STATUSES = (
    "TODO",
    "IN_PROGRESS",
    "WAITING_BLOCKED",
    "DONE",
)

TASK_PRIORITIES = (
    "LOW",
    "NORMAL",
    "HIGH",
    "URGENT",
)

NOTE_CATEGORIES = (
    "GENERAL",
    "CUSTOMER_CONTACT",
    "VENDOR",
    "VENUE",
    "PRICING",
    "INTERNAL",
    "DECISION",
)

FOLLOW_UP_STATUSES = (
    "OPEN",
    "DONE",
    "CANCELED",
)

VENDOR_STATUSES = (
    "ACTIVE",
    "PREFERRED",
    "INACTIVE",
    "DO_NOT_USE",
)

VENDOR_CATEGORIES = (
    "VENUE",
    "CATERING",
    "DECORATION",
    "PHOTO_VIDEO",
    "ENTERTAINMENT",
    "MC",
    "MAKEUP",
    "ATTIRE",
    "INVITATION_STATIONERY",
    "CAKE_DESSERT",
    "FLORIST",
    "RENTAL",
    "LIGHTING_SOUND",
    "TRANSPORTATION",
    "ACCOMMODATION",
    "SECURITY",
    "GIFT_SOUVENIR",
    "CEREMONY",
    "OTHER",
)

PROJECT_VENDOR_OPERATIONAL_STATUSES = (
    "SHORTLISTED",
    "CONTACTED",
    "QUOTE_REQUESTED",
    "QUOTE_RECEIVED",
    "SELECTED",
    "CONFIRMED",
    "COMPLETED",
    "DECLINED",
)

PROJECT_VENDOR_BOOKING_STATUSES = (
    "NOT_STARTED",
    "PENDING",
    "CONFIRMED",
    "CANCELLED",
)

PROJECT_VENDOR_RELATIONSHIP_STATUSES = (
    "ACTIVE",
    "UNLINKED",
)



class LeadConversionConflict(RuntimeError):
    pass


class VendorWriteConflict(RuntimeError):
    pass


class ProjectVendorConflict(RuntimeError):
    def __init__(
        self,
        code: str,
    ):
        super().__init__(code)
        self.code = code


_serializer = TypeSerializer()

_ops_table_instance = None
_leads_table_instance = None
_cognito_client_instance = None


def _response(
    status: int,
    body: dict[str, Any],
) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "content-type":
                "application/json; charset=utf-8",
            "cache-control": "no-store",
            "x-content-type-options": "nosniff",
        },
        "body": json.dumps(
            body,
            ensure_ascii=False,
        ),
    }


def _utcnow() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
    )


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


def _leads_table():
    global _leads_table_instance

    if not LEADS_TABLE_NAME:
        raise RuntimeError(
            "leads_table_not_configured"
        )

    if _leads_table_instance is None:
        _leads_table_instance = (
            boto3.resource("dynamodb")
            .Table(LEADS_TABLE_NAME)
        )

    return _leads_table_instance


def _public_lead(
    item: dict[str, Any],
    *,
    detail: bool = False,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lead = {
        "reference": str(
            item.get("reference")
            or ""
        ),
        "createdAt": str(
            item.get("createdAt")
            or ""
        ),
        "language": str(
            item.get("language")
            or "en"
        ),
        "name": str(
            item.get("name")
            or ""
        ),
        "phone": str(
            item.get("phone")
            or ""
        ),
        "email": str(
            item.get("email")
            or ""
        ),
        "preferredContact": str(
            item.get("preferredContact")
            or ""
        ),
        "eventType": str(
            item.get("eventType")
            or ""
        ),
        "product": str(
            item.get("product")
            or ""
        ),
        "package": str(
            item.get("package")
            or ""
        ),
        "direction": str(
            item.get("direction")
            or ""
        ),
        "city": str(
            item.get("city")
            or ""
        ),
        "date": str(
            item.get("date")
            or ""
        ),
        "guests": str(
            item.get("guests")
            or ""
        ),
    }

    state = state or {}

    lead["pipelineStatus"] = str(
        state.get("status")
        or "NEW"
    )

    lead["convertedProjectId"] = str(
        state.get("convertedProjectId")
        or ""
    )

    lead["pipelineUpdatedAt"] = str(
        state.get("updatedAt")
        or ""
    )

    if detail:
        lead["message"] = str(
            item.get("message")
            or ""
        )

        lead["page"] = str(
            item.get("page")
            or ""
        )

    return lead


def _list_leads(
    limit: int = 50,
) -> list[dict[str, Any]]:
    response = _leads_table().query(
        IndexName="LeadCreatedAtIndex",
        KeyConditionExpression=(
            "LeadIndexPK = :pk"
        ),
        ExpressionAttributeValues={
            ":pk": "LEADS",
        },
        ScanIndexForward=False,
        Limit=limit,
    )

    items = response.get("Items") or []

    return [
        item
        for item in items
        if (
            isinstance(item, dict)
            and item.get("recordType")
                == "EVENT_BRIEF"
        )
    ]


def _lead_record(
    reference: str,
) -> dict[str, Any] | None:
    if (
        not reference
        or not reference.startswith("KAS-")
        or len(reference) > 80
    ):
        return None

    response = _leads_table().get_item(
        Key={
            "reference": reference,
        },
        ConsistentRead=True,
    )

    item = response.get("Item")

    if (
        not isinstance(item, dict)
        or item.get("recordType")
            != "EVENT_BRIEF"
    ):
        return None

    return item


def _serialize_map(
    value: dict[str, Any],
) -> dict[str, Any]:
    return {
        key: _serializer.serialize(item)
        for key, item in value.items()
    }


def _lead_state(
    reference: str,
) -> dict[str, Any] | None:
    response = _ops_table().get_item(
        Key={
            "PK": f"LEAD#{reference}",
            "SK": "STATE",
        },
        ConsistentRead=True,
    )

    item = response.get("Item")

    if not isinstance(item, dict):
        return None

    return item


def _lead_states(
    references: list[str],
) -> dict[str, dict[str, Any]]:
    unique = list(dict.fromkeys(
        reference
        for reference in references
        if reference
    ))

    if not unique:
        return {}

    request = {
        OPS_TABLE_NAME: {
            "Keys": [
                {
                    "PK": f"LEAD#{reference}",
                    "SK": "STATE",
                }
                for reference in unique
            ],
            "ConsistentRead": True,
        }
    }

    items: list[dict[str, Any]] = []
    dynamodb = boto3.resource("dynamodb")

    for _ in range(4):
        response = dynamodb.batch_get_item(
            RequestItems=request
        )

        items.extend(
            response
            .get("Responses", {})
            .get(OPS_TABLE_NAME, [])
        )

        unprocessed = (
            response.get("UnprocessedKeys")
            or {}
        )

        if not unprocessed:
            break

        request = unprocessed
    else:
        raise RuntimeError(
            "lead_state_batch_incomplete"
        )

    result: dict[str, dict[str, Any]] = {}

    for item in items:
        reference = str(
            item.get("leadReference")
            or ""
        )

        if not reference:
            pk = str(item.get("PK") or "")

            if pk.startswith("LEAD#"):
                reference = pk[5:]

        if reference:
            result[reference] = item

    return result


def _set_lead_status(
    reference: str,
    status: str,
    actor_subject: str,
) -> dict[str, Any]:
    now = _utcnow()

    kwargs: dict[str, Any] = {
        "Key": {
            "PK": f"LEAD#{reference}",
            "SK": "STATE",
        },
        "UpdateExpression": (
            "SET "
            "recordType = if_not_exists("
            "recordType, :record_type), "
            "leadReference = if_not_exists("
            "leadReference, :reference), "
            "#status = :status, "
            "createdAt = if_not_exists("
            "createdAt, :now), "
            "createdBy = if_not_exists("
            "createdBy, :actor), "
            "updatedAt = :now, "
            "updatedBy = :actor, "
            "GSI3PK = :gsi_pk, "
            "GSI3SK = :gsi_sk"
        ),
        "ExpressionAttributeNames": {
            "#status": "status",
        },
        "ExpressionAttributeValues": {
            ":record_type": "LEAD_STATE",
            ":reference": reference,
            ":status": status,
            ":now": now,
            ":actor": actor_subject,
            ":gsi_pk":
                f"LEADS#STATUS#{status}",
            ":gsi_sk":
                f"UPDATED#{now}#LEAD#{reference}",
        },
        "ReturnValues": "ALL_NEW",
    }

    if status != "WON":
        kwargs["ConditionExpression"] = (
            "attribute_not_exists("
            "convertedProjectId)"
        )

    response = _ops_table().update_item(
        **kwargs
    )

    return response["Attributes"]


def _next_project_id() -> str:
    response = _ops_table().update_item(
        Key={
            "PK": "SYSTEM#COUNTERS",
            "SK": "PROJECT",
        },
        UpdateExpression=(
            "SET "
            "recordType = if_not_exists("
            "recordType, :record_type), "
            "updatedAt = :updated "
            "ADD nextValue :one"
        ),
        ExpressionAttributeValues={
            ":record_type": "COUNTER",
            ":updated": _utcnow(),
            ":one": 1,
        },
        ReturnValues="ALL_NEW",
    )

    number = int(
        response["Attributes"]["nextValue"]
    )

    return f"KAS-{number:03d}"


PROJECT_COLORS = (
    "RUST",
    "BLUE",
    "OLIVE",
    "GOLD",
    "PLUM",
    "TEAL",
    "ROSE",
    "STONE",
)


def _normalize_project_color(
    value: Any,
) -> str:
    color = str(
        value or ""
    ).strip().upper()

    if color not in PROJECT_COLORS:
        return ""

    return color


def _default_project_color(
    project_id: str,
) -> str:
    suffix = str(
        project_id or ""
    ).rsplit("-", 1)[-1]

    try:
        number = int(suffix)
    except ValueError:
        number = 1

    index = (
        max(number, 1) - 1
    ) % len(PROJECT_COLORS)

    return PROJECT_COLORS[index]


def _project_color(
    item: dict[str, Any],
) -> str:
    stored = _normalize_project_color(
        item.get("projectColor")
    )

    if stored:
        return stored

    return _default_project_color(
        str(
            item.get("projectId")
            or ""
        )
    )


def _public_project(
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
        "projectColor":
            _project_color(item),
        "activeMemberUserIds": [
            str(user_id)
            for user_id in (
                item.get(
                    "activeMemberUserIds"
                )
                or []
            )
            if str(user_id).strip()
        ],
        "activeMemberCount": int(
            item.get("activeMemberCount")
            or 0
        ),
        "projectLeadUserIds": [
            str(user_id)
            for user_id in (
                item.get(
                    "projectLeadUserIds"
                )
                or []
            )
            if str(user_id).strip()
        ],
        "leadReference": str(
            item.get("leadReference")
            or ""
        ),
        "clientName": str(
            item.get("clientName")
            or ""
        ),
        "email": str(
            item.get("email")
            or ""
        ),
        "phone": str(
            item.get("phone")
            or ""
        ),
        "preferredContact": str(
            item.get("preferredContact")
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
        "createdAt": str(
            item.get("createdAt")
            or ""
        ),
        "updatedAt": str(
            item.get("updatedAt")
            or ""
        ),
        "lastActivityAt": str(
            item.get("lastActivityAt")
            or item.get("updatedAt")
            or ""
        ),
        "lastActivityBy": str(
            item.get("lastActivityBy")
            or item.get("updatedBy")
            or ""
        ),
        "completedAt": str(
            item.get("completedAt")
            or ""
        ),
        "completedBy": str(
            item.get("completedBy")
            or ""
        ),
        "completionNote": str(
            item.get("completionNote")
            or ""
        ),
        "cancelledAt": str(
            item.get("cancelledAt")
            or ""
        ),
        "cancelledBy": str(
            item.get("cancelledBy")
            or ""
        ),
        "cancellationReason": str(
            item.get("cancellationReason")
            or ""
        ),
        "archivedAt": str(
            item.get("archivedAt")
            or ""
        ),
        "archivedBy": str(
            item.get("archivedBy")
            or ""
        ),
        "restoredAt": str(
            item.get("restoredAt")
            or ""
        ),
        "restoredBy": str(
            item.get("restoredBy")
            or ""
        ),
        "reopenedAt": str(
            item.get("reopenedAt")
            or ""
        ),
        "reopenedBy": str(
            item.get("reopenedBy")
            or ""
        ),
        "reopenReason": str(
            item.get("reopenReason")
            or ""
        ),
    }


def _update_project_color(
    project_id: str,
    color: str,
    actor_subject: str,
) -> dict[str, Any]:
    now = _utcnow()

    response = _ops_table().update_item(
        Key={
            "PK":
                f"PROJECT#{project_id}",
            "SK":
                "META",
        },
        UpdateExpression=(
            "SET "
            "projectColor = :color, "
            "updatedAt = :updated, "
            "updatedBy = :actor"
        ),
        ConditionExpression=(
            "attribute_exists(PK) "
            "AND attribute_exists(SK) "
            "AND recordType = :record_type"
        ),
        ExpressionAttributeValues={
            ":color":
                color,
            ":updated":
                now,
            ":actor":
                actor_subject,
            ":record_type":
                "PROJECT",
        },
        ReturnValues="ALL_NEW",
    )

    updated = response["Attributes"]

    _record_activity(
        project_id,
        actor_subject,
        "PROJECT_COLOR_CHANGED",
        (
            "Changed project color "
            f"to {color.lower()}"
        ),
        {
            "projectColor":
                color,
        },
    )

    return updated


def _handle_update_project_color(
    event: dict[str, Any],
    actor_subject: str,
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
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

    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {"error": "invalid_json"},
        )

    color = _normalize_project_color(
        body.get("color")
    )

    if not color:
        return _response(
            400,
            {
                "error":
                    "invalid_project_color",
                "allowed":
                    list(PROJECT_COLORS),
            },
        )

    try:
        updated = _update_project_color(
            project_id,
            color,
            actor_subject,
        )

    except ClientError as exc:
        code = str(
            exc.response.get(
                "Error",
                {}
            ).get(
                "Code",
                ""
            )
        )

        if (
            code
            == "ConditionalCheckFailedException"
        ):
            return _response(
                404,
                {
                    "error":
                        "project_not_found"
                },
            )

        LOGGER.exception(
            "Failed to update project color"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    except (
        BotoCoreError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to update project color"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "project":
                _public_project(updated)
        },
    )


PROJECT_SCOPE_FIELDS = (
    "package",
    "product",
    "direction",
)


def _project_scope_changes(
    body: dict[str, Any],
) -> dict[str, str]:
    changes: dict[str, str] = {}

    for field in PROJECT_SCOPE_FIELDS:
        if field not in body:
            continue

        value = " ".join(
            str(
                body.get(field)
                or ""
            ).split()
        )

        if len(value) > 180:
            raise ValueError(
                f"{field}_too_long"
            )

        changes[field] = value

    if not changes:
        raise ValueError(
            "scope_fields_required"
        )

    return changes


def _update_project_scope(
    current: dict[str, Any],
    changes: dict[str, str],
    actor_subject: str,
) -> tuple[dict[str, Any], bool]:
    changed_fields = [
        field
        for field, value in changes.items()
        if str(
            current.get(field)
            or ""
        ) != value
    ]

    if not changed_fields:
        return current, False

    project_id = str(
        current.get("projectId")
        or ""
    )

    now = _utcnow()

    names = {
        "#recordType": "recordType",
    }

    values: dict[str, Any] = {
        ":project_type": "PROJECT",
        ":updated": now,
        ":actor": actor_subject,
    }

    set_parts = [
        "updatedAt = :updated",
        "updatedBy = :actor",
    ]

    remove_parts: list[str] = []

    for index, field in enumerate(
        changed_fields
    ):
        name_key = f"#scope{index}"
        value_key = f":scope{index}"

        names[name_key] = field

        value = changes[field]

        if value:
            values[value_key] = value
            set_parts.append(
                f"{name_key} = {value_key}"
            )
        else:
            remove_parts.append(
                name_key
            )

    expression = (
        "SET " + ", ".join(set_parts)
    )

    if remove_parts:
        expression += (
            " REMOVE "
            + ", ".join(remove_parts)
        )

    response = _ops_table().update_item(
        Key={
            "PK":
                f"PROJECT#{project_id}",
            "SK":
                "META",
        },
        UpdateExpression=expression,
        ConditionExpression=(
            "attribute_exists(PK) "
            "AND attribute_exists(SK) "
            "AND #recordType = :project_type"
        ),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ReturnValues="ALL_NEW",
    )

    updated = response["Attributes"]

    public = _public_project(updated)

    _record_activity(
        project_id,
        actor_subject,
        "PROJECT_SCOPE_UPDATED",
        "Updated project scope",
        {
            "changedFields":
                changed_fields,
            "package":
                public["package"],
            "product":
                public["product"],
            "direction":
                public["direction"],
        },
    )

    return updated, True


def _handle_update_project_scope(
    event: dict[str, Any],
    identity: dict[str, Any],
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
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

    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {"error": "invalid_json"},
        )

    try:
        changes = (
            _project_scope_changes(body)
        )
    except ValueError as exc:
        return _response(
            400,
            {"error": str(exc)},
        )

    try:
        current = _project_record(
            project_id
        )

        if not current:
            return _response(
                404,
                {
                    "error":
                        "project_not_found"
                },
            )

        updated, changed = (
            _update_project_scope(
                current,
                changes,
                identity["subject"],
            )
        )

    except ClientError as exc:
        if (
            _aws_error_code(exc)
            ==
            "ConditionalCheckFailedException"
        ):
            return _response(
                404,
                {
                    "error":
                        "project_not_found"
                },
            )

        LOGGER.exception(
            "Project scope update failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    except (
        BotoCoreError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Project scope update failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "project":
                _public_project(updated),
            "changed":
                changed,
        },
    )


def _project_record(
    project_id: str,
) -> dict[str, Any] | None:
    if (
        not project_id
        or not project_id.startswith("KAS-")
        or len(project_id) > 40
    ):
        return None

    response = _ops_table().get_item(
        Key={
            "PK": f"PROJECT#{project_id}",
            "SK": "META",
        },
        ConsistentRead=True,
    )

    item = response.get("Item")

    if (
        not isinstance(item, dict)
        or item.get("recordType")
            != "PROJECT"
    ):
        return None

    return item


def _list_projects(
    limit: int = 100,
) -> list[dict[str, Any]]:
    response = _ops_table().query(
        IndexName="GSI3",
        KeyConditionExpression=(
            "GSI3PK = :pk"
        ),
        ExpressionAttributeValues={
            ":pk": "PROJECTS",
        },
        ScanIndexForward=True,
        Limit=limit,
    )

    return [
        item
        for item in (
            response.get("Items")
            or []
        )
        if (
            isinstance(item, dict)
            and item.get("recordType")
                == "PROJECT"
        )
    ]


class ProjectLifecycleConflict(Exception):
    def __init__(
        self,
        code: str,
    ):
        super().__init__(code)
        self.code = code


def _can_view_project(
    identity: dict[str, Any],
    project: dict[str, Any],
) -> bool:
    if identity["role"] in {
        "OWNER",
        "MANAGER",
    }:
        return True

    project_id = str(
        project.get("projectId")
        or ""
    )

    subject = str(
        identity.get("subject")
        or ""
    )

    if not project_id or not subject:
        return False

    membership = _project_member_record(
        project_id,
        subject,
    )

    if not membership:
        return False

    status = str(
        project.get("status")
        or "ACTIVE"
    )

    membership_status = str(
        membership.get(
            "membershipStatus"
        )
        or ""
    )

    if status == "ARCHIVED":
        return True

    return membership_status == "ACTIVE"


def _project_read_access_error(
    event: dict[str, Any],
    identity: dict[str, Any],
):
    if identity["role"] in {
        "OWNER",
        "MANAGER",
    }:
        return None

    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
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

    try:
        project = _project_record(
            project_id
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to authorize "
            "project read access"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    if not project:
        return _response(
            404,
            {
                "error":
                    "project_not_found"
            },
        )

    if not _can_view_project(
        identity,
        project,
    ):
        return _response(
            403,
            {
                "error":
                    "project_access_required"
            },
        )

    return None


def _can_complete_project(
    identity: dict[str, Any],
    project: dict[str, Any],
) -> bool:
    if identity["role"] in {
        "OWNER",
        "MANAGER",
    }:
        return True

    project_id = str(
        project.get("projectId")
        or ""
    )

    subject = str(
        identity.get("subject")
        or ""
    )

    if not project_id or not subject:
        return False

    membership = _project_member_record(
        project_id,
        subject,
    )

    if not membership:
        return False

    return (
        membership.get(
            "membershipStatus"
        )
        == "ACTIVE"
        and membership.get(
            "projectRole"
        )
        == "PROJECT_LEAD"
    )


def _project_status_sort_key(
    project: dict[str, Any],
    status: str,
) -> str:
    event_date = str(
        project.get("eventDate")
        or ""
    ).strip()

    project_id = str(
        project.get("projectId")
        or ""
    )

    return (
        f"STATUS#{status}"
        f"#DATE#{event_date or '9999-12-31'}"
        f"#PROJECT#{project_id}"
    )


def _project_open_work_summary(
    project_id: str,
) -> dict[str, int]:
    tasks = _list_project_children(
        project_id,
        "TASK#",
        "TASK",
    )

    follow_ups = _list_project_children(
        project_id,
        "FOLLOWUP#",
        "FOLLOW_UP",
    )

    open_tasks = sum(
        1
        for item in tasks
        if str(
            item.get("status")
            or "TODO"
        )
        != "DONE"
    )

    open_follow_ups = sum(
        1
        for item in follow_ups
        if str(
            item.get("status")
            or "OPEN"
        )
        == "OPEN"
    )

    return {
        "openTasks":
            open_tasks,
        "openFollowUps":
            open_follow_ups,
    }


def _lifecycle_target_status(
    current_status: str,
    action: str,
    pre_archive_status: str = "",
) -> str:
    if (
        action == "complete"
        and current_status == "ACTIVE"
    ):
        return "COMPLETED"

    if (
        action == "cancel"
        and current_status == "ACTIVE"
    ):
        return "CANCELLED"

    if (
        action == "reopen"
        and current_status == "COMPLETED"
    ):
        return "ACTIVE"

    if (
        action == "archive"
        and current_status in {
            "COMPLETED",
            "CANCELLED",
        }
    ):
        return "ARCHIVED"

    if (
        action == "restore"
        and current_status == "ARCHIVED"
    ):
        if pre_archive_status in {
            "COMPLETED",
            "CANCELLED",
        }:
            return pre_archive_status

        return "COMPLETED"

    raise ProjectLifecycleConflict(
        "invalid_project_transition"
    )


def _transition_project(
    current: dict[str, Any],
    action: str,
    actor_subject: str,
    note: str = "",
) -> dict[str, Any]:
    project_id = str(
        current.get("projectId")
        or ""
    )

    current_status = str(
        current.get("status")
        or "ACTIVE"
    )

    target_status = (
        _lifecycle_target_status(
            current_status,
            action,
            str(
                current.get(
                    "preArchiveStatus"
                )
                or ""
            ),
        )
    )

    now = _utcnow()

    names = {
        "#status": "status",
    }

    values: dict[str, Any] = {
        ":new_status":
            target_status,
        ":expected_status":
            current_status,
        ":updated":
            now,
        ":actor":
            actor_subject,
        ":project_type":
            "PROJECT",
        ":gsi":
            _project_status_sort_key(
                current,
                target_status,
            ),
    }

    set_parts = [
        "#status = :new_status",
        "updatedAt = :updated",
        "updatedBy = :actor",
        "GSI3SK = :gsi",
    ]

    remove_parts: list[str] = []

    activity_type = ""
    summary = ""
    metadata: dict[str, Any] = {
        "previousStatus":
            current_status,
        "status":
            target_status,
    }

    if action == "complete":
        values[":completed"] = now
        values[":note"] = note

        set_parts.extend([
            "completedAt = :completed",
            "completedBy = :actor",
            "completionNote = :note",
        ])

        activity_type = (
            "PROJECT_COMPLETED"
        )

        summary = "Completed project"

        metadata["completionNote"] = (
            note
        )

    elif action == "reopen":
        values[":reopened"] = now
        values[":reason"] = note

        set_parts.extend([
            "reopenedAt = :reopened",
            "reopenedBy = :actor",
            "reopenReason = :reason",
        ])

        remove_parts.extend([
            "completedAt",
            "completedBy",
            "completionNote",
        ])

        activity_type = (
            "PROJECT_REOPENED"
        )

        summary = "Reopened project"

        metadata["reason"] = note

    elif action == "cancel":
        values[":cancelled"] = now
        values[":reason"] = note

        set_parts.extend([
            "cancelledAt = :cancelled",
            "cancelledBy = :actor",
            "cancellationReason = :reason",
        ])

        activity_type = (
            "PROJECT_CANCELLED"
        )

        summary = "Cancelled project"

        metadata["reason"] = note

    elif action == "archive":
        values[":archived"] = now
        values[":pre_archive"] = (
            current_status
        )

        set_parts.extend([
            "archivedAt = :archived",
            "archivedBy = :actor",
            "preArchiveStatus = :pre_archive",
        ])

        activity_type = (
            "PROJECT_ARCHIVED"
        )

        summary = "Archived project"

        if note:
            metadata["note"] = note

    elif action == "restore":
        values[":restored"] = now

        set_parts.extend([
            "restoredAt = :restored",
            "restoredBy = :actor",
        ])

        remove_parts.append(
            "preArchiveStatus"
        )

        activity_type = (
            "PROJECT_RESTORED"
        )

        summary = "Restored project"

    update_expression = (
        "SET "
        + ", ".join(set_parts)
    )

    if remove_parts:
        update_expression += (
            " REMOVE "
            + ", ".join(remove_parts)
        )

    activity_id = _new_record_id(
        "ACT"
    )

    activity_item = {
        "PK":
            f"PROJECT#{project_id}",
        "SK":
            (
                f"ACTIVITY#{now}"
                f"#{activity_id}"
            ),
        "recordType":
            "ACTIVITY",
        "activityId":
            activity_id,
        "projectId":
            project_id,
        "activityType":
            activity_type,
        "summary":
            summary,
        "actorUserId":
            actor_subject,
        "metadata":
            metadata,
        "createdAt":
            now,
    }

    boto3.client(
        "dynamodb"
    ).transact_write_items(
        TransactItems=[
            {
                "Update": {
                    "TableName":
                        OPS_TABLE_NAME,
                    "Key":
                        _serialize_map({
                            "PK":
                                f"PROJECT#{project_id}",
                            "SK":
                                "META",
                        }),
                    "UpdateExpression":
                        update_expression,
                    "ConditionExpression": (
                        "attribute_exists(PK) "
                        "AND recordType = "
                        ":project_type "
                        "AND #status = "
                        ":expected_status"
                    ),
                    "ExpressionAttributeNames":
                        names,
                    "ExpressionAttributeValues":
                        _serialize_map(
                            values
                        ),
                }
            },
            {
                "Put": {
                    "TableName":
                        OPS_TABLE_NAME,
                    "Item":
                        _serialize_map(
                            activity_item
                        ),
                    "ConditionExpression": (
                        "attribute_not_exists(PK) "
                        "AND "
                        "attribute_not_exists(SK)"
                    ),
                }
            },
        ]
    )

    updated = _project_record(
        project_id
    )

    if not updated:
        raise RuntimeError(
            "project_missing_after_transition"
        )

    return updated


def _optional_request_body(
    event: dict[str, Any],
) -> dict[str, Any] | None:
    raw = event.get("body")

    if raw in {
        None,
        "",
    }:
        return {}

    return _request_body(event)


def _handle_project_lifecycle(
    event: dict[str, Any],
    identity: dict[str, Any],
    action: str,
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
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

    body = _optional_request_body(
        event
    )

    if body is None:
        return _response(
            400,
            {"error": "invalid_json"},
        )

    try:
        current = _project_record(
            project_id
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to read project "
            "for lifecycle transition"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    if not current:
        return _response(
            404,
            {
                "error":
                    "project_not_found"
            },
        )

    if action == "complete":
        if not _can_complete_project(
            identity,
            current,
        ):
            return _response(
                403,
                {
                    "error":
                        "project_complete_forbidden"
                },
            )

    elif identity["role"] not in {
        "OWNER",
        "MANAGER",
    }:
        return _response(
            403,
            {
                "error":
                    "manager_or_owner_required"
            },
        )

    note = str(
        body.get("note")
        or body.get("reason")
        or ""
    ).strip()

    if len(note) > 2000:
        return _response(
            400,
            {
                "error":
                    "lifecycle_note_too_long"
            },
        )

    if (
        action in {
            "cancel",
            "reopen",
        }
        and not note
    ):
        return _response(
            400,
            {
                "error":
                    "reason_required"
            },
        )

    if action == "complete":
        try:
            open_work = (
                _project_open_work_summary(
                    project_id
                )
            )

        except (
            BotoCoreError,
            ClientError,
            RuntimeError,
        ):
            LOGGER.exception(
                "Failed to inspect "
                "project open work"
            )

            return _response(
                503,
                {
                    "error":
                        "temporarily_unavailable"
                },
            )

        force_requested = (
            body.get("force")
            is True
        )

        can_force = (
            identity["role"]
            in {
                "OWNER",
                "MANAGER",
            }
        )

        if (
            force_requested
            and not can_force
        ):
            return _response(
                403,
                {
                    "error":
                        "project_force_complete_forbidden"
                },
            )

        force = (
            force_requested
            and can_force
        )

        has_open_work = (
            open_work["openTasks"] > 0
            or open_work[
                "openFollowUps"
            ] > 0
        )

        if (
            has_open_work
            and force
            and not note
        ):
            return _response(
                400,
                {
                    "error":
                        "completion_note_required"
                },
            )

        if (
            has_open_work
            and not force
        ):
            return _response(
                409,
                {
                    "error":
                        "open_work_remaining",
                    **open_work,
                },
            )

    if (
        action == "archive"
        and str(
            current.get("status")
            or ""
        )
        == "COMPLETED"
    ):
        try:
            archive_work = (
                _project_open_work_summary(
                    project_id
                )
            )

        except (
            BotoCoreError,
            ClientError,
            RuntimeError,
        ):
            LOGGER.exception(
                "Failed to inspect "
                "project work before archive"
            )

            return _response(
                503,
                {
                    "error":
                        "temporarily_unavailable"
                },
            )

        archive_has_open_work = (
            archive_work["openTasks"] > 0
            or archive_work[
                "openFollowUps"
            ] > 0
        )

        archive_force = (
            body.get("force")
            is True
        )

        if (
            archive_has_open_work
            and not archive_force
        ):
            return _response(
                409,
                {
                    "error":
                        "open_work_remaining",
                    **archive_work,
                },
            )

        if (
            archive_has_open_work
            and archive_force
            and not note
        ):
            return _response(
                400,
                {
                    "error":
                        "archive_note_required"
                },
            )

    try:
        updated = _transition_project(
            current,
            action,
            identity["subject"],
            note,
        )

    except ProjectLifecycleConflict as exc:
        return _response(
            409,
            {
                "error":
                    exc.code,
                "currentStatus":
                    str(
                        current.get("status")
                        or ""
                    ),
                "action":
                    action,
            },
        )

    except ClientError as exc:
        code = str(
            exc.response.get(
                "Error",
                {}
            ).get(
                "Code",
                ""
            )
        )

        if code in {
            "ConditionalCheckFailedException",
            "TransactionCanceledException",
        }:
            return _response(
                409,
                {
                    "error":
                        "project_state_changed"
                },
            )

        LOGGER.exception(
            "Project lifecycle update failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    except (
        BotoCoreError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Project lifecycle update failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "project":
                _public_project(updated)
        },
    )


def _project_client_brief_from_lead(
    lead: dict[str, Any],
) -> str:
    return str(
        lead.get("message")
        or ""
    )


def _project_scope_from_lead(
    lead: dict[str, Any],
) -> dict[str, str]:
    return {
        "package": str(
            lead.get("package")
            or ""
        ).strip(),
        "product": str(
            lead.get("product")
            or ""
        ).strip(),
        "direction": str(
            lead.get("direction")
            or ""
        ).strip(),
    }


def _convert_lead(
    lead: dict[str, Any],
    actor_subject: str,
) -> tuple[dict[str, Any], bool]:
    reference = str(
        lead.get("reference")
        or ""
    )

    existing_state = _lead_state(
        reference
    )

    if existing_state:
        existing_project_id = str(
            existing_state.get(
                "convertedProjectId"
            )
            or ""
        )

        if existing_project_id:
            existing_project = (
                _project_record(
                    existing_project_id
                )
            )

            if not existing_project:
                raise RuntimeError(
                    "converted_project_missing"
                )

            return existing_project, False

        if (
            str(
                existing_state.get("status")
                or ""
            ).upper()
            == "LOST"
        ):
            raise LeadConversionConflict(
                "lead_marked_lost"
            )

    client_name = str(
        lead.get("name")
        or "Untitled client"
    ).strip()

    event_type = str(
        lead.get("eventType")
        or ""
    ).strip()

    project_name = (
        f"{client_name} · {event_type}"
        if event_type
        else client_name
    )

    for _ in range(4):
        project_id = _next_project_id()
        now = _utcnow()

        event_date = str(
            lead.get("date")
            or ""
        ).strip()

        project = {
            "PK":
                f"PROJECT#{project_id}",
            "SK": "META",
            "recordType": "PROJECT",
            "projectId": project_id,
            "name": project_name,
            "status": "ACTIVE",
            "phase": "PLANNING",
            "projectColor":
                _default_project_color(
                    project_id
                ),
            "leadReference": reference,
            "clientName": client_name,
            "email": str(
                lead.get("email")
                or ""
            ),
            "phone": str(
                lead.get("phone")
                or ""
            ),
            "preferredContact": str(
                lead.get("preferredContact")
                or ""
            ),
            "clientBrief":
                _project_client_brief_from_lead(
                    lead
                ),
            **_project_scope_from_lead(
                lead
            ),
            "eventType": event_type,
            "eventDate": event_date,
            "city": str(
                lead.get("city")
                or ""
            ),
            "guests": str(
                lead.get("guests")
                or ""
            ),
            "createdAt": now,
            "createdBy": actor_subject,
            "updatedAt": now,
            "updatedBy": actor_subject,
            "lastActivityAt": now,
            "lastActivityBy": actor_subject,
            "GSI3PK": "PROJECTS",
            "GSI3SK": (
                "STATUS#ACTIVE"
                f"#DATE#{event_date or '9999-12-31'}"
                f"#PROJECT#{project_id}"
            ),
        }

        try:
            boto3.client(
                "dynamodb"
            ).transact_write_items(
                TransactItems=[
                    {
                        "Put": {
                            "TableName":
                                OPS_TABLE_NAME,
                            "Item":
                                _serialize_map(
                                    project
                                ),
                            "ConditionExpression": (
                                "attribute_not_exists("
                                "PK)"
                            ),
                        }
                    },
                    {
                        "Update": {
                            "TableName":
                                OPS_TABLE_NAME,
                            "Key":
                                _serialize_map({
                                    "PK":
                                        f"LEAD#{reference}",
                                    "SK":
                                        "STATE",
                                }),
                            "UpdateExpression": (
                                "SET "
                                "recordType = "
                                "if_not_exists("
                                "recordType, "
                                ":record_type), "
                                "leadReference = "
                                "if_not_exists("
                                "leadReference, "
                                ":reference), "
                                "#status = :won, "
                                "convertedProjectId = "
                                ":project_id, "
                                "createdAt = "
                                "if_not_exists("
                                "createdAt, :now), "
                                "createdBy = "
                                "if_not_exists("
                                "createdBy, :actor), "
                                "updatedAt = :now, "
                                "updatedBy = :actor, "
                                "GSI3PK = :gsi_pk, "
                                "GSI3SK = :gsi_sk"
                            ),
                            "ConditionExpression": (
                                "attribute_not_exists("
                                "convertedProjectId) "
                                "AND ("
                                "attribute_not_exists("
                                "#status) "
                                "OR #status <> :lost)"
                            ),
                            "ExpressionAttributeNames": {
                                "#status": "status",
                            },
                            "ExpressionAttributeValues":
                                _serialize_map({
                                    ":record_type":
                                        "LEAD_STATE",
                                    ":reference":
                                        reference,
                                    ":won":
                                        "WON",
                                    ":lost":
                                        "LOST",
                                    ":project_id":
                                        project_id,
                                    ":now":
                                        now,
                                    ":actor":
                                        actor_subject,
                                    ":gsi_pk":
                                        "LEADS#STATUS#WON",
                                    ":gsi_sk":
                                        (
                                            f"UPDATED#{now}"
                                            f"#LEAD#{reference}"
                                        ),
                                }),
                        }
                    },
                ]
            )

            return project, True

        except ClientError as exc:
            if (
                _aws_error_code(exc)
                !=
                "TransactionCanceledException"
            ):
                raise

            current_state = _lead_state(
                reference
            )

            if current_state:
                existing_project_id = str(
                    current_state.get(
                        "convertedProjectId"
                    )
                    or ""
                )

                if existing_project_id:
                    existing_project = (
                        _project_record(
                            existing_project_id
                        )
                    )

                    if not existing_project:
                        raise RuntimeError(
                            "converted_project_missing"
                        )

                    return (
                        existing_project,
                        False,
                    )

                if (
                    str(
                        current_state.get(
                            "status"
                        )
                        or ""
                    ).upper()
                    == "LOST"
                ):
                    raise LeadConversionConflict(
                        "lead_marked_lost"
                    )

    raise RuntimeError(
        "project_conversion_failed"
    )


def _new_record_id(
    prefix: str,
) -> str:
    return (
        f"{prefix}-"
        f"{uuid4().hex[:12].upper()}"
    )


def _normalize_note_category(
    value: Any,
) -> str | None:
    category = str(
        value
        or ""
    ).strip().upper()

    if category not in NOTE_CATEGORIES:
        return None

    return category


def _normalize_follow_up_status(
    value: Any,
) -> str | None:
    status = str(
        value
        or ""
    ).strip().upper()

    if status not in FOLLOW_UP_STATUSES:
        return None

    return status


def _normalize_due_at(
    value: Any,
) -> str | None:
    raw = str(
        value
        or ""
    ).strip()

    if not raw:
        return None

    candidate = (
        raw[:-1] + "+00:00"
        if raw.endswith("Z")
        else raw
    )

    try:
        parsed = datetime.fromisoformat(
            candidate
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return None

    return (
        parsed
        .astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _public_note(
    item: dict[str, Any],
) -> dict[str, Any]:
    return {
        "noteId": str(
            item.get("noteId")
            or ""
        ),
        "projectId": str(
            item.get("projectId")
            or ""
        ),
        "category": str(
            item.get("category")
            or ""
        ),
        "body": str(
            item.get("body")
            or ""
        ),
        "createdAt": str(
            item.get("createdAt")
            or ""
        ),
        "createdBy": str(
            item.get("createdBy")
            or ""
        ),
        "updatedAt": str(
            item.get("updatedAt")
            or ""
        ),
        "updatedBy": str(
            item.get("updatedBy")
            or ""
        ),
    }


def _public_follow_up(
    item: dict[str, Any],
) -> dict[str, Any]:
    return {
        "followUpId": str(
            item.get("followUpId")
            or ""
        ),
        "projectId": str(
            item.get("projectId")
            or ""
        ),
        "title": str(
            item.get("title")
            or ""
        ),
        "details": str(
            item.get("details")
            or ""
        ),
        "status": str(
            item.get("status")
            or ""
        ),
        "assigneeUserId": str(
            item.get("assigneeUserId")
            or ""
        ),
        "dueAt": str(
            item.get("dueAt")
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
        "completedAt": str(
            item.get("completedAt")
            or ""
        ),
        "closedAt": str(
            item.get("closedAt")
            or ""
        ),
    }


def _public_activity(
    item: dict[str, Any],
) -> dict[str, Any]:
    metadata = item.get("metadata")

    if not isinstance(metadata, dict):
        metadata = {}

    return {
        "activityId": str(
            item.get("activityId")
            or ""
        ),
        "projectId": str(
            item.get("projectId")
            or ""
        ),
        "activityType": str(
            item.get("activityType")
            or ""
        ),
        "summary": str(
            item.get("summary")
            or ""
        ),
        "actorUserId": str(
            item.get("actorUserId")
            or ""
        ),
        "createdAt": str(
            item.get("createdAt")
            or ""
        ),
        "metadata": metadata,
    }


def _project_child_record(
    project_id: str,
    sk: str,
    record_type: str,
) -> dict[str, Any] | None:
    response = _ops_table().get_item(
        Key={
            "PK":
                f"PROJECT#{project_id}",
            "SK":
                sk,
        },
        ConsistentRead=True,
    )

    item = response.get("Item")

    if (
        not isinstance(item, dict)
        or item.get("recordType")
            != record_type
    ):
        return None

    return item


def _list_project_children(
    project_id: str,
    prefix: str,
    record_type: str,
) -> list[dict[str, Any]]:
    response = _ops_table().query(
        KeyConditionExpression=(
            "PK = :pk AND "
            "begins_with(SK, :prefix)"
        ),
        ExpressionAttributeValues={
            ":pk":
                f"PROJECT#{project_id}",
            ":prefix":
                prefix,
        },
        ConsistentRead=True,
    )

    return [
        item
        for item in (
            response.get("Items")
            or []
        )
        if (
            isinstance(item, dict)
            and item.get("recordType")
                == record_type
        )
    ]


def _append_activity(
    project_id: str,
    actor_subject: str,
    activity_type: str,
    summary: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = _utcnow()

    activity_id = _new_record_id(
        "ACT"
    )

    item = {
        "PK":
            f"PROJECT#{project_id}",
        "SK":
            (
                f"ACTIVITY#{now}"
                f"#{activity_id}"
            ),
        "recordType":
            "ACTIVITY",
        "activityId":
            activity_id,
        "projectId":
            project_id,
        "activityType":
            activity_type,
        "summary":
            summary,
        "actorUserId":
            actor_subject,
        "metadata":
            metadata or {},
        "createdAt":
            now,
    }

    table = _ops_table()

    table.put_item(
        Item=item,
        ConditionExpression=(
            "attribute_not_exists(PK) "
            "AND attribute_not_exists(SK)"
        ),
    )

    table.update_item(
        Key={
            "PK":
                f"PROJECT#{project_id}",
            "SK":
                "META",
        },
        UpdateExpression=(
            "SET "
            "lastActivityAt = :now, "
            "lastActivityBy = :actor"
        ),
        ConditionExpression=(
            "attribute_exists(PK) "
            "AND recordType = :project_type"
        ),
        ExpressionAttributeValues={
            ":now":
                now,
            ":actor":
                actor_subject,
            ":project_type":
                "PROJECT",
        },
    )

    return item


def _record_activity(
    project_id: str,
    actor_subject: str,
    activity_type: str,
    summary: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        _append_activity(
            project_id,
            actor_subject,
            activity_type,
            summary,
            metadata,
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Operational activity write failed "
            "project=%s type=%s",
            project_id,
            activity_type,
        )


def _list_project_activity(
    project_id: str,
) -> list[dict[str, Any]]:
    response = _ops_table().query(
        KeyConditionExpression=(
            "PK = :pk AND "
            "begins_with(SK, :prefix)"
        ),
        ExpressionAttributeValues={
            ":pk":
                f"PROJECT#{project_id}",
            ":prefix":
                "ACTIVITY#",
        },
        ConsistentRead=True,
        ScanIndexForward=False,
        Limit=100,
    )

    return [
        item
        for item in (
            response.get("Items")
            or []
        )
        if (
            isinstance(item, dict)
            and item.get("recordType")
                == "ACTIVITY"
        )
    ]


def _create_project_note(
    project_id: str,
    *,
    category: str,
    body: str,
    actor_subject: str,
) -> dict[str, Any]:
    note_id = _new_record_id(
        "NTE"
    )

    now = _utcnow()

    item = {
        "PK":
            f"PROJECT#{project_id}",
        "SK":
            f"NOTE#{note_id}",
        "recordType":
            "NOTE",
        "noteId":
            note_id,
        "projectId":
            project_id,
        "category":
            category,
        "body":
            body,
        "createdAt":
            now,
        "createdBy":
            actor_subject,
        "updatedAt":
            now,
        "updatedBy":
            actor_subject,
    }

    _ops_table().put_item(
        Item=item,
        ConditionExpression=(
            "attribute_not_exists(PK) "
            "AND attribute_not_exists(SK)"
        ),
    )

    _record_activity(
        project_id,
        actor_subject,
        "NOTE_ADDED",
        f"Added {category.lower()} note",
        {
            "noteId":
                note_id,
            "category":
                category,
        },
    )

    return item


def _update_project_note(
    current: dict[str, Any],
    *,
    category: str,
    body: str,
    actor_subject: str,
) -> dict[str, Any]:
    now = _utcnow()

    response = _ops_table().update_item(
        Key={
            "PK":
                current["PK"],
            "SK":
                current["SK"],
        },
        UpdateExpression=(
            "SET "
            "category = :category, "
            "body = :body, "
            "updatedAt = :updated, "
            "updatedBy = :actor"
        ),
        ExpressionAttributeValues={
            ":category":
                category,
            ":body":
                body,
            ":updated":
                now,
            ":actor":
                actor_subject,
            ":note_type":
                "NOTE",
        },
        ConditionExpression=(
            "attribute_exists(PK) "
            "AND recordType = :note_type"
        ),
        ReturnValues="ALL_NEW",
    )

    updated = response["Attributes"]

    _record_activity(
        str(
            updated.get("projectId")
            or ""
        ),
        actor_subject,
        "NOTE_UPDATED",
        "Updated project note",
        {
            "noteId":
                str(
                    updated.get("noteId")
                    or ""
                ),
            "category":
                category,
        },
    )

    return updated


def _create_project_follow_up(
    project_id: str,
    *,
    title: str,
    details: str,
    assignee_user_id: str,
    due_at: str,
    actor_subject: str,
) -> dict[str, Any]:
    follow_up_id = _new_record_id(
        "FUP"
    )

    now = _utcnow()

    item: dict[str, Any] = {
        "PK":
            f"PROJECT#{project_id}",
        "SK":
            f"FOLLOWUP#{follow_up_id}",
        "recordType":
            "FOLLOW_UP",
        "followUpId":
            follow_up_id,
        "projectId":
            project_id,
        "title":
            title,
        "details":
            details,
        "status":
            "OPEN",
        "assigneeUserId":
            assignee_user_id,
        "dueAt":
            due_at,
        "createdAt":
            now,
        "createdBy":
            actor_subject,
        "updatedAt":
            now,
        "updatedBy":
            actor_subject,
        "GSI3PK":
            "QUEUE#FOLLOWUP#OPEN",
        "GSI3SK": (
            f"DUE#{due_at}"
            f"#PROJECT#{project_id}"
            f"#FOLLOWUP#{follow_up_id}"
        ),
    }

    if assignee_user_id:
        item["GSI1PK"] = (
            f"ASSIGNEE#{assignee_user_id}"
        )

        item["GSI1SK"] = (
            f"DUE#{due_at}"
            f"#TYPE#FOLLOWUP"
            f"#PROJECT#{project_id}"
            f"#FOLLOWUP#{follow_up_id}"
        )

    _ops_table().put_item(
        Item=item,
        ConditionExpression=(
            "attribute_not_exists(PK) "
            "AND attribute_not_exists(SK)"
        ),
    )

    _record_activity(
        project_id,
        actor_subject,
        "FOLLOWUP_CREATED",
        f"Created follow-up: {title}",
        {
            "followUpId":
                follow_up_id,
            "dueAt":
                due_at,
            "assigneeUserId":
                assignee_user_id,
        },
    )

    return item


def _update_project_follow_up(
    current: dict[str, Any],
    *,
    title: str,
    details: str,
    status: str,
    assignee_user_id: str,
    due_at: str,
    actor_subject: str,
) -> dict[str, Any]:
    now = _utcnow()

    previous_status = str(
        current.get("status")
        or "OPEN"
    )

    names = {
        "#status":
            "status",
    }

    values: dict[str, Any] = {
        ":title":
            title,
        ":details":
            details,
        ":status":
            status,
        ":assignee":
            assignee_user_id,
        ":due_at":
            due_at,
        ":updated":
            now,
        ":actor":
            actor_subject,
        ":follow_up_type":
            "FOLLOW_UP",
    }

    set_parts = [
        "title = :title",
        "details = :details",
        "#status = :status",
        "assigneeUserId = :assignee",
        "dueAt = :due_at",
        "updatedAt = :updated",
        "updatedBy = :actor",
    ]

    remove_parts: list[str] = []

    if status == "OPEN":
        values[":gsi3pk"] = (
            "QUEUE#FOLLOWUP#OPEN"
        )

        values[":gsi3sk"] = (
            f"DUE#{due_at}"
            f"#PROJECT#{current['projectId']}"
            f"#FOLLOWUP#{current['followUpId']}"
        )

        set_parts.extend([
            "GSI3PK = :gsi3pk",
            "GSI3SK = :gsi3sk",
        ])

        if assignee_user_id:
            values[":gsi1pk"] = (
                f"ASSIGNEE#{assignee_user_id}"
            )

            values[":gsi1sk"] = (
                f"DUE#{due_at}"
                f"#TYPE#FOLLOWUP"
                f"#PROJECT#{current['projectId']}"
                f"#FOLLOWUP#{current['followUpId']}"
            )

            set_parts.extend([
                "GSI1PK = :gsi1pk",
                "GSI1SK = :gsi1sk",
            ])

        else:
            remove_parts.extend([
                "GSI1PK",
                "GSI1SK",
            ])

        remove_parts.extend([
            "closedAt",
            "closedBy",
            "completedAt",
        ])

    else:
        values[":closed_at"] = now
        values[":closed_by"] = (
            actor_subject
        )

        set_parts.extend([
            "closedAt = :closed_at",
            "closedBy = :closed_by",
        ])

        remove_parts.extend([
            "GSI1PK",
            "GSI1SK",
            "GSI3PK",
            "GSI3SK",
        ])

        if status == "DONE":
            values[":completed_at"] = now

            set_parts.append(
                "completedAt = :completed_at"
            )

        else:
            remove_parts.append(
                "completedAt"
            )

    update_expression = (
        "SET "
        + ", ".join(set_parts)
    )

    if remove_parts:
        update_expression += (
            " REMOVE "
            + ", ".join(
                dict.fromkeys(
                    remove_parts
                )
            )
        )

    response = _ops_table().update_item(
        Key={
            "PK":
                current["PK"],
            "SK":
                current["SK"],
        },
        UpdateExpression=
            update_expression,
        ExpressionAttributeNames=
            names,
        ExpressionAttributeValues=
            values,
        ConditionExpression=(
            "attribute_exists(PK) "
            "AND recordType = "
            ":follow_up_type"
        ),
        ReturnValues="ALL_NEW",
    )

    updated = response["Attributes"]

    if (
        status == "DONE"
        and previous_status != "DONE"
    ):
        activity_type = (
            "FOLLOWUP_COMPLETED"
        )

        summary = (
            f"Completed follow-up: "
            f"{title}"
        )

    elif (
        status == "CANCELED"
        and previous_status
            != "CANCELED"
    ):
        activity_type = (
            "FOLLOWUP_CANCELED"
        )

        summary = (
            f"Canceled follow-up: "
            f"{title}"
        )

    elif (
        status == "OPEN"
        and previous_status != "OPEN"
    ):
        activity_type = (
            "FOLLOWUP_REOPENED"
        )

        summary = (
            f"Reopened follow-up: "
            f"{title}"
        )

    else:
        activity_type = (
            "FOLLOWUP_UPDATED"
        )

        summary = (
            f"Updated follow-up: "
            f"{title}"
        )

    _record_activity(
        str(
            updated.get("projectId")
            or ""
        ),
        actor_subject,
        activity_type,
        summary,
        {
            "followUpId":
                str(
                    updated.get(
                        "followUpId"
                    )
                    or ""
                ),
            "status":
                status,
            "dueAt":
                due_at,
            "assigneeUserId":
                assignee_user_id,
        },
    )

    return updated


def _list_open_follow_ups(
    limit: int = 100,
) -> list[dict[str, Any]]:
    response = _ops_table().query(
        IndexName="GSI3",
        KeyConditionExpression=(
            "GSI3PK = :pk"
        ),
        ExpressionAttributeValues={
            ":pk":
                "QUEUE#FOLLOWUP#OPEN",
        },
        ScanIndexForward=True,
        Limit=limit,
    )

    return [
        item
        for item in (
            response.get("Items")
            or []
        )
        if (
            isinstance(item, dict)
            and item.get("recordType")
                == "FOLLOW_UP"
            and item.get("status")
                == "OPEN"
        )
    ]


def _normalize_task_status(
    value: Any,
) -> str | None:
    status = str(
        value
        or ""
    ).strip().upper()

    if status not in TASK_STATUSES:
        return None

    return status


def _normalize_task_priority(
    value: Any,
) -> str | None:
    priority = str(
        value
        or ""
    ).strip().upper()

    if priority not in TASK_PRIORITIES:
        return None

    return priority


def _next_task_id(
    project_id: str,
) -> str:
    response = _ops_table().update_item(
        Key={
            "PK":
                f"PROJECT#{project_id}",
            "SK":
                "COUNTER#TASK",
        },
        UpdateExpression=(
            "SET "
            "recordType = if_not_exists("
            "recordType, :record_type), "
            "updatedAt = :updated "
            "ADD nextValue :one"
        ),
        ExpressionAttributeValues={
            ":record_type":
                "TASK_COUNTER",
            ":updated":
                _utcnow(),
            ":one":
                1,
        },
        ReturnValues="ALL_NEW",
    )

    number = int(
        response["Attributes"]["nextValue"]
    )

    return f"TASK-{number:03d}"


def _task_due_sort(
    due_date: str,
) -> str:
    return (
        due_date
        if due_date
        else "9999-12-31"
    )


def _public_task(
    item: dict[str, Any],
) -> dict[str, Any]:
    return {
        "taskId": str(
            item.get("taskId")
            or ""
        ),
        "projectId": str(
            item.get("projectId")
            or ""
        ),
        "title": str(
            item.get("title")
            or ""
        ),
        "description": str(
            item.get("description")
            or ""
        ),
        "status": str(
            item.get("status")
            or ""
        ),
        "priority": str(
            item.get("priority")
            or ""
        ),
        "assigneeUserId": str(
            item.get("assigneeUserId")
            or ""
        ),
        "dueDate": str(
            item.get("dueDate")
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
    }


def _task_record(
    project_id: str,
    task_id: str,
) -> dict[str, Any] | None:
    response = _ops_table().get_item(
        Key={
            "PK":
                f"PROJECT#{project_id}",
            "SK":
                f"TASK#{task_id}",
        },
        ConsistentRead=True,
    )

    item = response.get("Item")

    if (
        not isinstance(item, dict)
        or item.get("recordType")
            != "TASK"
    ):
        return None

    return item


def _list_project_tasks(
    project_id: str,
) -> list[dict[str, Any]]:
    response = _ops_table().query(
        KeyConditionExpression=(
            "PK = :pk AND "
            "begins_with(SK, :task)"
        ),
        ExpressionAttributeValues={
            ":pk":
                f"PROJECT#{project_id}",
            ":task":
                "TASK#",
        },
        ConsistentRead=True,
    )

    items = [
        item
        for item in (
            response.get("Items")
            or []
        )
        if (
            isinstance(item, dict)
            and item.get("recordType")
                == "TASK"
        )
    ]

    return sorted(
        items,
        key=lambda item: (
            str(
                item.get("status")
                or ""
            ),
            _task_due_sort(
                str(
                    item.get("dueDate")
                    or ""
                )
            ),
            str(
                item.get("taskId")
                or ""
            ),
        ),
    )


def _list_all_tasks() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for status in TASK_STATUSES:
        response = _ops_table().query(
            IndexName="GSI3",
            KeyConditionExpression=(
                "GSI3PK = :pk"
            ),
            ExpressionAttributeValues={
                ":pk":
                    f"QUEUE#TASK#{status}",
            },
            ScanIndexForward=True,
        )

        for item in (
            response.get("Items")
            or []
        ):
            if (
                isinstance(item, dict)
                and item.get("recordType")
                    == "TASK"
            ):
                result.append(item)

    return result


def _create_project_task(
    project_id: str,
    *,
    title: str,
    description: str,
    status: str,
    priority: str,
    assignee_user_id: str,
    due_date: str,
    actor_subject: str,
) -> dict[str, Any]:
    task_id = _next_task_id(
        project_id
    )

    now = _utcnow()

    task = {
        "PK":
            f"PROJECT#{project_id}",
        "SK":
            f"TASK#{task_id}",
        "recordType":
            "TASK",
        "taskId":
            task_id,
        "projectId":
            project_id,
        "title":
            title,
        "description":
            description,
        "status":
            status,
        "priority":
            priority,
        "assigneeUserId":
            assignee_user_id,
        "dueDate":
            due_date,
        "createdAt":
            now,
        "createdBy":
            actor_subject,
        "updatedAt":
            now,
        "updatedBy":
            actor_subject,
        "GSI3PK":
            f"QUEUE#TASK#{status}",
        "GSI3SK": (
            f"DUE#{_task_due_sort(due_date)}"
            f"#PROJECT#{project_id}"
            f"#TASK#{task_id}"
        ),
    }

    if assignee_user_id:
        task["GSI1PK"] = (
            f"ASSIGNEE#{assignee_user_id}"
        )

        task["GSI1SK"] = (
            f"DUE#{_task_due_sort(due_date)}"
            f"#STATUS#{status}"
            f"#PROJECT#{project_id}"
            f"#TASK#{task_id}"
        )

    _ops_table().put_item(
        Item=task,
        ConditionExpression=(
            "attribute_not_exists(PK)"
        ),
    )

    return task


def _update_project_task(
    task: dict[str, Any],
    *,
    title: str | None,
    description: str | None,
    status: str | None,
    priority: str | None,
    assignee_user_id: str | None,
    due_date: str | None,
    actor_subject: str,
) -> dict[str, Any]:
    next_title = (
        title
        if title is not None
        else str(
            task.get("title")
            or ""
        )
    )

    next_description = (
        description
        if description is not None
        else str(
            task.get("description")
            or ""
        )
    )

    next_status = (
        status
        if status is not None
        else str(
            task.get("status")
            or "TODO"
        )
    )

    next_priority = (
        priority
        if priority is not None
        else str(
            task.get("priority")
            or "NORMAL"
        )
    )

    next_assignee = (
        assignee_user_id
        if assignee_user_id is not None
        else str(
            task.get("assigneeUserId")
            or ""
        )
    )

    next_due_date = (
        due_date
        if due_date is not None
        else str(
            task.get("dueDate")
            or ""
        )
    )

    now = _utcnow()

    names = {
        "#status": "status",
    }

    values: dict[str, Any] = {
        ":title":
            next_title,
        ":description":
            next_description,
        ":status":
            next_status,
        ":priority":
            next_priority,
        ":assignee":
            next_assignee,
        ":due_date":
            next_due_date,
        ":updated":
            now,
        ":actor":
            actor_subject,
        ":task_type":
            "TASK",
        ":gsi3pk":
            f"QUEUE#TASK#{next_status}",
        ":gsi3sk": (
            f"DUE#{_task_due_sort(next_due_date)}"
            f"#PROJECT#{task['projectId']}"
            f"#TASK#{task['taskId']}"
        ),
    }

    update_expression = (
        "SET "
        "title = :title, "
        "description = :description, "
        "#status = :status, "
        "priority = :priority, "
        "assigneeUserId = :assignee, "
        "dueDate = :due_date, "
        "updatedAt = :updated, "
        "updatedBy = :actor, "
        "GSI3PK = :gsi3pk, "
        "GSI3SK = :gsi3sk"
    )

    if next_assignee:
        values[":gsi1pk"] = (
            f"ASSIGNEE#{next_assignee}"
        )

        values[":gsi1sk"] = (
            f"DUE#{_task_due_sort(next_due_date)}"
            f"#STATUS#{next_status}"
            f"#PROJECT#{task['projectId']}"
            f"#TASK#{task['taskId']}"
        )

        update_expression += (
            ", GSI1PK = :gsi1pk, "
            "GSI1SK = :gsi1sk"
        )

    else:
        update_expression += (
            " REMOVE GSI1PK, GSI1SK"
        )

    response = _ops_table().update_item(
        Key={
            "PK":
                task["PK"],
            "SK":
                task["SK"],
        },
        UpdateExpression=
            update_expression,
        ExpressionAttributeNames=
            names,
        ExpressionAttributeValues=
            values,
        ConditionExpression=(
            "attribute_exists(PK) "
            "AND recordType = :task_type"
        ),
        ReturnValues="ALL_NEW",
    )

    return response["Attributes"]


def _normalize_project_role(
    value: Any,
) -> str | None:
    role = str(
        value
        or ""
    ).strip().upper()

    if role not in PROJECT_ROLES:
        return None

    return role


def _project_member_record(
    project_id: str,
    user_id: str,
) -> dict[str, Any] | None:
    response = _ops_table().get_item(
        Key={
            "PK": f"PROJECT#{project_id}",
            "SK": f"MEMBER#{user_id}",
        },
        ConsistentRead=True,
    )

    item = response.get("Item")

    if not isinstance(item, dict):
        return None

    if (
        item.get("recordType")
        != "PROJECT_MEMBERSHIP"
    ):
        return None

    return item


def _public_project_member(
    membership: dict[str, Any],
    staff: dict[str, Any] | None = None,
) -> dict[str, Any]:
    staff = staff or {}

    return {
        "userId": str(
            membership.get("userId")
            or ""
        ),
        "projectId": str(
            membership.get("projectId")
            or ""
        ),
        "displayName": str(
            staff.get("displayName")
            or ""
        ),
        "email": str(
            staff.get("email")
            or ""
        ),
        "organizationRole": str(
            staff.get("organizationRole")
            or ""
        ),
        "staffStatus": str(
            staff.get("status")
            or ""
        ),
        "projectRole": str(
            membership.get("projectRole")
            or ""
        ),
        "membershipStatus": str(
            membership.get(
                "membershipStatus"
            )
            or ""
        ),
        "assignedAt": str(
            membership.get("assignedAt")
            or ""
        ),
        "updatedAt": str(
            membership.get("updatedAt")
            or ""
        ),
    }


def _list_project_members(
    project_id: str,
) -> list[dict[str, Any]]:
    response = _ops_table().query(
        KeyConditionExpression=(
            "PK = :pk AND "
            "begins_with(SK, :member)"
        ),
        ExpressionAttributeValues={
            ":pk":
                f"PROJECT#{project_id}",
            ":member": "MEMBER#",
        },
        ConsistentRead=True,
    )

    result = []

    for membership in (
        response.get("Items")
        or []
    ):
        if (
            not isinstance(
                membership,
                dict,
            )
            or membership.get(
                "recordType"
            )
            != "PROJECT_MEMBERSHIP"
            or membership.get(
                "membershipStatus"
            )
            != "ACTIVE"
        ):
            continue

        user_id = str(
            membership.get("userId")
            or ""
        )

        staff = (
            _staff_record(user_id)
            if user_id
            else None
        )

        result.append(
            _public_project_member(
                membership,
                staff,
            )
        )

    return sorted(
        result,
        key=lambda item: (
            item["projectRole"],
            item["displayName"].casefold(),
        ),
    )


def _project_assignment_summary(
    project_id: str,
) -> dict[str, Any]:
    response = _ops_table().query(
        KeyConditionExpression=(
            "PK = :pk AND "
            "begins_with(SK, :member)"
        ),
        ExpressionAttributeValues={
            ":pk":
                f"PROJECT#{project_id}",
            ":member":
                "MEMBER#",
        },
        ConsistentRead=True,
    )

    active_member_count = 0
    active_member_user_ids = []
    project_lead_user_ids = []

    for membership in (
        response.get("Items")
        or []
    ):
        if (
            not isinstance(
                membership,
                dict,
            )
            or membership.get(
                "recordType"
            )
            != "PROJECT_MEMBERSHIP"
            or membership.get(
                "membershipStatus"
            )
            != "ACTIVE"
        ):
            continue

        user_id = str(
            membership.get("userId")
            or ""
        ).strip()

        if not user_id:
            continue

        active_member_count += 1
        active_member_user_ids.append(
            user_id
        )

        if (
            membership.get(
                "projectRole"
            )
            == "PROJECT_LEAD"
        ):
            project_lead_user_ids.append(
                user_id
            )

    return {
        "activeMemberUserIds":
            sorted(
                set(
                    active_member_user_ids
                )
            ),
        "activeMemberCount":
            active_member_count,
        "projectLeadUserIds":
            sorted(
                set(
                    project_lead_user_ids
                )
            ),
    }


def _refresh_project_assignment_summary(
    project_id: str,
):
    summary = (
        _project_assignment_summary(
            project_id
        )
    )

    _ops_table().update_item(
        Key={
            "PK":
                f"PROJECT#{project_id}",
            "SK":
                "META",
        },
        UpdateExpression=(
            "SET "
            "activeMemberUserIds = "
            ":member_ids, "
            "activeMemberCount = "
            ":member_count, "
            "projectLeadUserIds = "
            ":lead_ids, "
            "assignmentSummaryUpdatedAt = "
            ":now"
        ),
        ConditionExpression=(
            "attribute_exists(PK) "
            "AND recordType = :project_type"
        ),
        ExpressionAttributeValues={
            ":member_ids":
                summary[
                    "activeMemberUserIds"
                ],
            ":member_count":
                summary[
                    "activeMemberCount"
                ],
            ":lead_ids":
                summary[
                    "projectLeadUserIds"
                ],
            ":now":
                _utcnow(),
            ":project_type":
                "PROJECT",
        },
    )

    return summary


def _assign_project_member(
    project_id: str,
    user_id: str,
    project_role: str,
    actor_subject: str,
) -> tuple[dict[str, Any], bool]:
    existing = _project_member_record(
        project_id,
        user_id,
    )

    if (
        existing
        and existing.get(
            "membershipStatus"
        )
        == "ACTIVE"
        and existing.get(
            "projectRole"
        )
        == project_role
    ):
        return existing, False

    now = _utcnow()

    response = _ops_table().update_item(
        Key={
            "PK":
                f"PROJECT#{project_id}",
            "SK":
                f"MEMBER#{user_id}",
        },
        UpdateExpression=(
            "SET "
            "recordType = :record_type, "
            "projectId = :project_id, "
            "userId = :user_id, "
            "projectRole = :project_role, "
            "membershipStatus = :active, "
            "createdAt = if_not_exists("
            "createdAt, :now), "
            "createdBy = if_not_exists("
            "createdBy, :actor), "
            "assignedAt = :now, "
            "updatedAt = :now, "
            "updatedBy = :actor, "
            "GSI2PK = :gsi_pk, "
            "GSI2SK = :gsi_sk "
            "REMOVE unassignedAt"
        ),
        ExpressionAttributeValues={
            ":record_type":
                "PROJECT_MEMBERSHIP",
            ":project_id":
                project_id,
            ":user_id":
                user_id,
            ":project_role":
                project_role,
            ":active":
                "ACTIVE",
            ":now":
                now,
            ":actor":
                actor_subject,
            ":gsi_pk":
                f"MEMBER#{user_id}",
            ":gsi_sk":
                (
                    f"PROJECT#{project_id}"
                    f"#ROLE#{project_role}"
                ),
        },
        ReturnValues="ALL_NEW",
    )

    _refresh_project_assignment_summary(
        project_id
    )

    return (
        response["Attributes"],
        True,
    )


def _change_project_member_role(
    project_id: str,
    user_id: str,
    project_role: str,
    actor_subject: str,
) -> dict[str, Any]:
    now = _utcnow()

    response = _ops_table().update_item(
        Key={
            "PK":
                f"PROJECT#{project_id}",
            "SK":
                f"MEMBER#{user_id}",
        },
        UpdateExpression=(
            "SET "
            "projectRole = :role, "
            "updatedAt = :now, "
            "updatedBy = :actor, "
            "GSI2SK = :gsi_sk"
        ),
        ConditionExpression=(
            "attribute_exists(PK) "
            "AND membershipStatus = :active"
        ),
        ExpressionAttributeValues={
            ":role":
                project_role,
            ":now":
                now,
            ":actor":
                actor_subject,
            ":active":
                "ACTIVE",
            ":gsi_sk":
                (
                    f"PROJECT#{project_id}"
                    f"#ROLE#{project_role}"
                ),
        },
        ReturnValues="ALL_NEW",
    )

    _refresh_project_assignment_summary(
        project_id
    )

    return response["Attributes"]


def _unassign_project_member(
    project_id: str,
    user_id: str,
    actor_subject: str,
) -> tuple[dict[str, Any] | None, bool]:
    existing = _project_member_record(
        project_id,
        user_id,
    )

    if not existing:
        return None, False

    if (
        existing.get(
            "membershipStatus"
        )
        != "ACTIVE"
    ):
        return existing, False

    now = _utcnow()

    response = _ops_table().update_item(
        Key={
            "PK":
                f"PROJECT#{project_id}",
            "SK":
                f"MEMBER#{user_id}",
        },
        UpdateExpression=(
            "SET "
            "membershipStatus = :status, "
            "unassignedAt = :now, "
            "updatedAt = :now, "
            "updatedBy = :actor"
        ),
        ExpressionAttributeValues={
            ":status":
                "UNASSIGNED",
            ":now":
                now,
            ":actor":
                actor_subject,
        },
        ReturnValues="ALL_NEW",
    )

    _refresh_project_assignment_summary(
        project_id
    )

    return (
        response["Attributes"],
        True,
    )


def _cognito():
    global _cognito_client_instance

    if not STAFF_USER_POOL_ID:
        raise RuntimeError(
            "staff_user_pool_not_configured"
        )

    if _cognito_client_instance is None:
        _cognito_client_instance = (
            boto3.client("cognito-idp")
        )

    return _cognito_client_instance


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


def _list_staff_records() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    last_key = None

    while True:
        kwargs: dict[str, Any] = {
            "IndexName": "GSI2",
            "KeyConditionExpression":
                "GSI2PK = :staff",
            "ExpressionAttributeValues": {
                ":staff": "STAFF",
            },
        }

        if last_key:
            kwargs["ExclusiveStartKey"] = last_key

        response = _ops_table().query(
            **kwargs
        )

        page = response.get("Items") or []

        items.extend(
            item
            for item in page
            if isinstance(item, dict)
        )

        last_key = response.get(
            "LastEvaluatedKey"
        )

        if not last_key:
            break

    return sorted(
        items,
        key=lambda item: str(
            item.get("displayName")
            or item.get("email")
            or ""
        ).casefold(),
    )


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


def _authz_version(
    staff: dict[str, Any],
) -> int:
    try:
        return int(
            staff.get("authzVersion")
            or 1
        )
    except (TypeError, ValueError):
        return 1


def _staff_id(
    staff: dict[str, Any],
) -> str:
    pk = str(
        staff.get("PK")
        or ""
    )

    if pk.startswith("USER#"):
        return pk[5:]

    return ""


def _new_lead_email_notifications(
    staff: dict[str, Any],
) -> bool:
    value = staff.get(
        "newLeadEmailNotifications"
    )

    if isinstance(value, bool):
        return value

    role = str(
        staff.get("organizationRole")
        or ""
    ).strip().upper()

    # Existing OWNER / MANAGER accounts
    # predate the preference field.
    return role in {
        "OWNER",
        "MANAGER",
    }


def _public_staff(
    staff: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": _staff_id(staff),
        "displayName": str(
            staff.get("displayName")
            or ""
        ),
        "email": str(
            staff.get("email")
            or ""
        ),
        "role": str(
            staff.get("organizationRole")
            or ""
        ),
        "status": str(
            staff.get("status")
            or ""
        ),
        "authzVersion":
            _authz_version(staff),
        "preferredLocale": str(
            staff.get("preferredLocale")
            or "en"
        ),
        "createdAt": str(
            staff.get("createdAt")
            or ""
        ),
        "updatedAt": str(
            staff.get("updatedAt")
            or ""
        ),
        "newLeadEmailNotifications":
            _new_lead_email_notifications(
                staff
            ),

    }


def _authorize_identity(
    event: dict[str, Any],
):
    claims = _claims(event)

    subject = str(
        claims.get("sub")
        or ""
    ).strip()

    if not subject:
        return None, _response(
            401,
            {"error": "unauthorized"},
        )

    token_use = str(
        claims.get("token_use")
        or ""
    ).strip()

    if token_use != "access":
        return None, _response(
            401,
            {"error": "invalid_token_type"},
        )

    identity_role = _effective_role(
        _groups(claims)
    )

    if not identity_role:
        return None, _response(
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

        return None, _response(
            503,
            {"error": "temporarily_unavailable"},
        )

    if not staff:
        return None, _response(
            403,
            {"error": "staff_profile_required"},
        )

    status = str(
        staff.get("status")
        or ""
    ).strip().upper()

    if status != "ACTIVE":
        return None, _response(
            403,
            {"error": "staff_disabled"},
        )

    role = str(
        staff.get("organizationRole")
        or ""
    ).strip().upper()

    if role not in ORGANIZATION_ROLES:
        return None, _response(
            403,
            {"error": "invalid_staff_role"},
        )

    return {
        "subject": subject,
        "claims": claims,
        "profile": staff,
        "role": role,
    }, None



def _preview_token_secret() -> str:
    global _preview_token_secret_value

    if not PREVIEW_TOKEN_SECRET_ARN:
        raise RuntimeError(
            "preview_secret_not_configured"
        )

    if _preview_token_secret_value is None:
        response = (
            boto3.client("secretsmanager")
            .get_secret_value(
                SecretId=PREVIEW_TOKEN_SECRET_ARN
            )
        )

        secret = str(
            response.get("SecretString")
            or ""
        ).strip()

        if not secret:
            raise RuntimeError(
                "preview_secret_empty"
            )

        _preview_token_secret_value = secret

    return _preview_token_secret_value


def _handle_preview_access(
    identity: dict[str, Any],
):
    if (
        STAGE != "dev"
        or not PREVIEW_TOKEN_SECRET_ARN
        or not PREVIEW_BASE_URL
    ):
        return _response(
            404,
            {"error": "preview_not_available"},
        )

    role = str(
        identity.get("role")
        or ""
    ).strip().upper()

    if role not in {
        "OWNER",
        "MANAGER",
    }:
        return _response(
            403,
            {
                "error":
                    "manager_or_owner_required"
            },
        )

    try:
        secret = _preview_token_secret()
    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Preview token secret lookup failed"
        )

        return _response(
            503,
            {"error": "temporarily_unavailable"},
        )

    now = int(
        datetime.now(timezone.utc).timestamp()
    )

    expires = (
        now + PREVIEW_TOKEN_TTL_SECONDS
    )

    nonce = uuid4().hex

    message = (
        f"v1.{expires}.{nonce}.{role}"
    )

    signature = (
        base64.urlsafe_b64encode(
            hmac.new(
                secret.encode("utf-8"),
                message.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        )
        .decode("ascii")
        .rstrip("=")
    )

    token = f"{message}.{signature}"

    preview_url = (
        f"{PREVIEW_BASE_URL.rstrip('/')}"
        f"/?preview={token}"
    )

    return _response(
        200,
        {
            "previewUrl": preview_url,
            "expiresAt": (
                datetime.fromtimestamp(
                    expires,
                    timezone.utc,
                ).isoformat()
            ),
            "expiresInSeconds":
                PREVIEW_TOKEN_TTL_SECONDS,
        },
    )


def _request_body(
    event: dict[str, Any],
) -> dict[str, Any] | None:
    raw = event.get("body")

    if not isinstance(raw, str):
        return None

    try:
        if event.get("isBase64Encoded"):
            raw = (
                base64.b64decode(raw)
                .decode("utf-8")
            )

        parsed = json.loads(raw)

    except (
        ValueError,
        UnicodeDecodeError,
    ):
        return None

    if not isinstance(parsed, dict):
        return None

    return parsed


def _normalize_email(
    value: Any,
) -> str | None:
    email = str(
        value
        or ""
    ).strip().lower()

    if (
        not email
        or len(email) > 254
        or " " in email
        or email.count("@") != 1
    ):
        return None

    local, domain = email.split(
        "@",
        1,
    )

    if (
        not local
        or not domain
        or "." not in domain
    ):
        return None

    return email


def _normalize_display_name(
    value: Any,
) -> str | None:
    name = " ".join(
        str(
            value
            or ""
        ).split()
    )

    if (
        not name
        or len(name) > 120
    ):
        return None

    return name


def _normalize_role(
    value: Any,
) -> str | None:
    role = str(
        value
        or ""
    ).strip().upper()

    if role not in ORGANIZATION_ROLES:
        return None

    return role


def _normalize_locale(
    value: Any,
) -> str | None:
    locale = str(
        value
        or "en"
    ).strip().lower()

    if locale not in {
        "en",
        "id",
    }:
        return None

    return locale


def _cognito_sub(
    user: dict[str, Any],
) -> str:
    for attribute in (
        user.get("Attributes")
        or []
    ):
        if (
            attribute.get("Name")
            == "sub"
        ):
            return str(
                attribute.get("Value")
                or ""
            )

    return ""


def _gsi_staff_sort_key(
    role: str,
    staff: dict[str, Any],
    subject: str,
) -> str:
    name = str(
        staff.get("displayName")
        or staff.get("email")
        or subject
    ).strip().upper()

    return (
        f"ROLE#{role}"
        f"#NAME#{name}"
        f"#USER#{subject}"
    )


def _create_staff(
    actor_subject: str,
    display_name: str,
    email: str,
    role: str,
    locale: str,
) -> dict[str, Any]:
    client = _cognito()
    username = ""

    try:
        created = client.admin_create_user(
            UserPoolId=STAFF_USER_POOL_ID,
            Username=email,
            UserAttributes=[
                {
                    "Name": "email",
                    "Value": email,
                },
                {
                    "Name": "email_verified",
                    "Value": "true",
                },
            ],
            DesiredDeliveryMediums=[
                "EMAIL",
            ],
        )

        user = (
            created.get("User")
            or {}
        )

        username = str(
            user.get("Username")
            or ""
        )

        subject = _cognito_sub(user)

        if (
            not username
            or not subject
        ):
            raise RuntimeError(
                "cognito_identity_incomplete"
            )

        client.admin_add_user_to_group(
            UserPoolId=STAFF_USER_POOL_ID,
            Username=username,
            GroupName=role,
        )

        now = _utcnow()

        item = {
            "PK": f"USER#{subject}",
            "SK": "PROFILE",
            "recordType": "STAFF_USER",
            "cognitoUsername": username,
            "displayName": display_name,
            "email": email,
            "organizationRole": role,
            "status": "ACTIVE",
            "authzVersion": 1,
            "preferredLocale": locale,
            "newLeadEmailNotifications":
                role in {
                    "OWNER",
                    "MANAGER",
                },
            "GSI2PK": "STAFF",
            "GSI2SK": (
                f"ROLE#{role}"
                f"#NAME#{display_name.upper()}"
                f"#USER#{subject}"
            ),
            "createdBy": actor_subject,
            "updatedBy": actor_subject,
            "createdAt": now,
            "updatedAt": now,
        }

        _ops_table().put_item(
            Item=item,
            ConditionExpression=(
                "attribute_not_exists(PK)"
            ),
        )

        LOGGER.info(
            "staff_admin action=create "
            "actor=%s target=%s role=%s",
            actor_subject,
            subject,
            role,
        )

        return item

    except Exception:
        if username:
            try:
                client.admin_delete_user(
                    UserPoolId=
                        STAFF_USER_POOL_ID,
                    Username=username,
                )
            except Exception:
                LOGGER.exception(
                    "Failed rollback of "
                    "Cognito staff user"
                )

        raise


def _sync_cognito_role(
    staff: dict[str, Any],
    subject: str,
    role: str,
) -> bool:
    username = str(
        staff.get("cognitoUsername")
        or subject
    )

    client = _cognito()

    try:
        response = (
            client
            .admin_list_groups_for_user(
                UserPoolId=
                    STAFF_USER_POOL_ID,
                Username=username,
            )
        )

        current_groups = {
            str(
                group.get("GroupName")
                or ""
            )
            for group in (
                response.get("Groups")
                or []
            )
        }

        for existing_role in (
            ORGANIZATION_ROLES
        ):
            if (
                existing_role
                in current_groups
                and existing_role != role
            ):
                client.admin_remove_user_from_group(
                    UserPoolId=
                        STAFF_USER_POOL_ID,
                    Username=username,
                    GroupName=existing_role,
                )

        if role not in current_groups:
            client.admin_add_user_to_group(
                UserPoolId=
                    STAFF_USER_POOL_ID,
                Username=username,
                GroupName=role,
            )

        try:
            client.admin_user_global_sign_out(
                UserPoolId=
                    STAFF_USER_POOL_ID,
                Username=username,
            )
        except ClientError:
            LOGGER.warning(
                "Global sign-out failed "
                "during role sync target=%s",
                subject,
            )

        return True

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Cognito role sync failed "
            "target=%s role=%s",
            subject,
            role,
        )

        return False


def _set_staff_role(
    actor_subject: str,
    subject: str,
    staff: dict[str, Any],
    role: str,
):
    now = _utcnow()

    updated = _ops_table().update_item(
        Key={
            "PK": f"USER#{subject}",
            "SK": "PROFILE",
        },
        UpdateExpression=(
            "SET organizationRole = :role, "
            "GSI2SK = :gsi, "
            "updatedAt = :updated, "
            "updatedBy = :actor "
            "ADD authzVersion :one"
        ),
        ExpressionAttributeValues={
            ":role": role,
            ":gsi": _gsi_staff_sort_key(
                role,
                staff,
                subject,
            ),
            ":updated": now,
            ":actor": actor_subject,
            ":one": 1,
        },
        ConditionExpression=(
            "attribute_exists(PK) "
            "AND attribute_exists(SK)"
        ),
        ReturnValues="ALL_NEW",
    )["Attributes"]

    synced = _sync_cognito_role(
        updated,
        subject,
        role,
    )

    LOGGER.info(
        "staff_admin action=role_change "
        "actor=%s target=%s role=%s "
        "identity_sync=%s",
        actor_subject,
        subject,
        role,
        synced,
    )

    return updated, synced


def _disable_cognito_user(
    staff: dict[str, Any],
    subject: str,
) -> bool:
    username = str(
        staff.get("cognitoUsername")
        or subject
    )

    client = _cognito()
    synced = True

    try:
        client.admin_user_global_sign_out(
            UserPoolId=STAFF_USER_POOL_ID,
            Username=username,
        )
    except ClientError:
        synced = False

        LOGGER.warning(
            "Global sign-out failed "
            "target=%s",
            subject,
        )

    try:
        client.admin_disable_user(
            UserPoolId=STAFF_USER_POOL_ID,
            Username=username,
        )
    except (
        BotoCoreError,
        ClientError,
    ):
        synced = False

        LOGGER.exception(
            "Cognito disable failed "
            "target=%s",
            subject,
        )

    return synced


def _enable_cognito_user(
    staff: dict[str, Any],
    subject: str,
) -> None:
    username = str(
        staff.get("cognitoUsername")
        or subject
    )

    _cognito().admin_enable_user(
        UserPoolId=STAFF_USER_POOL_ID,
        Username=username,
    )


def _update_staff_status_record(
    actor_subject: str,
    subject: str,
    status: str,
):
    return _ops_table().update_item(
        Key={
            "PK": f"USER#{subject}",
            "SK": "PROFILE",
        },
        UpdateExpression=(
            "SET #status = :status, "
            "updatedAt = :updated, "
            "updatedBy = :actor "
            "ADD authzVersion :one"
        ),
        ExpressionAttributeNames={
            "#status": "status",
        },
        ExpressionAttributeValues={
            ":status": status,
            ":updated": _utcnow(),
            ":actor": actor_subject,
            ":one": 1,
        },
        ConditionExpression=(
            "attribute_exists(PK) "
            "AND attribute_exists(SK)"
        ),
        ReturnValues="ALL_NEW",
    )["Attributes"]


def _set_staff_status(
    actor_subject: str,
    subject: str,
    staff: dict[str, Any],
    status: str,
):
    current_status = str(
        staff.get("status")
        or ""
    ).upper()

    if status == "DISABLED":
        if current_status == status:
            updated = staff
        else:
            updated = (
                _update_staff_status_record(
                    actor_subject,
                    subject,
                    status,
                )
            )

        synced = _disable_cognito_user(
            updated,
            subject,
        )

    else:
        _enable_cognito_user(
            staff,
            subject,
        )

        if current_status == status:
            updated = staff
        else:
            updated = (
                _update_staff_status_record(
                    actor_subject,
                    subject,
                    status,
                )
            )

        synced = True

    LOGGER.info(
        "staff_admin action=status_change "
        "actor=%s target=%s status=%s "
        "identity_sync=%s",
        actor_subject,
        subject,
        status,
        synced,
    )

    return updated, synced


def _aws_error_code(
    exc: ClientError,
) -> str:
    return str(
        (
            exc.response.get("Error")
            or {}
        ).get("Code")
        or ""
    )


def _me_response(
    identity: dict[str, Any],
) -> dict[str, Any]:
    claims = identity["claims"]
    staff = identity["profile"]

    username = str(
        claims.get("username")
        or claims.get("cognito:username")
        or ""
    ).strip()

    user = _public_staff(staff)
    user["username"] = username

    return _response(
        200,
        {
            "ok": True,
            "stage": STAGE,
            "user": user,
        },
    )


def _handle_list_leads():
    try:
        items = _list_leads()

        references = [
            str(
                item.get("reference")
                or ""
            )
            for item in items
        ]

        states = _lead_states(
            references
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to list leads"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "items": [
                _public_lead(
                    item,
                    state=states.get(
                        str(
                            item.get(
                                "reference"
                            )
                            or ""
                        )
                    ),
                )
                for item in items
            ],
            "count": len(items),
        },
    )


def _handle_get_lead(
    event: dict[str, Any],
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    reference = str(
        parameters.get("reference")
        or ""
    ).strip()

    if not reference:
        return _response(
            400,
            {
                "error":
                    "reference_required"
            },
        )

    try:
        item = _lead_record(
            reference
        )

        if not item:
            return _response(
                404,
                {
                    "error":
                        "lead_not_found"
                },
            )

        state = _lead_state(
            reference
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to read lead"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "lead": _public_lead(
                item,
                detail=True,
                state=state,
            ),
        },
    )


def _handle_lead_status_change(
    event: dict[str, Any],
    actor_subject: str,
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    reference = str(
        parameters.get("reference")
        or ""
    ).strip()

    if not reference:
        return _response(
            400,
            {
                "error":
                    "reference_required"
            },
        )

    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {"error": "invalid_json"},
        )

    status = str(
        body.get("status")
        or ""
    ).strip().upper()

    if status not in LEAD_STATUSES:
        return _response(
            400,
            {
                "error":
                    "invalid_lead_status"
            },
        )

    try:
        lead = _lead_record(
            reference
        )

        if not lead:
            return _response(
                404,
                {
                    "error":
                        "lead_not_found"
                },
            )

        state = _set_lead_status(
            reference,
            status,
            actor_subject,
        )

    except ClientError as exc:
        if (
            _aws_error_code(exc)
            ==
            "ConditionalCheckFailedException"
        ):
            return _response(
                409,
                {
                    "error":
                        "converted_lead_locked"
                },
            )

        LOGGER.exception(
            "Lead status update failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    except (
        BotoCoreError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Lead status update failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    LOGGER.info(
        "lead_pipeline action=status_change "
        "actor=%s lead=%s status=%s",
        actor_subject,
        reference,
        status,
    )

    return _response(
        200,
        {
            "lead": _public_lead(
                lead,
                detail=True,
                state=state,
            ),
        },
    )


def _handle_convert_lead(
    event: dict[str, Any],
    actor_subject: str,
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    reference = str(
        parameters.get("reference")
        or ""
    ).strip()

    if not reference:
        return _response(
            400,
            {
                "error":
                    "reference_required"
            },
        )

    try:
        lead = _lead_record(
            reference
        )

        if not lead:
            return _response(
                404,
                {
                    "error":
                        "lead_not_found"
                },
            )

        project, created = (
            _convert_lead(
                lead,
                actor_subject,
            )
        )

    except LeadConversionConflict as exc:
        return _response(
            409,
            {
                "error":
                    str(exc)
            },
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Lead conversion failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    LOGGER.info(
        "lead_pipeline action=convert "
        "actor=%s lead=%s project=%s "
        "created=%s",
        actor_subject,
        reference,
        project.get("projectId"),
        created,
    )

    return _response(
        201 if created else 200,
        {
            "project":
                _public_project(project),
            "created": created,
        },
    )


def _handle_list_projects(
    identity: dict[str, Any],
):
    try:
        projects = _list_projects()

        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            projects = [
                project
                for project in projects
                if _can_view_project(
                    identity,
                    project,
                )
            ]

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to list projects"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "items": [
                _public_project(project)
                for project in projects
            ],
            "count": len(projects),
        },
    )


def _handle_get_project(
    event: dict[str, Any],
    identity: dict[str, Any],
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
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

    try:
        project = _project_record(
            project_id
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to read project"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    if not project:
        return _response(
            404,
            {
                "error":
                    "project_not_found"
            },
        )

    if not _can_view_project(
        identity,
        project,
    ):
        return _response(
            403,
            {
                "error":
                    "project_access_required"
            },
        )

    return _response(
        200,
        {
            "project":
                _public_project(project),
        },
    )

def _handle_list_follow_ups():
    try:
        items = _list_open_follow_ups()

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to list follow-ups"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "items": [
                _public_follow_up(item)
                for item in items
            ],
            "count":
                len(items),
        },
    )


def _handle_list_project_notes(
    event: dict[str, Any],
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
        or ""
    ).strip()

    try:
        if not _project_record(
            project_id
        ):
            return _response(
                404,
                {
                    "error":
                        "project_not_found"
                },
            )

        items = _list_project_children(
            project_id,
            "NOTE#",
            "NOTE",
        )

        items.sort(
            key=lambda item:
                str(
                    item.get("createdAt")
                    or ""
                ),
            reverse=True,
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to list project notes"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "items": [
                _public_note(item)
                for item in items
            ],
            "count":
                len(items),
        },
    )


def _handle_create_project_note(
    event: dict[str, Any],
    actor_subject: str,
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
        or ""
    ).strip()

    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {"error": "invalid_json"},
        )

    category = (
        _normalize_note_category(
            body.get("category")
            or "GENERAL"
        )
    )

    note_body = str(
        body.get("body")
        or ""
    ).strip()

    if not category:
        return _response(
            400,
            {
                "error":
                    "invalid_note_category"
            },
        )

    if not note_body:
        return _response(
            400,
            {
                "error":
                    "note_body_required"
            },
        )

    if len(note_body) > 6000:
        return _response(
            400,
            {
                "error":
                    "note_body_too_long"
            },
        )

    try:
        if not _project_record(
            project_id
        ):
            return _response(
                404,
                {
                    "error":
                        "project_not_found"
                },
            )

        note = _create_project_note(
            project_id,
            category=category,
            body=note_body,
            actor_subject=
                actor_subject,
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Project note creation failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        201,
        {
            "note":
                _public_note(note),
        },
    )


def _handle_update_project_note(
    event: dict[str, Any],
    actor_subject: str,
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
        or ""
    ).strip()

    note_id = str(
        parameters.get("noteId")
        or ""
    ).strip()

    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {"error": "invalid_json"},
        )

    category = (
        _normalize_note_category(
            body.get("category")
            or "GENERAL"
        )
    )

    note_body = str(
        body.get("body")
        or ""
    ).strip()

    if not category:
        return _response(
            400,
            {
                "error":
                    "invalid_note_category"
            },
        )

    if not note_body:
        return _response(
            400,
            {
                "error":
                    "note_body_required"
            },
        )

    if len(note_body) > 6000:
        return _response(
            400,
            {
                "error":
                    "note_body_too_long"
            },
        )

    try:
        current = (
            _project_child_record(
                project_id,
                f"NOTE#{note_id}",
                "NOTE",
            )
        )

        if not current:
            return _response(
                404,
                {
                    "error":
                        "note_not_found"
                },
            )

        updated = _update_project_note(
            current,
            category=category,
            body=note_body,
            actor_subject=
                actor_subject,
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Project note update failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "note":
                _public_note(updated),
        },
    )


def _handle_list_project_follow_ups(
    event: dict[str, Any],
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
        or ""
    ).strip()

    try:
        if not _project_record(
            project_id
        ):
            return _response(
                404,
                {
                    "error":
                        "project_not_found"
                },
            )

        items = _list_project_children(
            project_id,
            "FOLLOWUP#",
            "FOLLOW_UP",
        )

        items.sort(
            key=lambda item: (
                str(
                    item.get("status")
                    or ""
                )
                != "OPEN",
                str(
                    item.get("dueAt")
                    or ""
                ),
            )
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to list follow-ups"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "items": [
                _public_follow_up(item)
                for item in items
            ],
            "count":
                len(items),
        },
    )


def _handle_create_project_follow_up(
    event: dict[str, Any],
    actor_subject: str,
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
        or ""
    ).strip()

    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {"error": "invalid_json"},
        )

    title = str(
        body.get("title")
        or ""
    ).strip()

    details = str(
        body.get("details")
        or ""
    ).strip()

    assignee_user_id = str(
        body.get("assigneeUserId")
        or ""
    ).strip()

    due_at = _normalize_due_at(
        body.get("dueAt")
    )

    if not title:
        return _response(
            400,
            {
                "error":
                    "follow_up_title_required"
            },
        )

    if len(title) > 180:
        return _response(
            400,
            {
                "error":
                    "follow_up_title_too_long"
            },
        )

    if len(details) > 4000:
        return _response(
            400,
            {
                "error":
                    "follow_up_details_too_long"
            },
        )

    if not due_at:
        return _response(
            400,
            {
                "error":
                    "invalid_follow_up_due_at"
            },
        )

    try:
        if not _project_record(
            project_id
        ):
            return _response(
                404,
                {
                    "error":
                        "project_not_found"
                },
            )

        if assignee_user_id:
            membership = (
                _project_member_record(
                    project_id,
                    assignee_user_id,
                )
            )

            profile = _staff_record(
                assignee_user_id
            )

            if (
                not membership
                or membership.get(
                    "membershipStatus"
                )
                != "ACTIVE"
                or not profile
                or profile.get("status")
                != "ACTIVE"
            ):
                return _response(
                    409,
                    {
                        "error":
                            "assignee_not_active_project_member"
                    },
                )

        follow_up = (
            _create_project_follow_up(
                project_id,
                title=title,
                details=details,
                assignee_user_id=
                    assignee_user_id,
                due_at=due_at,
                actor_subject=
                    actor_subject,
            )
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Follow-up creation failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        201,
        {
            "followUp":
                _public_follow_up(
                    follow_up
                ),
        },
    )


def _handle_update_project_follow_up(
    event: dict[str, Any],
    actor_subject: str,
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
        or ""
    ).strip()

    follow_up_id = str(
        parameters.get("followUpId")
        or ""
    ).strip()

    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {"error": "invalid_json"},
        )

    try:
        current = (
            _project_child_record(
                project_id,
                (
                    "FOLLOWUP#"
                    f"{follow_up_id}"
                ),
                "FOLLOW_UP",
            )
        )

        if not current:
            return _response(
                404,
                {
                    "error":
                        "follow_up_not_found"
                },
            )

        title = str(
            body.get(
                "title",
                current.get("title")
                or "",
            )
            or ""
        ).strip()

        details = str(
            body.get(
                "details",
                current.get("details")
                or "",
            )
            or ""
        ).strip()

        status = (
            _normalize_follow_up_status(
                body.get(
                    "status",
                    current.get("status")
                    or "OPEN",
                )
            )
        )

        assignee_user_id = str(
            body.get(
                "assigneeUserId",
                current.get(
                    "assigneeUserId"
                )
                or "",
            )
            or ""
        ).strip()

        due_at = _normalize_due_at(
            body.get(
                "dueAt",
                current.get("dueAt")
                or "",
            )
        )

        if not title:
            return _response(
                400,
                {
                    "error":
                        "follow_up_title_required"
                },
            )

        if not status:
            return _response(
                400,
                {
                    "error":
                        "invalid_follow_up_status"
                },
            )

        if not due_at:
            return _response(
                400,
                {
                    "error":
                        "invalid_follow_up_due_at"
                },
            )

        if assignee_user_id:
            membership = (
                _project_member_record(
                    project_id,
                    assignee_user_id,
                )
            )

            profile = _staff_record(
                assignee_user_id
            )

            if (
                not membership
                or membership.get(
                    "membershipStatus"
                )
                != "ACTIVE"
                or not profile
                or profile.get("status")
                != "ACTIVE"
            ):
                return _response(
                    409,
                    {
                        "error":
                            "assignee_not_active_project_member"
                    },
                )

        updated = (
            _update_project_follow_up(
                current,
                title=title,
                details=details,
                status=status,
                assignee_user_id=
                    assignee_user_id,
                due_at=due_at,
                actor_subject=
                    actor_subject,
            )
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Follow-up update failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "followUp":
                _public_follow_up(
                    updated
                ),
        },
    )


def _handle_list_project_activity(
    event: dict[str, Any],
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
        or ""
    ).strip()

    try:
        if not _project_record(
            project_id
        ):
            return _response(
                404,
                {
                    "error":
                        "project_not_found"
                },
            )

        items = _list_project_activity(
            project_id
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Activity listing failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "items": [
                _public_activity(item)
                for item in items
            ],
            "count":
                len(items),
        },
    )


def _handle_list_tasks():
    try:
        tasks = _list_all_tasks()

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to list tasks"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "items": [
                _public_task(task)
                for task in tasks
            ],
            "count": len(tasks),
        },
    )


def _handle_list_project_tasks(
    event: dict[str, Any],
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
        or ""
    ).strip()

    try:
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

        tasks = _list_project_tasks(
            project_id
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to list project tasks"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "items": [
                _public_task(task)
                for task in tasks
            ],
            "count": len(tasks),
        },
    )


def _handle_create_project_task(
    event: dict[str, Any],
    actor_subject: str,
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
        or ""
    ).strip()

    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {"error": "invalid_json"},
        )

    title = str(
        body.get("title")
        or ""
    ).strip()

    description = str(
        body.get("description")
        or ""
    ).strip()

    status = (
        _normalize_task_status(
            body.get("status")
            or "TODO"
        )
    )

    priority = (
        _normalize_task_priority(
            body.get("priority")
            or "NORMAL"
        )
    )

    assignee_user_id = str(
        body.get("assigneeUserId")
        or ""
    ).strip()

    due_date = str(
        body.get("dueDate")
        or ""
    ).strip()

    if not title:
        return _response(
            400,
            {
                "error":
                    "task_title_required"
            },
        )

    if len(title) > 180:
        return _response(
            400,
            {
                "error":
                    "task_title_too_long"
            },
        )

    if not status:
        return _response(
            400,
            {
                "error":
                    "invalid_task_status"
            },
        )

    if not priority:
        return _response(
            400,
            {
                "error":
                    "invalid_task_priority"
            },
        )

    try:
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

        if assignee_user_id:
            membership = (
                _project_member_record(
                    project_id,
                    assignee_user_id,
                )
            )

            if (
                not membership
                or membership.get(
                    "membershipStatus"
                )
                != "ACTIVE"
            ):
                return _response(
                    409,
                    {
                        "error":
                            "assignee_not_project_member"
                    },
                )

        task = _create_project_task(
            project_id,
            title=title,
            description=description,
            status=status,
            priority=priority,
            assignee_user_id=
                assignee_user_id,
            due_date=due_date,
            actor_subject=
                actor_subject,
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Task creation failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    LOGGER.info(
        "task action=create "
        "actor=%s project=%s task=%s",
        actor_subject,
        project_id,
        task.get("taskId"),
    )

    return _response(
        201,
        {
            "task":
                _public_task(task),
        },
    )


def _handle_update_project_task(
    event: dict[str, Any],
    actor_subject: str,
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
        or ""
    ).strip()

    task_id = str(
        parameters.get("taskId")
        or ""
    ).strip()

    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {"error": "invalid_json"},
        )

    title = (
        str(body["title"]).strip()
        if "title" in body
        else None
    )

    description = (
        str(
            body["description"]
            or ""
        ).strip()
        if "description" in body
        else None
    )

    status = None

    if "status" in body:
        status = (
            _normalize_task_status(
                body.get("status")
            )
        )

        if not status:
            return _response(
                400,
                {
                    "error":
                        "invalid_task_status"
                },
            )

    priority = None

    if "priority" in body:
        priority = (
            _normalize_task_priority(
                body.get("priority")
            )
        )

        if not priority:
            return _response(
                400,
                {
                    "error":
                        "invalid_task_priority"
                },
            )

    assignee_user_id = (
        str(
            body.get(
                "assigneeUserId"
            )
            or ""
        ).strip()
        if "assigneeUserId" in body
        else None
    )

    due_date = (
        str(
            body.get("dueDate")
            or ""
        ).strip()
        if "dueDate" in body
        else None
    )

    if title is not None:
        if not title:
            return _response(
                400,
                {
                    "error":
                        "task_title_required"
                },
            )

        if len(title) > 180:
            return _response(
                400,
                {
                    "error":
                        "task_title_too_long"
                },
            )

    try:
        task = _task_record(
            project_id,
            task_id,
        )

        if not task:
            return _response(
                404,
                {
                    "error":
                        "task_not_found"
                },
            )

        if (
            assignee_user_id is not None
            and assignee_user_id
        ):
            membership = (
                _project_member_record(
                    project_id,
                    assignee_user_id,
                )
            )

            if (
                not membership
                or membership.get(
                    "membershipStatus"
                )
                != "ACTIVE"
            ):
                return _response(
                    409,
                    {
                        "error":
                            "assignee_not_project_member"
                    },
                )

        updated = (
            _update_project_task(
                task,
                title=title,
                description=description,
                status=status,
                priority=priority,
                assignee_user_id=
                    assignee_user_id,
                due_date=due_date,
                actor_subject=
                    actor_subject,
            )
        )

    except ClientError as exc:
        if (
            _aws_error_code(exc)
            ==
            "ConditionalCheckFailedException"
        ):
            return _response(
                409,
                {
                    "error":
                        "task_update_conflict"
                },
            )

        LOGGER.exception(
            "Task update failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    except (
        BotoCoreError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Task update failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "task":
                _public_task(updated),
        },
    )


def _handle_list_project_members(
    event: dict[str, Any],
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
        or ""
    ).strip()

    try:
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

        members = _list_project_members(
            project_id
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to list project members"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "items": members,
            "count": len(members),
        },
    )


def _handle_assign_project_member(
    event: dict[str, Any],
    actor_subject: str,
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
        or ""
    ).strip()

    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {"error": "invalid_json"},
        )

    user_id = str(
        body.get("userId")
        or ""
    ).strip()

    project_role = (
        _normalize_project_role(
            body.get("projectRole")
        )
    )

    if not user_id:
        return _response(
            400,
            {"error": "user_id_required"},
        )

    if not project_role:
        return _response(
            400,
            {
                "error":
                    "invalid_project_role"
            },
        )

    try:
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

        staff = _staff_record(
            user_id
        )

        if not staff:
            return _response(
                404,
                {
                    "error":
                        "staff_not_found"
                },
            )

        if (
            str(
                staff.get("status")
                or ""
            ).upper()
            != "ACTIVE"
        ):
            return _response(
                409,
                {
                    "error":
                        "staff_not_active"
                },
            )

        membership, changed = (
            _assign_project_member(
                project_id,
                user_id,
                project_role,
                actor_subject,
            )
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Project assignment failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    LOGGER.info(
        "project_membership action=assign "
        "actor=%s project=%s user=%s role=%s "
        "changed=%s",
        actor_subject,
        project_id,
        user_id,
        project_role,
        changed,
    )

    return _response(
        201 if changed else 200,
        {
            "membership":
                _public_project_member(
                    membership,
                    staff,
                ),
            "changed": changed,
        },
    )


def _handle_project_member_role_change(
    event: dict[str, Any],
    actor_subject: str,
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
        or ""
    ).strip()

    user_id = str(
        parameters.get("userId")
        or ""
    ).strip()

    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {"error": "invalid_json"},
        )

    project_role = (
        _normalize_project_role(
            body.get("projectRole")
        )
    )

    if not project_role:
        return _response(
            400,
            {
                "error":
                    "invalid_project_role"
            },
        )

    try:
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

        membership = (
            _project_member_record(
                project_id,
                user_id,
            )
        )

        if (
            not membership
            or membership.get(
                "membershipStatus"
            )
            != "ACTIVE"
        ):
            return _response(
                404,
                {
                    "error":
                        "membership_not_found"
                },
            )

        updated = (
            _change_project_member_role(
                project_id,
                user_id,
                project_role,
                actor_subject,
            )
        )

        staff = _staff_record(
            user_id
        )

    except ClientError as exc:
        if (
            _aws_error_code(exc)
            ==
            "ConditionalCheckFailedException"
        ):
            return _response(
                409,
                {
                    "error":
                        "membership_not_active"
                },
            )

        LOGGER.exception(
            "Membership role update failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    except (
        BotoCoreError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Membership role update failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "membership":
                _public_project_member(
                    updated,
                    staff,
                ),
        },
    )


def _handle_unassign_project_member(
    event: dict[str, Any],
    actor_subject: str,
):
    parameters = (
        event.get("pathParameters")
        or {}
    )

    project_id = str(
        parameters.get("projectId")
        or ""
    ).strip()

    user_id = str(
        parameters.get("userId")
        or ""
    ).strip()

    try:
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

        membership, changed = (
            _unassign_project_member(
                project_id,
                user_id,
                actor_subject,
            )
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Project unassignment failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    if not membership:
        return _response(
            404,
            {
                "error":
                    "membership_not_found"
            },
        )

    LOGGER.info(
        "project_membership action=unassign "
        "actor=%s project=%s user=%s "
        "changed=%s",
        actor_subject,
        project_id,
        user_id,
        changed,
    )

    return _response(
        200,
        {
            "membership": {
                "userId": user_id,
                "projectId": project_id,
                "projectRole": str(
                    membership.get(
                        "projectRole"
                    )
                    or ""
                ),
                "membershipStatus": str(
                    membership.get(
                        "membershipStatus"
                    )
                    or ""
                ),
            },
            "changed": changed,
        },
    )


def _public_directory_member(
    staff: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": _staff_id(staff),
        "displayName": str(
            staff.get("displayName")
            or ""
        ),
        "email": str(
            staff.get("email")
            or ""
        ),
        "organizationRole": str(
            staff.get("organizationRole")
            or ""
        ),
        "status": str(
            staff.get("status")
            or ""
        ),
    }


def _handle_staff_directory():
    try:
        staff = _list_staff_records()

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to list staff directory"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    active = [
        item
        for item in staff
        if (
            str(
                item.get("status")
                or ""
            ).upper()
            == "ACTIVE"
        )
    ]

    return _response(
        200,
        {
            "items": [
                _public_directory_member(
                    item
                )
                for item in active
            ],
            "count": len(active),
        },
    )


def _handle_list_staff():
    try:
        staff = _list_staff_records()

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to list staff"
        )

        return _response(
            503,
            {"error": "temporarily_unavailable"},
        )

    return _response(
        200,
        {
            "items": [
                _public_staff(item)
                for item in staff
            ],
            "count": len(staff),
        },
    )


def _handle_create_staff(
    event: dict[str, Any],
    actor_subject: str,
):
    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {"error": "invalid_json"},
        )

    email = _normalize_email(
        body.get("email")
    )

    display_name = (
        _normalize_display_name(
            body.get("displayName")
        )
    )

    role = _normalize_role(
        body.get(
            "role",
            "WORKER",
        )
    )

    locale = _normalize_locale(
        body.get(
            "preferredLocale",
            "en",
        )
    )

    if not email:
        return _response(
            400,
            {"error": "invalid_email"},
        )

    if not display_name:
        return _response(
            400,
            {"error": "invalid_display_name"},
        )

    if not role:
        return _response(
            400,
            {"error": "invalid_role"},
        )

    if not locale:
        return _response(
            400,
            {"error": "invalid_locale"},
        )

    try:
        staff = _create_staff(
            actor_subject,
            display_name,
            email,
            role,
            locale,
        )

    except ClientError as exc:
        code = _aws_error_code(exc)

        if code in {
            "UsernameExistsException",
            "AliasExistsException",
        }:
            return _response(
                409,
                {
                    "error":
                        "staff_already_exists"
                },
            )

        LOGGER.exception(
            "Cognito staff creation failed "
            "code=%s",
            code,
        )

        return _response(
            503,
            {"error": "temporarily_unavailable"},
        )

    except (
        BotoCoreError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Staff creation failed"
        )

        return _response(
            503,
            {"error": "temporarily_unavailable"},
        )

    return _response(
        201,
        {
            "staff": _public_staff(staff),
            "invitationSent": True,
        },
    )


def _handle_my_preferences(
    event: dict[str, Any],
    identity: dict[str, Any],
):
    if identity["role"] not in {
        "OWNER",
        "MANAGER",
    }:
        return _response(
            403,
            {
                "error":
                    "lead_notifications_not_available_for_role"
            },
        )

    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {"error": "invalid_json"},
        )

    enabled = body.get(
        "newLeadEmailNotifications"
    )

    if not isinstance(enabled, bool):
        return _response(
            400,
            {
                "error":
                    "new_lead_email_notifications_boolean_required"
            },
        )

    subject = identity["subject"]
    now = _utcnow()

    try:
        response = (
            _ops_table().update_item(
                Key={
                    "PK":
                        f"USER#{subject}",
                    "SK":
                        "PROFILE",
                },
                UpdateExpression=(
                    "SET "
                    "newLeadEmailNotifications = :enabled, "
                    "updatedAt = :updated, "
                    "updatedBy = :actor"
                ),
                ExpressionAttributeValues={
                    ":enabled":
                        enabled,
                    ":updated":
                        now,
                    ":actor":
                        subject,
                },
                ConditionExpression=(
                    "attribute_exists(PK) "
                    "AND attribute_exists(SK)"
                ),
                ReturnValues="ALL_NEW",
            )
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Notification preference update failed"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    updated = response[
        "Attributes"
    ]

    return _response(
        200,
        {
            "ok": True,
            "user":
                _public_staff(updated),
        },
    )


def _target_user_id(
    event: dict[str, Any],
) -> str:
    path_parameters = (
        event.get("pathParameters")
        or {}
    )

    return str(
        path_parameters.get("userId")
        or ""
    ).strip()


def _handle_role_change(
    event: dict[str, Any],
    actor_subject: str,
):
    subject = _target_user_id(event)

    if not subject:
        return _response(
            400,
            {"error": "user_id_required"},
        )

    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {"error": "invalid_json"},
        )

    role = _normalize_role(
        body.get("role")
    )

    if not role:
        return _response(
            400,
            {"error": "invalid_role"},
        )

    if (
        subject == actor_subject
        and role != "OWNER"
    ):
        return _response(
            409,
            {
                "error":
                    "cannot_change_own_role"
            },
        )

    try:
        staff = _staff_record(subject)

        if not staff:
            return _response(
                404,
                {"error": "staff_not_found"},
            )

        current_role = str(
            staff.get("organizationRole")
            or ""
        ).upper()

        if current_role == role:
            synced = _sync_cognito_role(
                staff,
                subject,
                role,
            )

            status_code = (
                200 if synced else 202
            )

            return _response(
                status_code,
                {
                    "staff":
                        _public_staff(staff),
                    "identitySync":
                        (
                            "OK"
                            if synced
                            else "PENDING"
                        ),
                },
            )

        updated, synced = (
            _set_staff_role(
                actor_subject,
                subject,
                staff,
                role,
            )
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Staff role update failed"
        )

        return _response(
            503,
            {"error": "temporarily_unavailable"},
        )

    return _response(
        200 if synced else 202,
        {
            "staff": _public_staff(
                updated
            ),
            "identitySync": (
                "OK"
                if synced
                else "PENDING"
            ),
        },
    )


def _handle_status_change(
    event: dict[str, Any],
    actor_subject: str,
):
    subject = _target_user_id(event)

    if not subject:
        return _response(
            400,
            {"error": "user_id_required"},
        )

    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {"error": "invalid_json"},
        )

    status = str(
        body.get("status")
        or ""
    ).strip().upper()

    if status not in STAFF_STATUSES:
        return _response(
            400,
            {"error": "invalid_status"},
        )

    if (
        subject == actor_subject
        and status == "DISABLED"
    ):
        return _response(
            409,
            {
                "error":
                    "cannot_disable_self"
            },
        )

    try:
        staff = _staff_record(subject)

        if not staff:
            return _response(
                404,
                {"error": "staff_not_found"},
            )

        updated, synced = (
            _set_staff_status(
                actor_subject,
                subject,
                staff,
                status,
            )
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Staff status update failed"
        )

        return _response(
            503,
            {"error": "temporarily_unavailable"},
        )

    return _response(
        200 if synced else 202,
        {
            "staff": _public_staff(
                updated
            ),
            "identitySync": (
                "OK"
                if synced
                else "PENDING"
            ),
        },
    )



def _normalize_vendor_status(
    value: Any,
) -> str | None:
    status = (
        str(value or "")
        .strip()
        .upper()
        .replace(" ", "_")
        .replace("-", "_")
    )

    if status not in VENDOR_STATUSES:
        return None

    return status


def _normalize_vendor_category(
    value: Any,
) -> str | None:
    category = (
        str(value or "")
        .strip()
        .upper()
        .replace(" ", "_")
        .replace("-", "_")
    )

    if category not in VENDOR_CATEGORIES:
        return None

    return category


def _normalize_vendor_services(
    value: Any,
) -> list[str] | None:
    if value is None:
        return []

    if isinstance(value, str):
        raw_items = (
            value
            .replace("\r", "\n")
            .replace(",", "\n")
            .splitlines()
        )

    elif isinstance(value, list):
        raw_items = value

    else:
        return None

    result = []
    seen = set()

    for raw_item in raw_items:
        service = str(
            raw_item or ""
        ).strip()

        if not service:
            continue

        if len(service) > 120:
            return None

        key = service.casefold()

        if key in seen:
            continue

        seen.add(key)
        result.append(service)

        if len(result) > 20:
            return None

    return result


def _vendor_request_fields(
    body: dict[str, Any],
    *,
    partial: bool,
) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise ValueError(
            "invalid_json"
        )

    result: dict[str, Any] = {}

    text_fields = {
        "name": 160,
        "contactPerson": 120,
        "phone": 60,
        "whatsapp": 60,
        "email": 254,
        "city": 120,
        "pricingNotes": 4000,
        "internalNotes": 8000,
    }

    for field, max_length in (
        text_fields.items()
    ):
        if (
            partial
            and field not in body
        ):
            continue

        value = str(
            body.get(field)
            or ""
        ).strip()

        if len(value) > max_length:
            raise ValueError(
                f"{field}_too_long"
            )

        if (
            field == "name"
            and not value
        ):
            raise ValueError(
                "vendor_name_required"
            )

        result[field] = value

    if (
        not partial
        or "category" in body
    ):
        category = (
            _normalize_vendor_category(
                body.get("category")
            )
        )

        if not category:
            raise ValueError(
                "invalid_vendor_category"
            )

        result["category"] = category

    if (
        not partial
        or "status" in body
    ):
        raw_status = (
            body.get("status")
            if "status" in body
            else "ACTIVE"
        )

        status = (
            _normalize_vendor_status(
                raw_status
            )
        )

        if not status:
            raise ValueError(
                "invalid_vendor_status"
            )

        result["status"] = status

    if (
        not partial
        or "services" in body
    ):
        services = (
            _normalize_vendor_services(
                body.get("services")
            )
        )

        if services is None:
            raise ValueError(
                "invalid_vendor_services"
            )

        result["services"] = services

    return result


def _public_vendor(
    item: dict[str, Any],
) -> dict[str, Any]:
    services = item.get("services")

    if not isinstance(
        services,
        list,
    ):
        services = []

    return {
        "vendorId": str(
            item.get("vendorId")
            or ""
        ),
        "name": str(
            item.get("name")
            or ""
        ),
        "category": str(
            item.get("category")
            or ""
        ),
        "contactPerson": str(
            item.get("contactPerson")
            or ""
        ),
        "phone": str(
            item.get("phone")
            or ""
        ),
        "whatsapp": str(
            item.get("whatsapp")
            or ""
        ),
        "email": str(
            item.get("email")
            or ""
        ),
        "city": str(
            item.get("city")
            or ""
        ),
        "services": [
            str(service)
            for service in services
            if str(service).strip()
        ],
        "pricingNotes": str(
            item.get("pricingNotes")
            or ""
        ),
        "internalNotes": str(
            item.get("internalNotes")
            or ""
        ),
        "status": str(
            item.get("status")
            or "ACTIVE"
        ),
        "createdAt": str(
            item.get("createdAt")
            or ""
        ),
        "createdBy": str(
            item.get("createdBy")
            or ""
        ),
        "updatedAt": str(
            item.get("updatedAt")
            or ""
        ),
        "updatedBy": str(
            item.get("updatedBy")
            or ""
        ),
    }


def _vendor_name_index_key(
    name: str,
    vendor_id: str,
) -> str:
    return (
        f"NAME#{name.casefold()}"
        f"#VENDOR#{vendor_id}"
    )


def _vendor_record(
    vendor_id: str,
) -> dict[str, Any] | None:
    response = _ops_table().get_item(
        Key={
            "PK":
                f"VENDOR#{vendor_id}",
            "SK":
                "PROFILE",
        },
        ConsistentRead=True,
    )

    item = response.get("Item")

    if (
        not isinstance(item, dict)
        or item.get("recordType")
            != "VENDOR"
    ):
        return None

    return item


def _list_vendors(
) -> list[dict[str, Any]]:
    items = []

    kwargs: dict[str, Any] = {
        "IndexName": "GSI1",
        "KeyConditionExpression":
            "GSI1PK = :pk",
        "ExpressionAttributeValues": {
            ":pk":
                "DIRECTORY#VENDORS",
        },
    }

    while True:
        response = (
            _ops_table().query(
                **kwargs
            )
        )

        items.extend(
            item
            for item in (
                response.get("Items")
                or []
            )
            if (
                isinstance(item, dict)
                and item.get(
                    "recordType"
                )
                == "VENDOR"
            )
        )

        last_key = response.get(
            "LastEvaluatedKey"
        )

        if not last_key:
            break

        kwargs[
            "ExclusiveStartKey"
        ] = last_key

    return sorted(
        items,
        key=lambda item: (
            str(
                item.get("name")
                or ""
            ).casefold(),
            str(
                item.get("vendorId")
                or ""
            ),
        ),
    )


def _vendor_audit_item(
    vendor_id: str,
    *,
    action: str,
    actor_subject: str,
    before: dict[str, Any] | None,
    after: dict[str, Any],
    changed_fields: list[str],
    now: str,
) -> dict[str, Any]:
    audit_id = _new_record_id(
        "AUD"
    )

    return {
        "PK":
            f"VENDOR#{vendor_id}",
        "SK":
            (
                f"AUDIT#{now}"
                f"#{audit_id}"
            ),
        "recordType":
            "VENDOR_AUDIT",
        "auditId":
            audit_id,
        "vendorId":
            vendor_id,
        "action":
            action,
        "actorUserId":
            actor_subject,
        "changedFields":
            changed_fields,
        "before":
            before or {},
        "after":
            after,
        "createdAt":
            now,
    }


def _create_vendor(
    fields: dict[str, Any],
    actor_subject: str,
) -> dict[str, Any]:
    vendor_id = _new_record_id(
        "VEN"
    )

    now = _utcnow()

    item = {
        "PK":
            f"VENDOR#{vendor_id}",
        "SK":
            "PROFILE",
        "recordType":
            "VENDOR",
        "vendorId":
            vendor_id,
        **fields,
        "createdAt":
            now,
        "createdBy":
            actor_subject,
        "updatedAt":
            now,
        "updatedBy":
            actor_subject,
        "GSI1PK":
            "DIRECTORY#VENDORS",
        "GSI1SK":
            _vendor_name_index_key(
                fields["name"],
                vendor_id,
            ),
    }

    public_after = (
        _public_vendor(item)
    )

    audit = _vendor_audit_item(
        vendor_id,
        action="VENDOR_CREATED",
        actor_subject=actor_subject,
        before=None,
        after=public_after,
        changed_fields=sorted(
            fields.keys()
        ),
        now=now,
    )

    boto3.client(
        "dynamodb"
    ).transact_write_items(
        TransactItems=[
            {
                "Put": {
                    "TableName":
                        OPS_TABLE_NAME,
                    "Item":
                        _serialize_map(
                            item
                        ),
                    "ConditionExpression": (
                        "attribute_not_exists("
                        "PK)"
                    ),
                }
            },
            {
                "Put": {
                    "TableName":
                        OPS_TABLE_NAME,
                    "Item":
                        _serialize_map(
                            audit
                        ),
                    "ConditionExpression": (
                        "attribute_not_exists("
                        "PK) "
                        "AND "
                        "attribute_not_exists("
                        "SK)"
                    ),
                }
            },
        ]
    )

    return item


def _update_vendor(
    current: dict[str, Any],
    changes: dict[str, Any],
    actor_subject: str,
) -> tuple[
    dict[str, Any],
    bool,
]:
    changed_fields = [
        field
        for field, value in (
            changes.items()
        )
        if current.get(field) != value
    ]

    if not changed_fields:
        return current, False

    now = _utcnow()

    updated = {
        **current,
        **changes,
        "updatedAt":
            now,
        "updatedBy":
            actor_subject,
    }

    vendor_id = str(
        current.get("vendorId")
        or ""
    )

    updated["GSI1PK"] = (
        "DIRECTORY#VENDORS"
    )

    updated["GSI1SK"] = (
        _vendor_name_index_key(
            str(
                updated.get("name")
                or ""
            ),
            vendor_id,
        )
    )

    before_public = (
        _public_vendor(current)
    )

    after_public = (
        _public_vendor(updated)
    )

    action = (
        "VENDOR_STATUS_CHANGED"
        if "status" in changed_fields
        else "VENDOR_UPDATED"
    )

    audit = _vendor_audit_item(
        vendor_id,
        action=action,
        actor_subject=actor_subject,
        before=before_public,
        after=after_public,
        changed_fields=sorted(
            changed_fields
        ),
        now=now,
    )

    expected_updated = str(
        current.get("updatedAt")
        or ""
    )

    condition = (
        "recordType = :vendor_type"
    )

    condition_values = {
        ":vendor_type":
            "VENDOR",
    }

    if expected_updated:
        condition += (
            " AND "
            "updatedAt = "
            ":expected_updated"
        )

        condition_values[
            ":expected_updated"
        ] = expected_updated

    try:
        boto3.client(
            "dynamodb"
        ).transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName":
                            OPS_TABLE_NAME,
                        "Item":
                            _serialize_map(
                                updated
                            ),
                        "ConditionExpression":
                            condition,
                        "ExpressionAttributeValues":
                            _serialize_map(
                                condition_values
                            ),
                    }
                },
                {
                    "Put": {
                        "TableName":
                            OPS_TABLE_NAME,
                        "Item":
                            _serialize_map(
                                audit
                            ),
                        "ConditionExpression": (
                            "attribute_not_exists("
                            "PK) "
                            "AND "
                            "attribute_not_exists("
                            "SK)"
                        ),
                    }
                },
            ]
        )

    except ClientError as exc:
        if (
            _aws_error_code(exc)
            ==
            "TransactionCanceledException"
        ):
            raise VendorWriteConflict(
                "vendor_write_conflict"
            ) from exc

        raise

    return updated, True


def _vendor_id_from_event(
    event: dict[str, Any],
) -> str:
    parameters = (
        event.get("pathParameters")
        or {}
    )

    vendor_id = str(
        parameters.get("vendorId")
        or ""
    ).strip().upper()

    if not vendor_id.startswith(
        "VEN-"
    ):
        return ""

    return vendor_id


def _handle_list_vendors():
    try:
        vendors = _list_vendors()

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to list vendors"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "items": [
                _public_vendor(vendor)
                for vendor in vendors
            ],
            "count":
                len(vendors),
        },
    )


def _handle_get_vendor(
    event: dict[str, Any],
):
    vendor_id = (
        _vendor_id_from_event(
            event
        )
    )

    if not vendor_id:
        return _response(
            400,
            {
                "error":
                    "vendor_id_required"
            },
        )

    try:
        vendor = _vendor_record(
            vendor_id
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to get vendor"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    if not vendor:
        return _response(
            404,
            {
                "error":
                    "vendor_not_found"
            },
        )

    return _response(
        200,
        {
            "vendor":
                _public_vendor(
                    vendor
                )
        },
    )


def _handle_create_vendor(
    event: dict[str, Any],
    identity: dict[str, Any],
):
    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {
                "error":
                    "invalid_json"
            },
        )

    try:
        fields = (
            _vendor_request_fields(
                body,
                partial=False,
            )
        )

    except ValueError as exc:
        return _response(
            400,
            {
                "error":
                    str(exc)
            },
        )

    if (
        fields["status"]
        != "ACTIVE"
        and identity["role"]
        not in {
            "OWNER",
            "MANAGER",
        }
    ):
        return _response(
            403,
            {
                "error":
                    "manager_or_owner_required"
            },
        )

    try:
        vendor = _create_vendor(
            fields,
            identity["subject"],
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to create vendor"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        201,
        {
            "vendor":
                _public_vendor(
                    vendor
                )
        },
    )


def _handle_update_vendor(
    event: dict[str, Any],
    identity: dict[str, Any],
):
    vendor_id = (
        _vendor_id_from_event(
            event
        )
    )

    if not vendor_id:
        return _response(
            400,
            {
                "error":
                    "vendor_id_required"
            },
        )

    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {
                "error":
                    "invalid_json"
            },
        )

    try:
        changes = (
            _vendor_request_fields(
                body,
                partial=True,
            )
        )

    except ValueError as exc:
        return _response(
            400,
            {
                "error":
                    str(exc)
            },
        )

    try:
        current = _vendor_record(
            vendor_id
        )

        if not current:
            return _response(
                404,
                {
                    "error":
                        "vendor_not_found"
                },
            )

        requested_status = (
            changes.get("status")
        )

        current_status = str(
            current.get("status")
            or "ACTIVE"
        )

        if (
            requested_status
            and requested_status
                != current_status
            and identity["role"]
                not in {
                    "OWNER",
                    "MANAGER",
                }
        ):
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        updated, changed = (
            _update_vendor(
                current,
                changes,
                identity["subject"],
            )
        )

    except VendorWriteConflict:
        return _response(
            409,
            {
                "error":
                    "vendor_changed_refresh"
            },
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to update vendor"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "vendor":
                _public_vendor(
                    updated
                ),
            "changed":
                changed,
        },
    )




def _normalize_project_vendor_operational_status(
    value: Any,
) -> str | None:
    status = (
        str(value or "")
        .strip()
        .upper()
        .replace(" ", "_")
        .replace("-", "_")
    )

    if (
        status
        not in
        PROJECT_VENDOR_OPERATIONAL_STATUSES
    ):
        return None

    return status


def _normalize_project_vendor_booking_status(
    value: Any,
) -> str | None:
    status = (
        str(value or "")
        .strip()
        .upper()
        .replace(" ", "_")
        .replace("-", "_")
    )

    if (
        status
        not in
        PROJECT_VENDOR_BOOKING_STATUSES
    ):
        return None

    return status


def _normalize_project_vendor_amount(
    value: Any,
) -> int | None:
    if (
        value is None
        or value == ""
    ):
        return 0

    if isinstance(value, bool):
        return None

    if isinstance(value, float):
        if not value.is_integer():
            return None

    if isinstance(value, str):
        raw = value.strip()

        if not raw.isdigit():
            return None

    try:
        amount = int(value)

    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if (
        amount < 0
        or amount > 1_000_000_000_000
    ):
        return None

    return amount


def _project_vendor_request_fields(
    body: dict[str, Any],
    *,
    partial: bool,
) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise ValueError(
            "invalid_json"
        )

    result: dict[str, Any] = {}

    if "category" in body:
        raise ValueError(
            "project_vendor_category_immutable"
        )

    if (
        not partial
        or "operationalStatus" in body
    ):
        raw_status = (
            body.get(
                "operationalStatus"
            )
            if "operationalStatus" in body
            else "SHORTLISTED"
        )

        status = (
            _normalize_project_vendor_operational_status(
                raw_status
            )
        )

        if not status:
            raise ValueError(
                "invalid_project_vendor_status"
            )

        result[
            "operationalStatus"
        ] = status

    if (
        not partial
        or "bookingStatus" in body
    ):
        raw_booking = (
            body.get("bookingStatus")
            if "bookingStatus" in body
            else "NOT_STARTED"
        )

        booking_status = (
            _normalize_project_vendor_booking_status(
                raw_booking
            )
        )

        if not booking_status:
            raise ValueError(
                "invalid_project_vendor_booking_status"
            )

        result[
            "bookingStatus"
        ] = booking_status

    for field in (
        "quoteAmount",
        "depositAmount",
    ):
        if (
            partial
            and field not in body
        ):
            continue

        amount = (
            _normalize_project_vendor_amount(
                body.get(field)
            )
        )

        if amount is None:
            raise ValueError(
                f"invalid_{field}"
            )

        result[field] = amount

    if (
        not partial
        or "notes" in body
    ):
        notes = str(
            body.get("notes")
            or ""
        ).strip()

        if len(notes) > 8000:
            raise ValueError(
                "project_vendor_notes_too_long"
            )

        result["notes"] = notes

    return result


def _public_project_vendor(
    item: dict[str, Any],
    vendor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "projectId": str(
            item.get("projectId")
            or ""
        ),
        "vendorId": str(
            item.get("vendorId")
            or ""
        ),
        "relationshipStatus": str(
            item.get(
                "relationshipStatus"
            )
            or "ACTIVE"
        ),
        "category": str(
            item.get("category")
            or ""
        ),
        "operationalStatus": str(
            item.get(
                "operationalStatus"
            )
            or "SHORTLISTED"
        ),
        "bookingStatus": str(
            item.get("bookingStatus")
            or "NOT_STARTED"
        ),
        "quoteAmount": int(
            item.get("quoteAmount")
            or 0
        ),
        "depositAmount": int(
            item.get("depositAmount")
            or 0
        ),
        "notes": str(
            item.get("notes")
            or ""
        ),
        "linkedAt": str(
            item.get("linkedAt")
            or ""
        ),
        "linkedBy": str(
            item.get("linkedBy")
            or ""
        ),
        "unlinkedAt": str(
            item.get("unlinkedAt")
            or ""
        ),
        "unlinkedBy": str(
            item.get("unlinkedBy")
            or ""
        ),
        "createdAt": str(
            item.get("createdAt")
            or ""
        ),
        "createdBy": str(
            item.get("createdBy")
            or ""
        ),
        "updatedAt": str(
            item.get("updatedAt")
            or ""
        ),
        "updatedBy": str(
            item.get("updatedBy")
            or ""
        ),
        "vendor": (
            _public_vendor(vendor)
            if vendor
            else None
        ),
    }


def _project_vendor_record(
    project_id: str,
    vendor_id: str,
) -> dict[str, Any] | None:
    response = _ops_table().get_item(
        Key={
            "PK":
                f"PROJECT#{project_id}",
            "SK":
                f"VENDOR#{vendor_id}",
        },
        ConsistentRead=True,
    )

    item = response.get("Item")

    if (
        not isinstance(item, dict)
        or item.get("recordType")
            != "PROJECT_VENDOR"
    ):
        return None

    return item


def _list_project_vendors(
    project_id: str,
) -> list[dict[str, Any]]:
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

    for item in (
        response.get("Items")
        or []
    ):
        if (
            not isinstance(item, dict)
            or item.get("recordType")
                != "PROJECT_VENDOR"
            or item.get(
                "relationshipStatus"
            )
                != "ACTIVE"
        ):
            continue

        vendor_id = str(
            item.get("vendorId")
            or ""
        )

        vendor = (
            _vendor_record(vendor_id)
            if vendor_id
            else None
        )

        result.append(
            _public_project_vendor(
                item,
                vendor,
            )
        )

    return sorted(
        result,
        key=lambda item: (
            item["category"],
            (
                item.get("vendor")
                or {}
            ).get(
                "name",
                "",
            ).casefold(),
            item["vendorId"],
        ),
    )


def _project_vendor_audit_item(
    project_id: str,
    vendor_id: str,
    *,
    action: str,
    actor_subject: str,
    before: dict[str, Any] | None,
    after: dict[str, Any],
    changed_fields: list[str],
    now: str,
) -> dict[str, Any]:
    audit_id = _new_record_id(
        "AUD"
    )

    return {
        "PK":
            f"PROJECT#{project_id}",
        "SK":
            (
                f"VENDOR_AUDIT#{now}"
                f"#{audit_id}"
            ),
        "recordType":
            "PROJECT_VENDOR_AUDIT",
        "auditId":
            audit_id,
        "projectId":
            project_id,
        "vendorId":
            vendor_id,
        "action":
            action,
        "actorUserId":
            actor_subject,
        "changedFields":
            changed_fields,
        "before":
            before or {},
        "after":
            after,
        "createdAt":
            now,
    }


def _write_project_vendor_transaction(
    item: dict[str, Any],
    *,
    action: str,
    actor_subject: str,
    before: dict[str, Any] | None,
    changed_fields: list[str],
    condition_expression: str,
    condition_values:
        dict[str, Any] | None = None,
) -> None:
    project_id = str(
        item.get("projectId")
        or ""
    )

    vendor_id = str(
        item.get("vendorId")
        or ""
    )

    now = str(
        item.get("updatedAt")
        or _utcnow()
    )

    audit = (
        _project_vendor_audit_item(
            project_id,
            vendor_id,
            action=action,
            actor_subject=
                actor_subject,
            before=before,
            after=
                _public_project_vendor(
                    item
                ),
            changed_fields=
                changed_fields,
            now=now,
        )
    )

    relation_put = {
        "TableName":
            OPS_TABLE_NAME,
        "Item":
            _serialize_map(item),
        "ConditionExpression":
            condition_expression,
    }

    if condition_values:
        relation_put[
            "ExpressionAttributeValues"
        ] = _serialize_map(
            condition_values
        )

    try:
        boto3.client(
            "dynamodb"
        ).transact_write_items(
            TransactItems=[
                {
                    "Put":
                        relation_put
                },
                {
                    "Put": {
                        "TableName":
                            OPS_TABLE_NAME,
                        "Item":
                            _serialize_map(
                                audit
                            ),
                        "ConditionExpression": (
                            "attribute_not_exists("
                            "PK) AND "
                            "attribute_not_exists("
                            "SK)"
                        ),
                    }
                },
            ]
        )

    except ClientError as exc:
        if (
            _aws_error_code(exc)
            ==
            "TransactionCanceledException"
        ):
            raise ProjectVendorConflict(
                "project_vendor_changed_refresh"
            ) from exc

        raise


def _link_project_vendor(
    project_id: str,
    vendor_id: str,
    fields: dict[str, Any],
    actor_subject: str,
) -> tuple[
    dict[str, Any],
    bool,
]:
    existing = (
        _project_vendor_record(
            project_id,
            vendor_id,
        )
    )

    if (
        existing
        and existing.get(
            "relationshipStatus"
        )
        == "ACTIVE"
    ):
        raise ProjectVendorConflict(
            "project_vendor_already_linked"
        )

    now = _utcnow()

    item = {
        "PK":
            f"PROJECT#{project_id}",
        "SK":
            f"VENDOR#{vendor_id}",
        "recordType":
            "PROJECT_VENDOR",
        "projectId":
            project_id,
        "vendorId":
            vendor_id,
        "relationshipStatus":
            "ACTIVE",
        **fields,
        "linkedAt":
            now,
        "linkedBy":
            actor_subject,
        "createdAt":
            (
                str(
                    existing.get(
                        "createdAt"
                    )
                    or now
                )
                if existing
                else now
            ),
        "createdBy":
            (
                str(
                    existing.get(
                        "createdBy"
                    )
                    or actor_subject
                )
                if existing
                else actor_subject
            ),
        "updatedAt":
            now,
        "updatedBy":
            actor_subject,
    }

    if existing:
        condition_expression = (
            "recordType = "
            ":relation_type AND "
            "updatedAt = "
            ":expected_updated"
        )

        condition_values = {
            ":relation_type":
                "PROJECT_VENDOR",
            ":expected_updated":
                str(
                    existing.get(
                        "updatedAt"
                    )
                    or ""
                ),
        }

    else:
        condition_expression = (
            "attribute_not_exists(PK)"
        )

        condition_values = None

    _write_project_vendor_transaction(
        item,
        action="PROJECT_VENDOR_LINKED",
        actor_subject=actor_subject,
        before=(
            _public_project_vendor(
                existing
            )
            if existing
            else None
        ),
        changed_fields=[
            "relationshipStatus",
            "category",
            "operationalStatus",
            "bookingStatus",
            "quoteAmount",
            "depositAmount",
            "notes",
        ],
        condition_expression=
            condition_expression,
        condition_values=
            condition_values,
    )

    return item, existing is None


def _update_project_vendor(
    current: dict[str, Any],
    changes: dict[str, Any],
    actor_subject: str,
) -> tuple[
    dict[str, Any],
    bool,
]:
    changed_fields = [
        field
        for field, value
        in changes.items()
        if current.get(field) != value
    ]

    if not changed_fields:
        return current, False

    now = _utcnow()

    updated = {
        **current,
        **changes,
        "updatedAt":
            now,
        "updatedBy":
            actor_subject,
    }

    _write_project_vendor_transaction(
        updated,
        action="PROJECT_VENDOR_UPDATED",
        actor_subject=actor_subject,
        before=
            _public_project_vendor(
                current
            ),
        changed_fields=
            sorted(changed_fields),
        condition_expression=(
            "recordType = "
            ":relation_type AND "
            "relationshipStatus = "
            ":active AND "
            "updatedAt = "
            ":expected_updated"
        ),
        condition_values={
            ":relation_type":
                "PROJECT_VENDOR",
            ":active":
                "ACTIVE",
            ":expected_updated":
                str(
                    current.get(
                        "updatedAt"
                    )
                    or ""
                ),
        },
    )

    return updated, True


def _unlink_project_vendor(
    current: dict[str, Any],
    actor_subject: str,
) -> tuple[
    dict[str, Any],
    bool,
]:
    if (
        current.get(
            "relationshipStatus"
        )
        == "UNLINKED"
    ):
        return current, False

    now = _utcnow()

    updated = {
        **current,
        "relationshipStatus":
            "UNLINKED",
        "unlinkedAt":
            now,
        "unlinkedBy":
            actor_subject,
        "updatedAt":
            now,
        "updatedBy":
            actor_subject,
    }

    _write_project_vendor_transaction(
        updated,
        action="PROJECT_VENDOR_UNLINKED",
        actor_subject=actor_subject,
        before=
            _public_project_vendor(
                current
            ),
        changed_fields=[
            "relationshipStatus",
        ],
        condition_expression=(
            "recordType = "
            ":relation_type AND "
            "relationshipStatus = "
            ":active AND "
            "updatedAt = "
            ":expected_updated"
        ),
        condition_values={
            ":relation_type":
                "PROJECT_VENDOR",
            ":active":
                "ACTIVE",
            ":expected_updated":
                str(
                    current.get(
                        "updatedAt"
                    )
                    or ""
                ),
        },
    )

    return updated, True


def _project_vendor_project_id(
    event: dict[str, Any],
) -> str:
    parameters = (
        event.get("pathParameters")
        or {}
    )

    return str(
        parameters.get("projectId")
        or ""
    ).strip().upper()


def _project_vendor_vendor_id(
    event: dict[str, Any],
) -> str:
    parameters = (
        event.get("pathParameters")
        or {}
    )

    return str(
        parameters.get("vendorId")
        or ""
    ).strip().upper()


def _project_vendor_write_access_error(
    event: dict[str, Any],
    identity: dict[str, Any],
):
    project_id = (
        _project_vendor_project_id(
            event
        )
    )

    if not project_id:
        return _response(
            400,
            {
                "error":
                    "project_id_required"
            },
        )

    try:
        project = _project_record(
            project_id
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to authorize "
            "project vendor write"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    if not project:
        return _response(
            404,
            {
                "error":
                    "project_not_found"
            },
        )

    if identity["role"] in {
        "OWNER",
        "MANAGER",
    }:
        return None

    if not _can_view_project(
        identity,
        project,
    ):
        return _response(
            403,
            {
                "error":
                    "project_access_required"
            },
        )

    if (
        str(
            project.get("status")
            or "ACTIVE"
        )
        != "ACTIVE"
    ):
        return _response(
            409,
            {
                "error":
                    "project_not_active"
            },
        )

    subject = str(
        identity.get("subject")
        or ""
    )

    membership = (
        _project_member_record(
            project_id,
            subject,
        )
    )

    if (
        not membership
        or membership.get(
            "membershipStatus"
        )
        != "ACTIVE"
        or membership.get(
            "projectRole"
        )
        == "VIEWER"
    ):
        return _response(
            403,
            {
                "error":
                    "project_write_access_required"
            },
        )

    return None


def _handle_list_project_vendors(
    event: dict[str, Any],
):
    project_id = (
        _project_vendor_project_id(
            event
        )
    )

    if not project_id:
        return _response(
            400,
            {
                "error":
                    "project_id_required"
            },
        )

    try:
        items = (
            _list_project_vendors(
                project_id
            )
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to list project vendors"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "items":
                items,
            "count":
                len(items),
        },
    )


def _handle_link_project_vendor(
    event: dict[str, Any],
    identity: dict[str, Any],
):
    project_id = (
        _project_vendor_project_id(
            event
        )
    )

    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {
                "error":
                    "invalid_json"
            },
        )

    vendor_id = str(
        body.get("vendorId")
        or ""
    ).strip().upper()

    if not vendor_id.startswith(
        "VEN-"
    ):
        return _response(
            400,
            {
                "error":
                    "vendor_id_required"
            },
        )

    try:
        fields = (
            _project_vendor_request_fields(
                body,
                partial=False,
            )
        )

    except ValueError as exc:
        return _response(
            400,
            {
                "error":
                    str(exc)
            },
        )

    try:
        vendor = _vendor_record(
            vendor_id
        )

        if not vendor:
            return _response(
                404,
                {
                    "error":
                        "vendor_not_found"
                },
            )

        if (
            str(
                vendor.get("status")
                or "ACTIVE"
            )
            not in {
                "ACTIVE",
                "PREFERRED",
            }
        ):
            return _response(
                409,
                {
                    "error":
                        "vendor_unavailable"
                },
            )

        fields["category"] = (
            _normalize_vendor_category(
                vendor.get("category")
            )
            or "OTHER"
        )

        relationship, _ = (
            _link_project_vendor(
                project_id,
                vendor_id,
                fields,
                identity["subject"],
            )
        )

        _record_activity(
            project_id,
            identity["subject"],
            "PROJECT_VENDOR_LINKED",
            (
                "Linked vendor: "
                f"{vendor.get('name') or vendor_id}"
            ),
            {
                "vendorId":
                    vendor_id,
                "category":
                    relationship[
                        "category"
                    ],
            },
        )

    except ProjectVendorConflict as exc:
        return _response(
            409,
            {
                "error":
                    exc.code
            },
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to link project vendor"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        201,
        {
            "projectVendor":
                _public_project_vendor(
                    relationship,
                    vendor,
                )
        },
    )


def _handle_update_project_vendor(
    event: dict[str, Any],
    identity: dict[str, Any],
):
    project_id = (
        _project_vendor_project_id(
            event
        )
    )

    vendor_id = (
        _project_vendor_vendor_id(
            event
        )
    )

    if not vendor_id.startswith(
        "VEN-"
    ):
        return _response(
            400,
            {
                "error":
                    "vendor_id_required"
            },
        )

    body = _request_body(event)

    if body is None:
        return _response(
            400,
            {
                "error":
                    "invalid_json"
            },
        )

    try:
        changes = (
            _project_vendor_request_fields(
                body,
                partial=True,
            )
        )

    except ValueError as exc:
        return _response(
            400,
            {
                "error":
                    str(exc)
            },
        )

    try:
        current = (
            _project_vendor_record(
                project_id,
                vendor_id,
            )
        )

        if (
            not current
            or current.get(
                "relationshipStatus"
            )
            != "ACTIVE"
        ):
            return _response(
                404,
                {
                    "error":
                        "project_vendor_not_found"
                },
            )

        updated, changed = (
            _update_project_vendor(
                current,
                changes,
                identity["subject"],
            )
        )

        vendor = _vendor_record(
            vendor_id
        )

        if changed:
            _record_activity(
                project_id,
                identity["subject"],
                "PROJECT_VENDOR_UPDATED",
                (
                    "Updated vendor: "
                    f"{(
                        vendor or {}
                    ).get('name') or vendor_id}"
                ),
                {
                    "vendorId":
                        vendor_id,
                    "changedFields":
                        sorted(
                            changes.keys()
                        ),
                },
            )

    except ProjectVendorConflict as exc:
        return _response(
            409,
            {
                "error":
                    exc.code
            },
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to update project vendor"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "projectVendor":
                _public_project_vendor(
                    updated,
                    vendor,
                ),
            "changed":
                changed,
        },
    )


def _handle_unlink_project_vendor(
    event: dict[str, Any],
    identity: dict[str, Any],
):
    project_id = (
        _project_vendor_project_id(
            event
        )
    )

    vendor_id = (
        _project_vendor_vendor_id(
            event
        )
    )

    if not vendor_id.startswith(
        "VEN-"
    ):
        return _response(
            400,
            {
                "error":
                    "vendor_id_required"
            },
        )

    try:
        current = (
            _project_vendor_record(
                project_id,
                vendor_id,
            )
        )

        if not current:
            return _response(
                404,
                {
                    "error":
                        "project_vendor_not_found"
                },
            )

        updated, changed = (
            _unlink_project_vendor(
                current,
                identity["subject"],
            )
        )

        vendor = _vendor_record(
            vendor_id
        )

        if changed:
            _record_activity(
                project_id,
                identity["subject"],
                "PROJECT_VENDOR_UNLINKED",
                (
                    "Unlinked vendor: "
                    f"{(
                        vendor or {}
                    ).get('name') or vendor_id}"
                ),
                {
                    "vendorId":
                        vendor_id,
                },
            )

    except ProjectVendorConflict as exc:
        return _response(
            409,
            {
                "error":
                    exc.code
            },
        )

    except (
        BotoCoreError,
        ClientError,
        RuntimeError,
    ):
        LOGGER.exception(
            "Failed to unlink project vendor"
        )

        return _response(
            503,
            {
                "error":
                    "temporarily_unavailable"
            },
        )

    return _response(
        200,
        {
            "projectVendor":
                _public_project_vendor(
                    updated,
                    vendor,
                ),
            "changed":
                changed,
        },
    )


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

    identity, error = (
        _authorize_identity(event)
    )

    if error:
        return error

    assert identity is not None

    if (
        method == "GET"
        and path.endswith(
            "/v1/admin/me"
        )
    ):
        return _me_response(identity)

    if (
        method == "POST"
        and path.endswith(
            "/v1/admin/preview-access"
        )
    ):
        return _handle_preview_access(
            identity
        )

    if (
        method == "PATCH"
        and path.endswith(
            "/v1/admin/me/preferences"
        )
    ):
        return _handle_my_preferences(
            event,
            identity,
        )

    if (
        method == "GET"
        and path.endswith(
            "/v1/admin/leads"
        )
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return _handle_list_leads()

    if (
        method == "GET"
        and "/v1/admin/leads/" in path
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return _handle_get_lead(
            event
        )

    if (
        method == "PATCH"
        and "/v1/admin/leads/" in path
        and path.endswith("/status")
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return _handle_lead_status_change(
            event,
            identity["subject"],
        )

    if (
        method == "POST"
        and "/v1/admin/leads/" in path
        and path.endswith("/convert")
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return _handle_convert_lead(
            event,
            identity["subject"],
        )

    if (
        method == "GET"
        and path.endswith(
            "/v1/admin/vendors"
        )
    ):
        return _handle_list_vendors()

    if (
        method == "POST"
        and path.endswith(
            "/v1/admin/vendors"
        )
    ):
        return _handle_create_vendor(
            event,
            identity,
        )

    if (
        method == "GET"
        and "/v1/admin/vendors/" in path
    ):
        return _handle_get_vendor(
            event
        )

    if (
        method == "PATCH"
        and "/v1/admin/vendors/" in path
    ):
        return _handle_update_vendor(
            event,
            identity,
        )

    if (
        method == "GET"
        and path.endswith(
            "/v1/admin/projects"
        )
    ):
        return _handle_list_projects(
            identity
        )

    if (
        method == "GET"
        and path.endswith(
            "/v1/admin/follow-ups"
        )
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return _handle_list_follow_ups()

    if (
        method == "GET"
        and path.endswith("/vendors")
        and "/v1/admin/projects/" in path
    ):
        access_error = (
            _project_read_access_error(
                event,
                identity,
            )
        )

        if access_error:
            return access_error

        return _handle_list_project_vendors(
            event
        )

    if (
        method == "POST"
        and path.endswith("/vendors")
        and "/v1/admin/projects/" in path
    ):
        access_error = (
            _project_vendor_write_access_error(
                event,
                identity,
            )
        )

        if access_error:
            return access_error

        return _handle_link_project_vendor(
            event,
            identity,
        )

    if (
        method == "PATCH"
        and "/vendors/" in path
        and "/v1/admin/projects/" in path
    ):
        access_error = (
            _project_vendor_write_access_error(
                event,
                identity,
            )
        )

        if access_error:
            return access_error

        return _handle_update_project_vendor(
            event,
            identity,
        )

    if (
        method == "DELETE"
        and "/vendors/" in path
        and "/v1/admin/projects/" in path
    ):
        access_error = (
            _project_vendor_write_access_error(
                event,
                identity,
            )
        )

        if access_error:
            return access_error

        return _handle_unlink_project_vendor(
            event,
            identity,
        )

    if (
        method == "GET"
        and path.endswith("/notes")
        and "/v1/admin/projects/" in path
    ):
        access_error = (
            _project_read_access_error(
                event,
                identity,
            )
        )

        if access_error:
            return access_error

        return _handle_list_project_notes(
            event
        )

    if (
        method == "POST"
        and path.endswith("/notes")
        and "/v1/admin/projects/" in path
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return _handle_create_project_note(
            event,
            identity["subject"],
        )

    if (
        method == "PATCH"
        and "/notes/" in path
        and "/v1/admin/projects/" in path
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return _handle_update_project_note(
            event,
            identity["subject"],
        )

    if (
        method == "GET"
        and path.endswith("/follow-ups")
        and "/v1/admin/projects/" in path
    ):
        access_error = (
            _project_read_access_error(
                event,
                identity,
            )
        )

        if access_error:
            return access_error

        return _handle_list_project_follow_ups(
            event
        )

    if (
        method == "POST"
        and path.endswith("/follow-ups")
        and "/v1/admin/projects/" in path
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return _handle_create_project_follow_up(
            event,
            identity["subject"],
        )

    if (
        method == "PATCH"
        and "/follow-ups/" in path
        and "/v1/admin/projects/" in path
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return _handle_update_project_follow_up(
            event,
            identity["subject"],
        )

    if (
        method == "GET"
        and path.endswith("/activity")
        and "/v1/admin/projects/" in path
    ):
        access_error = (
            _project_read_access_error(
                event,
                identity,
            )
        )

        if access_error:
            return access_error

        return _handle_list_project_activity(
            event
        )

    if (
        method == "GET"
        and path.endswith(
            "/v1/admin/tasks"
        )
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return _handle_list_tasks()

    if (
        method == "GET"
        and path.endswith("/tasks")
        and "/v1/admin/projects/" in path
    ):
        access_error = (
            _project_read_access_error(
                event,
                identity,
            )
        )

        if access_error:
            return access_error

        return _handle_list_project_tasks(
            event
        )

    if (
        method == "POST"
        and path.endswith("/tasks")
        and "/v1/admin/projects/" in path
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return _handle_create_project_task(
            event,
            identity["subject"],
        )

    if (
        method == "PATCH"
        and "/tasks/" in path
        and "/v1/admin/projects/" in path
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return _handle_update_project_task(
            event,
            identity["subject"],
        )

    if (
        method == "GET"
        and path.endswith("/members")
        and "/v1/admin/projects/" in path
    ):
        access_error = (
            _project_read_access_error(
                event,
                identity,
            )
        )

        if access_error:
            return access_error

        return _handle_list_project_members(
            event
        )

    if (
        method == "POST"
        and path.endswith("/members")
        and "/v1/admin/projects/" in path
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return _handle_assign_project_member(
            event,
            identity["subject"],
        )

    if (
        method == "PATCH"
        and path.endswith("/role")
        and "/members/" in path
        and "/v1/admin/projects/" in path
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return (
            _handle_project_member_role_change(
                event,
                identity["subject"],
            )
        )

    if (
        method == "DELETE"
        and "/members/" in path
        and "/v1/admin/projects/" in path
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return _handle_unassign_project_member(
            event,
            identity["subject"],
        )

    if (
        method == "POST"
        and "/v1/admin/projects/" in path
    ):
        for lifecycle_action in (
            "complete",
            "reopen",
            "archive",
            "restore",
            "cancel",
        ):
            if path.endswith(
                f"/{lifecycle_action}"
            ):
                return (
                    _handle_project_lifecycle(
                        event,
                        identity,
                        lifecycle_action,
                    )
                )

    if (
        method == "PATCH"
        and path.endswith("/scope")
        and "/v1/admin/projects/" in path
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return _handle_update_project_scope(
            event,
            identity,
        )

    if (
        method == "PATCH"
        and path.endswith("/color")
        and "/v1/admin/projects/" in path
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return _handle_update_project_color(
            event,
            identity["subject"],
        )

    if (
        method == "GET"
        and "/v1/admin/projects/" in path
    ):
        return _handle_get_project(
            event,
            identity,
        )

    if (
        method == "GET"
        and path.endswith(
            "/v1/admin/directory"
        )
    ):
        if identity["role"] not in {
            "OWNER",
            "MANAGER",
        }:
            return _response(
                403,
                {
                    "error":
                        "manager_or_owner_required"
                },
            )

        return _handle_staff_directory()

    if identity["role"] != "OWNER":
        return _response(
            403,
            {"error": "owner_required"},
        )

    actor_subject = identity["subject"]

    if path.endswith(
        "/v1/admin/staff"
    ):
        if method == "GET":
            return _handle_list_staff()

        if method == "POST":
            return _handle_create_staff(
                event,
                actor_subject,
            )

    if (
        method == "PATCH"
        and path.endswith("/role")
    ):
        return _handle_role_change(
            event,
            actor_subject,
        )

    if (
        method == "PATCH"
        and path.endswith("/status")
    ):
        return _handle_status_change(
            event,
            actor_subject,
        )

    return _response(
        404,
        {"error": "not_found"},
    )
