import importlib.util
import json
from pathlib import Path
from unittest.mock import patch


ADMIN_APP = (
    Path(__file__).resolve().parent.parent
    / "admin"
    / "app.py"
)

SPEC = importlib.util.spec_from_file_location(
    "kasane_admin_staff_app",
    ADMIN_APP,
)

admin_app = importlib.util.module_from_spec(
    SPEC
)

assert SPEC.loader is not None
SPEC.loader.exec_module(admin_app)


def profile(
    subject="actor-1",
    role="OWNER",
    status="ACTIVE",
):
    return {
        "PK": f"USER#{subject}",
        "SK": "PROFILE",
        "recordType": "STAFF_USER",
        "displayName": "Test User",
        "email": "test@example.com",
        "organizationRole": role,
        "status": status,
        "authzVersion": 1,
        "preferredLocale": "en",
    }


def identity(
    role="OWNER",
    subject="actor-1",
):
    return {
        "subject": subject,
        "claims": {
            "username": subject,
        },
        "profile": profile(
            subject=subject,
            role=role,
        ),
        "role": role,
    }


def event(
    method,
    path,
    *,
    body=None,
    user_id=None,
):
    value = {
        "version": "2.0",
        "rawPath": path,
        "requestContext": {
            "http": {
                "method": method,
                "path": path,
            },
        },
    }

    if body is not None:
        value["body"] = json.dumps(body)

    if user_id is not None:
        value["pathParameters"] = {
            "userId": user_id,
        }

    return value


def body(response):
    return json.loads(
        response["body"]
    )


def test_manager_cannot_list_staff():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity(role="MANAGER"),
            None,
        ),
    ):
        response = admin_app.handler(
            event(
                "GET",
                "/v1/admin/staff",
            ),
            None,
        )

    assert response["statusCode"] == 403
    assert (
        body(response)["error"]
        == "owner_required"
    )


def test_owner_can_list_staff():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity(),
            None,
        ),
    ), patch.object(
        admin_app,
        "_list_staff_records",
        return_value=[
            profile(subject="staff-1")
        ],
    ):
        response = admin_app.handler(
            event(
                "GET",
                "/v1/admin/staff",
            ),
            None,
        )

    assert response["statusCode"] == 200
    assert body(response)["count"] == 1


def test_create_staff_defaults_to_worker():
    created_staff = profile(
        subject="staff-2",
        role="WORKER",
    )

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity(),
            None,
        ),
    ), patch.object(
        admin_app,
        "_create_staff",
        return_value=created_staff,
    ) as create_mock:
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/staff",
                body={
                    "displayName":
                        "New Worker",
                    "email":
                        "worker@example.com",
                },
            ),
            None,
        )

    assert response["statusCode"] == 201
    assert (
        body(response)["staff"]["role"]
        == "WORKER"
    )

    assert create_mock.call_args.args[3] == "WORKER"


def test_create_rejects_invalid_role():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity(),
            None,
        ),
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/staff",
                body={
                    "displayName": "Bad Role",
                    "email":
                        "role@example.com",
                    "role": "SUPER_ADMIN",
                },
            ),
            None,
        )

    assert response["statusCode"] == 400
    assert (
        body(response)["error"]
        == "invalid_role"
    )


def test_owner_cannot_demote_self():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity(
                subject="owner-1"
            ),
            None,
        ),
    ):
        response = admin_app.handler(
            event(
                "PATCH",
                "/v1/admin/staff/"
                "owner-1/role",
                body={
                    "role": "WORKER",
                },
                user_id="owner-1",
            ),
            None,
        )

    assert response["statusCode"] == 409
    assert (
        body(response)["error"]
        == "cannot_change_own_role"
    )


def test_owner_can_change_target_role():
    target = profile(
        subject="staff-3",
        role="WORKER",
    )

    updated = dict(target)
    updated["organizationRole"] = "MANAGER"
    updated["authzVersion"] = 2

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity(),
            None,
        ),
    ), patch.object(
        admin_app,
        "_staff_record",
        return_value=target,
    ), patch.object(
        admin_app,
        "_set_staff_role",
        return_value=(
            updated,
            True,
        ),
    ):
        response = admin_app.handler(
            event(
                "PATCH",
                "/v1/admin/staff/"
                "staff-3/role",
                body={
                    "role": "MANAGER",
                },
                user_id="staff-3",
            ),
            None,
        )

    assert response["statusCode"] == 200
    assert (
        body(response)["staff"]["role"]
        == "MANAGER"
    )


def test_owner_cannot_disable_self():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity(
                subject="owner-1"
            ),
            None,
        ),
    ):
        response = admin_app.handler(
            event(
                "PATCH",
                "/v1/admin/staff/"
                "owner-1/status",
                body={
                    "status": "DISABLED",
                },
                user_id="owner-1",
            ),
            None,
        )

    assert response["statusCode"] == 409
    assert (
        body(response)["error"]
        == "cannot_disable_self"
    )


def test_owner_can_disable_target():
    target = profile(
        subject="staff-4",
        role="WORKER",
    )

    updated = dict(target)
    updated["status"] = "DISABLED"
    updated["authzVersion"] = 2

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity(),
            None,
        ),
    ), patch.object(
        admin_app,
        "_staff_record",
        return_value=target,
    ), patch.object(
        admin_app,
        "_set_staff_status",
        return_value=(
            updated,
            True,
        ),
    ):
        response = admin_app.handler(
            event(
                "PATCH",
                "/v1/admin/staff/"
                "staff-4/status",
                body={
                    "status":
                        "DISABLED",
                },
                user_id="staff-4",
            ),
            None,
        )

    assert response["statusCode"] == 200
    assert (
        body(response)["staff"]["status"]
        == "DISABLED"
    )


def test_missing_staff_returns_404():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity(),
            None,
        ),
    ), patch.object(
        admin_app,
        "_staff_record",
        return_value=None,
    ):
        response = admin_app.handler(
            event(
                "PATCH",
                "/v1/admin/staff/"
                "missing/status",
                body={
                    "status":
                        "DISABLED",
                },
                user_id="missing",
            ),
            None,
        )

    assert response["statusCode"] == 404
