from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3
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
                _public_lead(item)
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

    if not item:
        return _response(
            404,
            {"error": "lead_not_found"},
        )

    return _response(
        200,
        {
            "lead": _public_lead(
                item,
                detail=True,
            ),
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
