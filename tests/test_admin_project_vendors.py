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
    "kasane_admin_project_vendors_app",
    ADMIN_APP,
)

admin_app = importlib.util.module_from_spec(
    SPEC
)

assert SPEC.loader is not None
SPEC.loader.exec_module(admin_app)


class FakeDynamoClient:
    def __init__(self):
        self.calls = []

    def transact_write_items(
        self,
        **kwargs,
    ):
        self.calls.append(kwargs)
        return {}


def relationship():
    return {
        "PK":
            "PROJECT#KAS-001",
        "SK":
            "VENDOR#VEN-TEST",
        "recordType":
            "PROJECT_VENDOR",
        "projectId":
            "KAS-001",
        "vendorId":
            "VEN-TEST",
        "relationshipStatus":
            "ACTIVE",
        "category":
            "CATERING",
        "operationalStatus":
            "CONTACTED",
        "bookingStatus":
            "PENDING",
        "quoteAmount":
            45_000_000,
        "depositAmount":
            10_000_000,
        "notes":
            "Wedding package",
        "linkedAt":
            "2026-09-10T00:00:00+00:00",
        "linkedBy":
            "owner-1",
        "createdAt":
            "2026-09-10T00:00:00+00:00",
        "createdBy":
            "owner-1",
        "updatedAt":
            "2026-09-10T00:00:00+00:00",
        "updatedBy":
            "owner-1",
    }


def vendor():
    return {
        "PK":
            "VENDOR#VEN-TEST",
        "SK":
            "PROFILE",
        "recordType":
            "VENDOR",
        "vendorId":
            "VEN-TEST",
        "name":
            "Royal Catering",
        "category":
            "CATERING",
        "status":
            "ACTIVE",
        "services": [],
    }


def test_project_vendor_fields_normalize():
    result = (
        admin_app
        ._project_vendor_request_fields(
            {
                "operationalStatus":
                    "quote received",
                "bookingStatus":
                    "pending",
                "quoteAmount":
                    "45000000",
                "depositAmount":
                    10000000,
                "notes":
                    " Wedding package ",
            },
            partial=False,
        )
    )

    assert (
        result["operationalStatus"]
        == "QUOTE_RECEIVED"
    )

    assert result["bookingStatus"] == (
        "PENDING"
    )

    assert result["quoteAmount"] == (
        45_000_000
    )

    assert result["depositAmount"] == (
        10_000_000
    )

    assert result["notes"] == (
        "Wedding package"
    )


def test_project_vendor_category_is_immutable():
    try:
        (
            admin_app
            ._project_vendor_request_fields(
                {
                    "category":
                        "PHOTO_VIDEO",
                },
                partial=True,
            )
        )

    except ValueError as exc:
        assert str(exc) == (
            "project_vendor_category_immutable"
        )

    else:
        raise AssertionError(
            "Expected immutable category error"
        )


def test_project_vendor_invalid_amount():
    try:
        (
            admin_app
            ._project_vendor_request_fields(
                {
                    "quoteAmount":
                        "-1000",
                },
                partial=True,
            )
        )

    except ValueError as exc:
        assert str(exc) == (
            "invalid_quoteAmount"
        )

    else:
        raise AssertionError(
            "Expected invalid quote amount"
        )


def test_project_viewer_cannot_write_vendor():
    event = {
        "pathParameters": {
            "projectId":
                "KAS-001",
        }
    }

    identity = {
        "role":
            "WORKER",
        "subject":
            "worker-1",
    }

    with patch.object(
        admin_app,
        "_project_record",
        return_value={
            "projectId":
                "KAS-001",
            "status":
                "ACTIVE",
        },
    ), patch.object(
        admin_app,
        "_can_view_project",
        return_value=True,
    ), patch.object(
        admin_app,
        "_project_member_record",
        return_value={
            "membershipStatus":
                "ACTIVE",
            "projectRole":
                "VIEWER",
        },
    ):
        response = (
            admin_app
            ._project_vendor_write_access_error(
                event,
                identity,
            )
        )

    assert response["statusCode"] == 403

    body = json.loads(
        response["body"]
    )

    assert body["error"] == (
        "project_write_access_required"
    )


def test_project_coordinator_can_write_vendor():
    event = {
        "pathParameters": {
            "projectId":
                "KAS-001",
        }
    }

    identity = {
        "role":
            "WORKER",
        "subject":
            "worker-1",
    }

    with patch.object(
        admin_app,
        "_project_record",
        return_value={
            "projectId":
                "KAS-001",
            "status":
                "ACTIVE",
        },
    ), patch.object(
        admin_app,
        "_can_view_project",
        return_value=True,
    ), patch.object(
        admin_app,
        "_project_member_record",
        return_value={
            "membershipStatus":
                "ACTIVE",
            "projectRole":
                "COORDINATOR",
        },
    ):
        response = (
            admin_app
            ._project_vendor_write_access_error(
                event,
                identity,
            )
        )

    assert response is None


