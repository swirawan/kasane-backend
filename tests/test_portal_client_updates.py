import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch


PORTAL_APP = (
    Path(__file__).resolve().parent.parent
    / "portal"
    / "app.py"
)

SPEC = importlib.util.spec_from_file_location(
    "kasane_portal_client_updates_app",
    PORTAL_APP,
)

portal_app = importlib.util.module_from_spec(
    SPEC
)

assert SPEC.loader is not None
SPEC.loader.exec_module(portal_app)


def item(status):
    result = {
        "PK":
            "PROJECT#KAS-001",
        "SK":
            f"CLIENTUPDATE#UPD-{status}",
        "recordType":
            "CLIENT_UPDATE",
        "projectId":
            "KAS-001",
        "updateId":
            f"UPD-{status}",
        "body":
            f"{status} update",
        "status":
            status,
        "authorName":
            "Stanley Wirawan",
        "authorRole":
            "Event Lead",
        "createdBy":
            "private-created-by",
        "updatedBy":
            "private-updated-by",
    }

    if status == "PUBLISHED":
        result["publishedAt"] = (
            "2026-09-12T14:05:00Z"
        )

    return result


def test_portal_exposes_only_published_updates():
    table = MagicMock()

    table.query.return_value = {
        "Items": [
            item("DRAFT"),
            item("PUBLISHED"),
        ],
    }

    with patch.object(
        portal_app,
        "_ops_table",
        return_value=table,
    ):
        updates = (
            portal_app
            ._client_updates(
                "KAS-001"
            )
        )

    assert len(updates) == 1

    update = updates[0]

    assert (
        update["updateId"]
        == "UPD-PUBLISHED"
    )

    assert "status" not in update
    assert "createdBy" not in update
    assert "updatedBy" not in update


def test_project_projection_can_include_updates():
    expected = [{
        "updateId": "UPD-1",
        "body": "Venue ready.",
        "authorName":
            "Stanley Wirawan",
        "authorRole":
            "Event Lead",
        "publishedAt":
            "2026-09-12T14:05:00Z",
    }]

    with patch.object(
        portal_app,
        "_client_updates",
        return_value=expected,
    ):
        result = (
            portal_app
            ._public_client_project(
                {
                    "projectId":
                        "KAS-001",
                    "status":
                        "ACTIVE",
                },
                resolve_updates=True,
            )
        )

    assert (
        result["clientUpdates"]
        == expected
    )
