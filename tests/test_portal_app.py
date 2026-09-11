import importlib.util
import json
from pathlib import Path
from unittest.mock import patch


PORTAL_APP = (
    Path(__file__).resolve().parent.parent
    / "portal"
    / "app.py"
)

SPEC = importlib.util.spec_from_file_location(
    "kasane_portal_app",
    PORTAL_APP,
)

portal_app = (
    importlib.util.module_from_spec(
        SPEC
    )
)

assert SPEC.loader is not None
SPEC.loader.exec_module(portal_app)


def event(
    path,
    *,
    email="client@example.com",
    verified=True,
    token_use="id",
    project_id=None,
):
    claims = {
        "sub": "client-sub-1",
        "token_use": token_use,
        "email": email,
        "email_verified":
            "true"
            if verified
            else "false",
    }

    result = {
        "version": "2.0",
        "rawPath": path,
        "requestContext": {
            "http": {
                "method": "GET",
                "path": path,
            },
            "authorizer": {
                "jwt": {
                    "claims": claims,
                },
            },
        },
    }

    if project_id:
        result[
            "pathParameters"
        ] = {
            "projectId":
                project_id
        }

    return result


def body(response):
    return json.loads(
        response["body"]
    )


def project():
    return {
        "PK":
            "PROJECT#KAS-001",
        "SK":
            "META",
        "recordType":
            "PROJECT",
        "projectId":
            "KAS-001",
        "name":
            "Alya - Wedding",
        "status":
            "ACTIVE",
        "phase":
            "PLANNING",
        "eventType":
            "Wedding",
        "eventDate":
            "2027-02-14",
        "city":
            "Surabaya",
        "guests":
            "500",
        "clientBrief":
            "Elegant and intimate.",
        "package":
            "Plan + Coordinate",
        "product":
            "KASANE MUSUBI",
        "direction":
            "Quiet luxury",
        "updatedAt":
            "2026-09-11T12:00:00Z",

        # These MUST NOT leak.
        "email":
            "alya@example.com",
        "phone":
            "+628123",
        "createdBy":
            "staff-user",
        "updatedBy":
            "staff-user",
        "lastActivityBy":
            "staff-user",
        "cancellationReason":
            "internal reason",
    }


def test_client_partition_key_normalizes_email():
    first = (
        portal_app
        ._client_partition_key(
            " Client@Example.COM "
        )
    )

    second = (
        portal_app
        ._client_partition_key(
            "client@example.com"
        )
    )

    assert first == second
    assert (
        "client@example.com"
        not in first
    )
    assert first.startswith(
        "CLIENT#EMAIL#"
    )


def test_client_identity_requires_verified_email():
    assert (
        portal_app._client_identity(
            event(
                "/v1/client/me",
                verified=False,
            )
        )
        is None
    )


def test_client_identity_rejects_access_token():
    assert (
        portal_app._client_identity(
            event(
                "/v1/client/me",
                token_use="access",
            )
        )
        is None
    )


def test_public_client_project_is_safe():
    public = (
        portal_app
        ._public_client_project(
            project()
        )
    )

    assert (
        public["projectId"]
        == "KAS-001"
    )

    assert (
        public["clientBrief"]
        == "Elegant and intimate."
    )

    for field in (
        "email",
        "phone",
        "createdBy",
        "updatedBy",
        "lastActivityBy",
        "cancellationReason",
    ):
        assert field not in public


def test_me_returns_authenticated_email():
    response = portal_app.handler(
        event(
            "/v1/client/me"
        ),
        None,
    )

    assert response[
        "statusCode"
    ] == 200

    assert body(response) == {
        "client": {
            "email":
                "client@example.com",
        }
    }


def test_projects_uses_authenticated_email():
    with patch.object(
        portal_app,
        "_list_client_projects",
        return_value=[
            {
                "projectId":
                    "KAS-001"
            }
        ],
    ) as mocked:
        response = portal_app.handler(
            event(
                "/v1/client/projects"
            ),
            None,
        )

    assert response[
        "statusCode"
    ] == 200

    mocked.assert_called_once_with(
        "client@example.com"
    )


def test_project_detail_hides_other_clients():
    with patch.object(
        portal_app,
        "_client_access_record",
        return_value=None,
    ):
        response = portal_app.handler(
            event(
                "/v1/client/projects/KAS-999",
                project_id="KAS-999",
            ),
            None,
        )

    assert response[
        "statusCode"
    ] == 404

    assert body(response)[
        "error"
    ] == "project_not_found"


def test_project_detail_returns_safe_project():
    with (
        patch.object(
            portal_app,
            "_client_access_record",
            return_value={
                "status": "ACTIVE",
            },
        ),
        patch.object(
            portal_app,
            "_project_record",
            return_value=project(),
        ),
    ):
        response = portal_app.handler(
            event(
                "/v1/client/projects/KAS-001",
                project_id="KAS-001",
            ),
            None,
        )

    assert response[
        "statusCode"
    ] == 200

    result = body(response)[
        "project"
    ]

    assert result[
        "projectId"
    ] == "KAS-001"

    assert "email" not in result
    assert "phone" not in result



# PHASE 7 — PRIVATE SHARE LINKS

def share_event(
    share_id="q7K2mV8xP4rN6cT9Wz3HdA99",
):
    path = (
        "/v1/portal/share/"
        f"{share_id}"
    )

    return {
        "version": "2.0",
        "rawPath": path,
        "pathParameters": {
            "shareId": share_id,
        },
        "requestContext": {
            "http": {
                "method": "GET",
                "path": path,
            },
        },
    }


def test_share_partition_key_does_not_expose_token():
    share_id = (
        "q7K2mV8xP4rN6cT9Wz3HdA99"
    )

    key = (
        portal_app
        ._portal_share_partition_key(
            share_id
        )
    )

    assert key.startswith(
        "PORTAL#SHARE#"
    )

    assert share_id not in key


def test_public_share_does_not_require_auth():
    with patch.object(
        portal_app,
        "_shared_project",
        return_value=project(),
    ):
        response = portal_app.handler(
            share_event(),
            None,
        )

    assert response["statusCode"] == 200

    result = body(response)["project"]

    assert (
        result["projectId"]
        == "KAS-001"
    )

    assert "email" not in result
    assert "phone" not in result


def test_public_share_invalid_or_revoked_is_generic_404():
    with patch.object(
        portal_app,
        "_shared_project",
        return_value=None,
    ):
        response = portal_app.handler(
            share_event(),
            None,
        )

    assert response["statusCode"] == 404

    assert body(response) == {
        "error": "portal_not_found"
    }


def test_public_serializer_keeps_musubi_hidden_by_default():
    result = (
        portal_app
        ._public_client_project(
            project()
        )
    )

    assert (
        result[
            "musubiClientVisible"
        ]
        is False
    )

    assert (
        result[
            "musubiReviewStatus"
        ]
        == ""
    )
