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
    "kasane_admin_vendors_app",
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
        "contactPerson":
            "Budi",
        "phone":
            "081234",
        "whatsapp":
            "081234",
        "email":
            "hello@example.com",
        "city":
            "Surabaya",
        "services": [
            "Wedding Catering",
        ],
        "pricingNotes":
            "Typical package",
        "internalNotes":
            "Responsive",
        "status":
            "ACTIVE",
        "createdAt":
            "2026-09-10T00:00:00+00:00",
        "createdBy":
            "owner-1",
        "updatedAt":
            "2026-09-10T00:00:00+00:00",
        "updatedBy":
            "owner-1",
        "GSI1PK":
            "DIRECTORY#VENDORS",
        "GSI1SK":
            "NAME#royal catering"
            "#VENDOR#VEN-TEST",
    }


def test_vendor_fields_normalize():
    result = (
        admin_app
        ._vendor_request_fields(
            {
                "name":
                    " Royal Catering ",
                "category":
                    "catering",
                "services":
                    "Wedding Catering, "
                    "Corporate Catering",
            },
            partial=False,
        )
    )

    assert result["name"] == (
        "Royal Catering"
    )

    assert result["category"] == (
        "CATERING"
    )

    assert result["status"] == (
        "ACTIVE"
    )

    assert result["services"] == [
        "Wedding Catering",
        "Corporate Catering",
    ]


def test_vendor_fields_reject_category():
    try:
        (
            admin_app
            ._vendor_request_fields(
                {
                    "name":
                        "Vendor",
                    "category":
                        "NOT_REAL",
                },
                partial=False,
            )
        )
    except ValueError as exc:
        assert str(exc) == (
            "invalid_vendor_category"
        )
    else:
        raise AssertionError(
            "Expected invalid category"
        )


def test_public_vendor():
    result = (
        admin_app
        ._public_vendor(
            vendor()
        )
    )

    assert result["vendorId"] == (
        "VEN-TEST"
    )

    assert result["name"] == (
        "Royal Catering"
    )

    assert result["status"] == (
        "ACTIVE"
    )


def test_create_vendor_is_audited_atomically():
    client = FakeDynamoClient()

    ids = iter([
        "VEN-TEST",
        "AUD-TEST",
    ])

    with patch.object(
        admin_app,
        "OPS_TABLE_NAME",
        "kasane-ops-dev",
    ), patch.object(
        admin_app,
        "_new_record_id",
        side_effect=lambda prefix:
            next(ids),
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
        result = (
            admin_app
            ._create_vendor(
                {
                    "name":
                        "Royal Catering",
                    "category":
                        "CATERING",
                    "contactPerson":
                        "",
                    "phone":
                        "",
                    "whatsapp":
                        "",
                    "email":
                        "",
                    "city":
                        "Surabaya",
                    "services": [],
                    "pricingNotes":
                        "",
                    "internalNotes":
                        "",
                    "status":
                        "ACTIVE",
                },
                "owner-1",
            )
        )

    assert result["vendorId"] == (
        "VEN-TEST"
    )

    assert len(client.calls) == 1

    transaction = (
        client.calls[0][
            "TransactItems"
        ]
    )

    assert len(transaction) == 2


def test_update_vendor_is_audited_atomically():
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
            ._update_vendor(
                vendor(),
                {
                    "city":
                        "Malang",
                },
                "manager-1",
            )
        )

    assert changed is True
    assert updated["city"] == "Malang"
    assert len(client.calls) == 1

    transaction = (
        client.calls[0][
            "TransactItems"
        ]
    )

    assert len(transaction) == 2


def test_noop_vendor_update_skips_write():
    client = FakeDynamoClient()

    with patch.object(
        admin_app.boto3,
        "client",
        return_value=client,
    ):
        updated, changed = (
            admin_app
            ._update_vendor(
                vendor(),
                {
                    "city":
                        "Surabaya",
                },
                "worker-1",
            )
        )

    assert changed is False
    assert updated["city"] == (
        "Surabaya"
    )
    assert client.calls == []


def test_worker_cannot_change_vendor_status():
    current = vendor()

    event = {
        "pathParameters": {
            "vendorId":
                "VEN-TEST",
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
        "_request_body",
        return_value={
            "status":
                "INACTIVE",
        },
    ), patch.object(
        admin_app,
        "_vendor_record",
        return_value=current,
    ):
        response = (
            admin_app
            ._handle_update_vendor(
                event,
                identity,
            )
        )

    assert response["statusCode"] == 403

    body = json.loads(
        response["body"]
    )

    assert body["error"] == (
        "manager_or_owner_required"
    )


def test_worker_can_edit_vendor_details():
    current = vendor()

    updated = {
        **current,
        "city":
            "Malang",
    }

    event = {
        "pathParameters": {
            "vendorId":
                "VEN-TEST",
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
        "_request_body",
        return_value={
            "city":
                "Malang",
        },
    ), patch.object(
        admin_app,
        "_vendor_record",
        return_value=current,
    ), patch.object(
        admin_app,
        "_update_vendor",
        return_value=(
            updated,
            True,
        ),
    ):
        response = (
            admin_app
            ._handle_update_vendor(
                event,
                identity,
            )
        )

    assert response["statusCode"] == 200

    body = json.loads(
        response["body"]
    )

    assert body["vendor"]["city"] == (
        "Malang"
    )
