import base64
import hashlib
import hmac
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
    "kasane_admin_preview_app",
    ADMIN_APP,
)

admin_app = importlib.util.module_from_spec(
    SPEC
)

assert SPEC.loader is not None
SPEC.loader.exec_module(admin_app)


def event(role):
    path = "/v1/admin/preview-access"

    return {
        "version": "2.0",
        "rawPath": path,
        "requestContext": {
            "http": {
                "method": "POST",
                "path": path,
            },
            "authorizer": {
                "jwt": {
                    "claims": {
                        "sub": "preview-user",
                        "username": "preview-user",
                        "token_use": "access",
                        "cognito:groups": [role],
                    }
                }
            },
        },
    }


def profile(role):
    return {
        "PK": "USER#preview-user",
        "SK": "PROFILE",
        "recordType": "STAFF_USER",
        "displayName": "Preview User",
        "email": "preview@kasanecollective.com",
        "organizationRole": role,
        "status": "ACTIVE",
        "authzVersion": 1,
        "preferredLocale": "en",
    }


def body(response):
    return json.loads(response["body"])


def invoke(role, stage="dev"):
    with (
        patch.object(
            admin_app,
            "STAGE",
            stage,
        ),
        patch.object(
            admin_app,
            "PREVIEW_TOKEN_SECRET_ARN",
            "arn:test:preview-secret",
        ),
        patch.object(
            admin_app,
            "PREVIEW_BASE_URL",
            "https://dev.kasanecollective.com",
        ),
        patch.object(
            admin_app,
            "_staff_record",
            return_value=profile(role),
        ),
        patch.object(
            admin_app,
            "_preview_token_secret",
            return_value="test-preview-secret",
        ),
    ):
        return admin_app.handler(
            event(role),
            None,
        )


def test_owner_can_create_preview_access():
    response = invoke("OWNER")

    assert response["statusCode"] == 200

    payload = body(response)

    assert payload["expiresInSeconds"] == 900
    assert payload["previewUrl"].startswith(
        "https://dev.kasanecollective.com/"
        "?preview="
    )

    token = payload["previewUrl"].split(
        "?preview=",
        1,
    )[1]

    parts = token.split(".")

    assert len(parts) == 5
    assert parts[0] == "v1"
    assert parts[3] == "OWNER"

    message = ".".join(parts[:4])

    expected = (
        base64.urlsafe_b64encode(
            hmac.new(
                b"test-preview-secret",
                message.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        )
        .decode("ascii")
        .rstrip("=")
    )

    assert parts[4] == expected


def test_manager_can_create_preview_access():
    response = invoke("MANAGER")

    assert response["statusCode"] == 200

    token = body(response)["previewUrl"].split(
        "?preview=",
        1,
    )[1]

    assert token.split(".")[3] == "MANAGER"


def test_worker_cannot_create_preview_access():
    response = invoke("WORKER")

    assert response["statusCode"] == 403
    assert (
        body(response)["error"]
        == "manager_or_owner_required"
    )


def test_preview_access_disabled_in_prod():
    response = invoke(
        "OWNER",
        stage="prod",
    )

    assert response["statusCode"] == 404
    assert (
        body(response)["error"]
        == "preview_not_available"
    )