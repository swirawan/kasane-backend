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
    "kasane_admin_app",
    ADMIN_APP,
)

admin_app = importlib.util.module_from_spec(
    SPEC
)

assert SPEC.loader is not None
SPEC.loader.exec_module(admin_app)

_DEFAULT = object()


def event(
    groups,
    token_use="access",
):
    return {
        "version": "2.0",
        "rawPath": "/v1/admin/me",
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/v1/admin/me",
            },
            "authorizer": {
                "jwt": {
                    "claims": {
                        "sub": "user-123",
                        "username": "user-123",
                        "token_use": token_use,
                        "cognito:groups": groups,
                    }
                }
            },
        },
    }


def profile(
    role="OWNER",
    status="ACTIVE",
):
    return {
        "PK": "USER#user-123",
        "SK": "PROFILE",
        "recordType": "STAFF_USER",
        "displayName": "Stanley Wirawan",
        "email": "stanley@example.com",
        "organizationRole": role,
        "status": status,
        "authzVersion": 1,
        "preferredLocale": "en",
    }


def invoke(
    groups,
    *,
    token_use="access",
    staff=_DEFAULT,
):
    if staff is _DEFAULT:
        staff = profile()

    with patch.object(
        admin_app,
        "_staff_record",
        return_value=staff,
    ):
        return admin_app.handler(
            event(groups, token_use),
            None,
        )


def body(response):
    return json.loads(response["body"])


def test_owner_profile():
    response = invoke(["OWNER"])

    assert response["statusCode"] == 200
    assert body(response)["user"]["role"] == "OWNER"
    assert (
        body(response)["user"]["displayName"]
        == "Stanley Wirawan"
    )


def test_manager_profile():
    response = invoke(
        ["MANAGER"],
        staff=profile(role="MANAGER"),
    )

    assert response["statusCode"] == 200
    assert body(response)["user"]["role"] == "MANAGER"


def test_worker_profile():
    response = invoke(
        ["WORKER"],
        staff=profile(role="WORKER"),
    )

    assert response["statusCode"] == 200
    assert body(response)["user"]["role"] == "WORKER"


def test_ops_table_role_is_authoritative():
    response = invoke(
        ["MANAGER"],
        staff=profile(role="WORKER"),
    )

    assert response["statusCode"] == 200
    assert body(response)["user"]["role"] == "WORKER"


def test_rejects_staff_without_cognito_role():
    response = invoke([])

    assert response["statusCode"] == 403
    assert (
        body(response)["error"]
        == "staff_role_required"
    )


def test_rejects_id_token():
    response = invoke(
        ["OWNER"],
        token_use="id",
    )

    assert response["statusCode"] == 401


def test_rejects_missing_jwt_claims():
    response = admin_app.handler(
        {
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/v1/admin/me",
                }
            }
        },
        None,
    )

    assert response["statusCode"] == 401


def test_disabled_staff_is_rejected():
    response = invoke(
        ["OWNER"],
        staff=profile(status="DISABLED"),
    )

    assert response["statusCode"] == 403
    assert body(response)["error"] == "staff_disabled"


def test_missing_staff_profile_is_rejected():
    response = invoke(
        ["OWNER"],
        staff=None,
    )

    assert response["statusCode"] == 403
    assert (
        body(response)["error"]
        == "staff_profile_required"
    )


def test_invalid_ops_role_is_rejected():
    response = invoke(
        ["OWNER"],
        staff=profile(role="SUPER_ADMIN"),
    )

    assert response["statusCode"] == 403
    assert (
        body(response)["error"]
        == "invalid_staff_role"
    )


def test_staff_lookup_failure_returns_503():
    with patch.object(
        admin_app,
        "_staff_record",
        side_effect=RuntimeError(
            "ddb unavailable"
        ),
    ):
        response = admin_app.handler(
            event(["OWNER"]),
            None,
        )

    assert response["statusCode"] == 503


def test_staff_record_uses_consistent_read():
    captured = {}

    class FakeTable:
        def get_item(self, **kwargs):
            captured.update(kwargs)

            return {"Item": profile()}

    with patch.object(
        admin_app,
        "_ops_table",
        return_value=FakeTable(),
    ):
        item = admin_app._staff_record(
            "user-123"
        )

    assert item is not None

    assert captured["Key"] == {
        "PK": "USER#user-123",
        "SK": "PROFILE",
    }

    assert captured["ConsistentRead"] is True


def test_groups_accept_api_gateway_bracket_string():
    assert admin_app._groups(
        {"cognito:groups": "[OWNER]"}
    ) == {"OWNER"}


def test_groups_accept_single_quoted_list_string():
    assert admin_app._groups(
        {"cognito:groups": "['OWNER']"}
    ) == {"OWNER"}


def test_groups_accept_multiple_bracketed_roles():
    assert admin_app._groups(
        {
            "cognito:groups":
                "[MANAGER,WORKER]"
        }
    ) == {
        "MANAGER",
        "WORKER",
    }
