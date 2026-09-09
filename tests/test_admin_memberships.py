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
    "kasane_admin_membership_app",
    ADMIN_APP,
)

admin_app = importlib.util.module_from_spec(
    SPEC
)

assert SPEC.loader is not None
SPEC.loader.exec_module(admin_app)


def identity(role):
    return {
        "subject": "actor-1",
        "claims": {
            "username": "actor-1",
        },
        "profile": {
            "PK": "USER#actor-1",
            "SK": "PROFILE",
            "organizationRole": role,
            "status": "ACTIVE",
        },
        "role": role,
    }


def project():
    return {
        "PK": "PROJECT#KAS-001",
        "SK": "META",
        "recordType": "PROJECT",
        "projectId": "KAS-001",
        "status": "ACTIVE",
    }


def staff():
    return {
        "PK": "USER#staff-1",
        "SK": "PROFILE",
        "recordType": "STAFF_USER",
        "displayName": "Davin",
        "email": "davin@example.com",
        "organizationRole": "MANAGER",
        "status": "ACTIVE",
    }


def membership(
    role="PROJECT_LEAD",
    status="ACTIVE",
):
    return {
        "PK": "PROJECT#KAS-001",
        "SK": "MEMBER#staff-1",
        "recordType":
            "PROJECT_MEMBERSHIP",
        "projectId": "KAS-001",
        "userId": "staff-1",
        "projectRole": role,
        "membershipStatus": status,
        "assignedAt": "now",
        "updatedAt": "now",
    }


def event(
    method,
    path,
    *,
    payload=None,
):
    result = {
        "version": "2.0",
        "rawPath": path,
        "requestContext": {
            "http": {
                "method": method,
                "path": path,
            },
        },
        "pathParameters": {
            "projectId": "KAS-001",
        },
    }

    if "staff-1" in path:
        result["pathParameters"][
            "userId"
        ] = "staff-1"

    if payload is not None:
        result["body"] = json.dumps(
            payload
        )

    return result


def body(response):
    return json.loads(
        response["body"]
    )


def test_public_membership_uses_staff_profile():
    result = (
        admin_app
        ._public_project_member(
            membership(),
            staff(),
        )
    )

    assert result["displayName"] == "Davin"
    assert result["organizationRole"] == "MANAGER"
    assert result["projectRole"] == "PROJECT_LEAD"


def test_manager_can_list_project_members():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("MANAGER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_project_record",
        return_value=project(),
    ), patch.object(
        admin_app,
        "_list_project_members",
        return_value=[
            admin_app._public_project_member(
                membership(),
                staff(),
            )
        ],
    ):
        response = admin_app.handler(
            event(
                "GET",
                "/v1/admin/projects/"
                "KAS-001/members",
            ),
            None,
        )

    assert response["statusCode"] == 200
    assert body(response)["count"] == 1


def test_worker_project_member_read_enforces_project_access():
    denied = admin_app._response(
        403,
        {
            "error":
                "project_access_required"
        },
    )

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("WORKER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_project_read_access_error",
        return_value=denied,
    ) as access_check, patch.object(
        admin_app,
        "_handle_list_project_members",
    ) as list_members:
        response = admin_app.handler(
            event(
                "GET",
                "/v1/admin/projects/"
                "KAS-001/members",
            ),
            None,
        )

    assert response["statusCode"] == 403

    access_check.assert_called_once()

    list_members.assert_not_called()


def test_invalid_project_role_rejected():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("OWNER"),
            None,
        ),
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/members",
                payload={
                    "userId": "staff-1",
                    "projectRole":
                        "SUPER_BOSS",
                },
            ),
            None,
        )

    assert response["statusCode"] == 400
    assert (
        body(response)["error"]
        == "invalid_project_role"
    )


def test_manager_can_assign_project_member():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("MANAGER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_project_record",
        return_value=project(),
    ), patch.object(
        admin_app,
        "_staff_record",
        return_value=staff(),
    ), patch.object(
        admin_app,
        "_assign_project_member",
        return_value=(
            membership(),
            True,
        ),
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/members",
                payload={
                    "userId": "staff-1",
                    "projectRole":
                        "PROJECT_LEAD",
                },
            ),
            None,
        )

    assert response["statusCode"] == 201
    assert body(response)["changed"] is True


def test_owner_can_change_project_role():
    changed = membership(
        role="COORDINATOR"
    )

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("OWNER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_project_record",
        return_value=project(),
    ), patch.object(
        admin_app,
        "_project_member_record",
        return_value=membership(),
    ), patch.object(
        admin_app,
        "_change_project_member_role",
        return_value=changed,
    ), patch.object(
        admin_app,
        "_staff_record",
        return_value=staff(),
    ):
        response = admin_app.handler(
            event(
                "PATCH",
                "/v1/admin/projects/"
                "KAS-001/members/"
                "staff-1/role",
                payload={
                    "projectRole":
                        "COORDINATOR",
                },
            ),
            None,
        )

    assert response["statusCode"] == 200
    assert (
        body(response)
        ["membership"]
        ["projectRole"]
        == "COORDINATOR"
    )


def test_manager_can_unassign_member():
    unassigned = membership(
        status="UNASSIGNED"
    )

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("MANAGER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_project_record",
        return_value=project(),
    ), patch.object(
        admin_app,
        "_unassign_project_member",
        return_value=(
            unassigned,
            True,
        ),
    ):
        response = admin_app.handler(
            event(
                "DELETE",
                "/v1/admin/projects/"
                "KAS-001/members/staff-1",
            ),
            None,
        )

    assert response["statusCode"] == 200
    assert (
        body(response)
        ["membership"]
        ["membershipStatus"]
        == "UNASSIGNED"
    )


def test_unassign_preserves_history_index():
    class FakeTable:
        def __init__(self):
            self.updated = False

        def get_item(self, **kwargs):
            return {
                "Item": membership()
            }

        def update_item(self, **kwargs):
            self.updated = True

            expression = kwargs[
                "UpdateExpression"
            ]

            assert (
                "REMOVE GSI2PK"
                not in expression
            )

            assert (
                "REMOVE GSI2SK"
                not in expression
            )

            item = membership(
                status="UNASSIGNED"
            )

            return {
                "Attributes": item
            }

    table = FakeTable()

    with patch.object(
        admin_app,
        "_ops_table",
        return_value=table,
    ):
        result, changed = (
            admin_app
            ._unassign_project_member(
                "KAS-001",
                "staff-1",
                "actor-1",
            )
        )

    assert changed is True
    assert table.updated is True
    assert (
        result["membershipStatus"]
        == "UNASSIGNED"
    )
