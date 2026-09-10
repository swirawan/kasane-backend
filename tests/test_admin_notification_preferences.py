import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from admin import app as admin_app


def _load_brief_app():
    path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "src"
        / "app.py"
    )

    spec = (
        importlib.util
        .spec_from_file_location(
            "kasane_brief_notification_test",
            path,
        )
    )

    module = (
        importlib.util
        .module_from_spec(spec)
    )

    assert spec.loader is not None
    spec.loader.exec_module(module)

    return module


def test_owner_notification_defaults_on():
    staff = {
        "PK":
            "USER#owner-1",
        "displayName":
            "Owner",
        "email":
            "owner@example.com",
        "organizationRole":
            "OWNER",
        "status":
            "ACTIVE",
    }

    public = admin_app._public_staff(
        staff
    )

    assert (
        public[
            "newLeadEmailNotifications"
        ]
        is True
    )


def test_worker_notification_defaults_off():
    staff = {
        "PK":
            "USER#worker-1",
        "displayName":
            "Worker",
        "email":
            "worker@example.com",
        "organizationRole":
            "WORKER",
        "status":
            "ACTIVE",
    }

    public = admin_app._public_staff(
        staff
    )

    assert (
        public[
            "newLeadEmailNotifications"
        ]
        is False
    )


def test_explicit_manager_opt_out():
    staff = {
        "PK":
            "USER#manager-1",
        "displayName":
            "Manager",
        "email":
            "manager@example.com",
        "organizationRole":
            "MANAGER",
        "status":
            "ACTIVE",
        "newLeadEmailNotifications":
            False,
    }

    public = admin_app._public_staff(
        staff
    )

    assert (
        public[
            "newLeadEmailNotifications"
        ]
        is False
    )


def test_manager_can_update_own_preference():
    table = MagicMock()

    table.update_item.return_value = {
        "Attributes": {
            "PK":
                "USER#manager-1",
            "SK":
                "PROFILE",
            "displayName":
                "Manager",
            "email":
                "manager@example.com",
            "organizationRole":
                "MANAGER",
            "status":
                "ACTIVE",
            "newLeadEmailNotifications":
                False,
        }
    }

    event = {
        "body": json.dumps(
            {
                "newLeadEmailNotifications":
                    False,
            }
        )
    }

    identity = {
        "subject":
            "manager-1",
        "role":
            "MANAGER",
    }

    with patch.object(
        admin_app,
        "_ops_table",
        return_value=table,
    ):
        response = (
            admin_app
            ._handle_my_preferences(
                event,
                identity,
            )
        )

    assert (
        response["statusCode"]
        == 200
    )

    body = json.loads(
        response["body"]
    )

    assert (
        body["user"][
            "newLeadEmailNotifications"
        ]
        is False
    )


def test_worker_cannot_enable_lead_notifications():
    response = (
        admin_app
        ._handle_my_preferences(
            {
                "body":
                    json.dumps(
                        {
                            "newLeadEmailNotifications":
                                True,
                        }
                    )
            },
            {
                "subject":
                    "worker-1",
                "role":
                    "WORKER",
            },
        )
    )

    assert (
        response["statusCode"]
        == 403
    )


def test_recipient_filtering():
    brief_app = _load_brief_app()

    table = MagicMock()

    table.query.return_value = {
        "Items": [
            {
                "email":
                    "owner@example.com",
                "organizationRole":
                    "OWNER",
                "status":
                    "ACTIVE",
            },
            {
                "email":
                    "manager-off@example.com",
                "organizationRole":
                    "MANAGER",
                "status":
                    "ACTIVE",
                "newLeadEmailNotifications":
                    False,
            },
            {
                "email":
                    "worker@example.com",
                "organizationRole":
                    "WORKER",
                "status":
                    "ACTIVE",
                "newLeadEmailNotifications":
                    True,
            },
            {
                "email":
                    "disabled@example.com",
                "organizationRole":
                    "OWNER",
                "status":
                    "DISABLED",
            },
        ]
    }

    brief_app.OPS_TABLE_NAME = (
        "kasane-ops-dev"
    )

    brief_app.OPS_STAFF_INDEX_NAME = (
        "GSI2"
    )

    with patch.object(
        brief_app,
        "_ops_table",
        return_value=table,
    ):
        recipients = (
            brief_app
            ._notification_recipients()
        )

    assert recipients == [
        "owner@example.com"
    ]

    query = (
        table.query
        .call_args.kwargs
    )

    assert (
        query["IndexName"]
        == "GSI2"
    )

    assert (
        query[
            "ExpressionAttributeValues"
        ][":staff"]
        == "STAFF"
    )
