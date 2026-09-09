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
    "kasane_admin_leads_app",
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


def event(path, reference=None):
    result = {
        "version": "2.0",
        "rawPath": path,
        "requestContext": {
            "http": {
                "method": "GET",
                "path": path,
            },
        },
    }

    if reference is not None:
        result["pathParameters"] = {
            "reference": reference,
        }

    return result


def lead():
    return {
        "reference": "KAS-260909-ABC123",
        "recordType": "EVENT_BRIEF",
        "createdAt":
            "2026-09-09T12:00:00+00:00",
        "name": "Alya",
        "phone": "+628123",
        "email": "alya@example.com",
        "preferredContact": "WhatsApp",
        "eventType": "Wedding",
        "city": "Surabaya",
        "date": "2027-02-14",
        "guests": "500",
        "message": "Wedding brief details.",
        "submissionId": "secret-internal-id",
        "expiresAt": 123456,
    }


def body(response):
    return json.loads(
        response["body"]
    )


def test_owner_can_list_leads():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("OWNER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_list_leads",
        return_value=[lead()],
    ), patch.object(
        admin_app,
        "_lead_states",
        return_value={},
    ):
        response = admin_app.handler(
            event("/v1/admin/leads"),
            None,
        )

    assert response["statusCode"] == 200
    assert body(response)["count"] == 1


def test_manager_can_list_leads():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("MANAGER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_list_leads",
        return_value=[lead()],
    ), patch.object(
        admin_app,
        "_lead_states",
        return_value={},
    ):
        response = admin_app.handler(
            event("/v1/admin/leads"),
            None,
        )

    assert response["statusCode"] == 200


def test_worker_cannot_list_leads():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("WORKER"),
            None,
        ),
    ):
        response = admin_app.handler(
            event("/v1/admin/leads"),
            None,
        )

    assert response["statusCode"] == 403
    assert (
        body(response)["error"]
        == "manager_or_owner_required"
    )


def test_owner_can_get_lead_detail():
    item = lead()

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("OWNER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_lead_record",
        return_value=item,
    ), patch.object(
        admin_app,
        "_lead_state",
        return_value=None,
    ):
        response = admin_app.handler(
            event(
                "/v1/admin/leads/"
                "KAS-260909-ABC123",
                "KAS-260909-ABC123",
            ),
            None,
        )

    assert response["statusCode"] == 200

    result = body(response)["lead"]

    assert (
        result["reference"]
        == "KAS-260909-ABC123"
    )

    assert (
        result["message"]
        == "Wedding brief details."
    )


def test_internal_fields_not_exposed():
    result = admin_app._public_lead(
        lead(),
        detail=True,
    )

    assert "submissionId" not in result
    assert "expiresAt" not in result
    assert "LeadIndexPK" not in result
    assert "LeadIndexSK" not in result


def test_missing_lead_returns_404():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("OWNER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_lead_record",
        return_value=None,
    ):
        response = admin_app.handler(
            event(
                "/v1/admin/leads/"
                "KAS-MISSING",
                "KAS-MISSING",
            ),
            None,
        )

    assert response["statusCode"] == 404
    assert (
        body(response)["error"]
        == "lead_not_found"
    )