def test_link_project_vendor_is_audited_atomically():
    client = FakeDynamoClient()

    with patch.object(
        admin_app,
        "OPS_TABLE_NAME",
        "kasane-ops-dev",
    ), patch.object(
        admin_app,
        "_project_vendor_record",
        return_value=None,
    ), patch.object(
        admin_app,
        "_new_record_id",
        return_value="AUD-TEST",
    ), patch.object(
        admin_app,
        "_utcnow",
        return_value=(
            "2026-09-10T00:00:00+00:00"
        ),
    ), patch.object(
        admin_app.boto3,
        "client",
        return_value=client,
    ):
        item, created = (
            admin_app
            ._link_project_vendor(
                "KAS-001",
                "VEN-TEST",
                {
                    "category":
                        "CATERING",
                    "operationalStatus":
                        "SHORTLISTED",
                    "bookingStatus":
                        "NOT_STARTED",
                    "quoteAmount":
                        0,
                    "depositAmount":
                        0,
                    "notes":
                        "",
                },
                "owner-1",
            )
        )

    assert created is True

    assert (
        item["relationshipStatus"]
        == "ACTIVE"
    )

    assert len(client.calls) == 1

    transaction = (
        client.calls[0][
            "TransactItems"
        ]
    )

    assert len(transaction) == 2


def test_project_vendor_update_is_audited():
    client = FakeDynamoClient()

    with patch.object(
        admin_app,
        "OPS_TABLE_NAME",
        "kasane-ops-dev",
    ), patch.object(
        admin_app,
        "_new_record_id",
        return_value="AUD-TEST",
    ), patch.object(
        admin_app,
        "_utcnow",
        return_value=(
            "2026-09-11T00:00:00+00:00"
        ),
    ), patch.object(
        admin_app.boto3,
        "client",
        return_value=client,
    ):
        updated, changed = (
            admin_app
            ._update_project_vendor(
                relationship(),
                {
                    "operationalStatus":
                        "QUOTE_RECEIVED",
                    "quoteAmount":
                        50_000_000,
                },
                "manager-1",
            )
        )

    assert changed is True

    assert (
        updated["operationalStatus"]
        == "QUOTE_RECEIVED"
    )

    assert updated["quoteAmount"] == (
        50_000_000
    )

    assert len(client.calls) == 1
    assert len(
        client.calls[0][
            "TransactItems"
        ]
    ) == 2


def test_project_vendor_unlink_is_soft():
    client = FakeDynamoClient()

    with patch.object(
        admin_app,
        "OPS_TABLE_NAME",
        "kasane-ops-dev",
    ), patch.object(
        admin_app,
        "_new_record_id",
        return_value="AUD-TEST",
    ), patch.object(
        admin_app,
        "_utcnow",
        return_value=(
            "2026-09-12T00:00:00+00:00"
        ),
    ), patch.object(
        admin_app.boto3,
        "client",
        return_value=client,
    ):
        updated, changed = (
            admin_app
            ._unlink_project_vendor(
                relationship(),
                "owner-1",
            )
        )

    assert changed is True

    assert (
        updated["relationshipStatus"]
        == "UNLINKED"
    )

    assert updated["vendorId"] == (
        "VEN-TEST"
    )

    assert len(client.calls) == 1

    transaction = (
        client.calls[0][
            "TransactItems"
        ]
    )

    assert len(transaction) == 2


def test_unavailable_vendor_cannot_be_linked():
    event = {
        "pathParameters": {
            "projectId":
                "KAS-001",
        }
    }

    identity = {
        "role":
            "OWNER",
        "subject":
            "owner-1",
    }

    unavailable = {
        **vendor(),
        "status":
            "DO_NOT_USE",
    }

    with patch.object(
        admin_app,
        "_request_body",
        return_value={
            "vendorId":
                "VEN-TEST",
        },
    ), patch.object(
        admin_app,
        "_vendor_record",
        return_value=unavailable,
    ):
        response = (
            admin_app
            ._handle_link_project_vendor(
                event,
                identity,
            )
        )

    assert response["statusCode"] == 409

    body = json.loads(
        response["body"]
    )

    assert body["error"] == (
        "vendor_unavailable"
    )
