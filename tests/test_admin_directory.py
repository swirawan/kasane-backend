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
    "kasane_admin_directory_app",
    ADMIN_APP,
)

admin_app = importlib.util.module_from_spec(
    SPEC
)

assert SPEC.loader is not None
SPEC.loader.exec_module(admin_app)


def identity(role):
    return {
        "subject": "user-1",
        "claims": {
            "username": "user-1",
        },
        "profile": {
            "PK": "USER#user-1",
            "SK": "PROFILE",
            "organizationRole": role,
            "status": "ACTIVE",
        },
        "role": role,
    }


def staff(
    user_id,
    name,
    status="ACTIVE",
):
    return {
        "PK": f"USER#{user_id}",
        "SK": "PROFILE",
        "recordType": "STAFF_USER",
        "displayName": name,
        "email":
            f"{user_id}@example.com",
        "organizationRole": "WORKER",
        "status": status,
    }


def event():
    return {
        "version": "2.0",
        "rawPath":
            "/v1/admin/directory",
        "requestContext": {
            "http": {
                "method": "GET",
                "path":
                    "/v1/admin/directory",
            },
        },
    }


def body(response):
    return json.loads(
        response["body"]
    )


def test_owner_can_read_directory():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("OWNER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_list_staff_records",
        return_value=[
            staff("a", "Aaron"),
        ],
    ):
        response = admin_app.handler(
            event(),
            None,
        )

    assert response["statusCode"] == 200
    assert body(response)["count"] == 1


def test_manager_can_read_directory():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("MANAGER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_list_staff_records",
        return_value=[
            staff("a", "Aaron"),
        ],
    ):
        response = admin_app.handler(
            event(),
            None,
        )

    assert response["statusCode"] == 200


def test_worker_cannot_read_directory():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("WORKER"),
            None,
        ),
    ):
        response = admin_app.handler(
            event(),
            None,
        )

    assert response["statusCode"] == 403


def test_directory_hides_disabled_staff():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("OWNER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_list_staff_records",
        return_value=[
            staff(
                "active",
                "Active Person",
            ),
            staff(
                "disabled",
                "Disabled Person",
                status="DISABLED",
            ),
        ],
    ):
        response = admin_app.handler(
            event(),
            None,
        )

    result = body(response)

    assert result["count"] == 1
    assert (
        result["items"][0]["id"]
        == "active"
    )


def test_directory_exposes_only_safe_fields():
    result = (
        admin_app
        ._public_directory_member(
            {
                **staff("a", "Aaron"),
                "authzVersion": 42,
                "createdBy": "secret",
                "GSI2PK": "internal",
            }
        )
    )

    assert set(result) == {
        "id",
        "displayName",
        "email",
        "organizationRole",
        "status",
    }
