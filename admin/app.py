from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

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


class LeadConversionConflict(RuntimeError):
    pass


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
    }


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
            "updatedBy = :actor "
            "REMOVE GSI2PK, GSI2SK"
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


def _handle_list_projects():
    try:
        projects = _list_projects()

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

    return _response(
        200,
        {
            "project":
                _public_project(project),
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
            "/v1/admin/projects"
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

        return _handle_list_projects()

    if (
        method == "GET"
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
        method == "GET"
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

        return _handle_get_project(
            event
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
