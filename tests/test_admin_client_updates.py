import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch


ADMIN_APP = (
    Path(__file__).resolve().parent.parent
    / "admin"
    / "app.py"
)

SPEC = importlib.util.spec_from_file_location(
    "kasane_admin_client_updates_app",
    ADMIN_APP,
)

admin_app = importlib.util.module_from_spec(
    SPEC
)

assert SPEC.loader is not None
SPEC.loader.exec_module(admin_app)


def identity(role="OWNER"):
    return {
        "subject": "staff-1",
        "role": role,
        "profile": {
            "displayName":
                "Stanley Wirawan",
            "organizationRole":
                role,
            "status":
                "ACTIVE",
        },
    }


def project(status="ACTIVE"):
    return {
        "PK": "PROJECT#KAS-001",
        "SK": "META",
        "recordType": "PROJECT",
        "projectId": "KAS-001",
        "status": status,
        "clientContactUserId":
            "staff-1",
        "clientContactRole":
            "Event Lead",
    }


def update(status="DRAFT"):
    result = {
        "PK": "PROJECT#KAS-001",
        "SK": "CLIENTUPDATE#UPD-ONE",
        "recordType":
            "CLIENT_UPDATE",
        "projectId":
            "KAS-001",
        "updateId":
            "UPD-ONE",
        "body":
            "Venue shortlist is ready.",
        "status":
            status,
        "authorUserId":
            "staff-1",
        "authorName":
            "Stanley Wirawan",
        "authorRole":
            "Event Lead",
        "createdAt":
            "2026-09-12T14:00:00Z",
        "updatedAt":
            "2026-09-12T14:00:00Z",
    }

    if status == "PUBLISHED":
        result["publishedAt"] = (
            "2026-09-12T14:05:00Z"
        )

    return result


def test_public_update_does_not_expose_internal_actor_fields():
    item = {
        **update("PUBLISHED"),
        "createdBy":
            "internal-subject",
        "updatedBy":
            "other-subject",
        "publishedBy":
            "publisher-subject",
    }

    public = (
        admin_app
        ._public_client_update(
            item
        )
    )

    assert public["body"] == (
        "Venue shortlist is ready."
    )

    assert "createdBy" not in public
    assert "updatedBy" not in public
    assert "publishedBy" not in public


def test_client_safe_list_excludes_drafts():
    table = MagicMock()

    table.query.return_value = {
        "Items": [
            update("DRAFT"),
            update("PUBLISHED"),
        ],
    }

    with patch.object(
        admin_app,
        "_ops_table",
        return_value=table,
    ):
        items = (
            admin_app
            ._list_project_client_updates(
                "KAS-001",
                published_only=True,
            )
        )

    assert len(items) == 1
    assert (
        items[0]["status"]
        == "PUBLISHED"
    )


def test_create_update_snapshots_server_author():
    table = MagicMock()

    with patch.object(
        admin_app,
        "_ops_table",
        return_value=table,
    ), patch.object(
        admin_app,
        "_new_record_id",
        return_value="UPD-TEST",
    ), patch.object(
        admin_app,
        "_utcnow",
        return_value=(
            "2026-09-12T14:00:00Z"
        ),
    ), patch.object(
        admin_app,
        "_project_member_record",
        return_value={
            "membershipStatus":
                "ACTIVE",
            "projectRole":
                "PROJECT_LEAD",
        },
    ), patch.object(
        admin_app,
        "_record_activity",
    ):
        item = (
            admin_app
            ._create_project_client_update(
                project(),
                "Venue shortlist is ready.",
                identity(),
            )
        )

    assert item["status"] == "DRAFT"
    assert (
        item["authorName"]
        == "Stanley Wirawan"
    )
    assert (
        item["authorRole"]
        == "Event Lead"
    )

    table.put_item.assert_called_once()


def test_publish_update_sets_published_timestamp():
    table = MagicMock()

    published = update(
        "PUBLISHED"
    )

    table.update_item.return_value = {
        "Attributes": published,
    }

    with patch.object(
        admin_app,
        "_ops_table",
        return_value=table,
    ), patch.object(
        admin_app,
        "_utcnow",
        return_value=(
            "2026-09-12T14:05:00Z"
        ),
    ), patch.object(
        admin_app,
        "_record_activity",
    ):
        result, changed = (
            admin_app
            ._publish_project_client_update(
                update("DRAFT"),
                "staff-1",
            )
        )

    assert changed is True
    assert (
        result["status"]
        == "PUBLISHED"
    )


def test_closed_project_rejects_update_write():
    with patch.object(
        admin_app,
        "_project_record",
        return_value=project(
            "COMPLETED"
        ),
    ):
        response = (
            admin_app
            ._project_client_update_write_access_error(
                {
                    "pathParameters": {
                        "projectId":
                            "KAS-001",
                    }
                },
                identity(),
            )
        )

    assert response is not None
    assert response["statusCode"] == 409
