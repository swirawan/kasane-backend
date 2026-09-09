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
    "kasane_admin_followups_app",
    ADMIN_APP,
)

admin_app = importlib.util.module_from_spec(
    SPEC
)

assert SPEC.loader is not None
SPEC.loader.exec_module(admin_app)


def identity(role="OWNER"):
    return {
        "subject": "user-1",
        "claims": {
            "username": "user-1",
        },
        "profile": {
            "organizationRole": role,
            "status": "ACTIVE",
        },
        "role": role,
    }


def project():
    return {
        "PK": "PROJECT#KAS-003",
        "SK": "META",
        "recordType": "PROJECT",
        "projectId": "KAS-003",
    }


def note():
    return {
        "PK": "PROJECT#KAS-003",
        "SK": "NOTE#NTE-1",
        "recordType": "NOTE",
        "noteId": "NTE-1",
        "projectId": "KAS-003",
        "category": "GENERAL",
        "body": "Client prefers garden venue.",
        "createdAt": "2026-09-09T15:00:00Z",
        "createdBy": "user-1",
        "updatedAt": "2026-09-09T15:00:00Z",
        "updatedBy": "user-1",
    }


def follow_up(status="OPEN"):
    return {
        "PK": "PROJECT#KAS-003",
        "SK": "FOLLOWUP#FUP-1",
        "recordType": "FOLLOW_UP",
        "followUpId": "FUP-1",
        "projectId": "KAS-003",
        "title": "Call client",
        "details": "",
        "status": status,
        "assigneeUserId": "user-1",
        "dueAt": "2026-09-10T13:00:00Z",
        "createdAt": "2026-09-09T15:00:00Z",
        "updatedAt": "2026-09-09T15:00:00Z",
    }


def event(
    method,
    path,
    *,
    payload=None,
    extra=None,
):
    parameters = {
        "projectId": "KAS-003",
    }

    if extra:
        parameters.update(extra)

    result = {
        "version": "2.0",
        "rawPath": path,
        "requestContext": {
            "http": {
                "method": method,
                "path": path,
            },
        },
        "pathParameters": parameters,
    }

    if payload is not None:
        result["body"] = json.dumps(
            payload
        )

    return result


def body(response):
    return json.loads(
        response["body"]
    )


def test_due_at_normalizes_to_utc():
    assert (
        admin_app._normalize_due_at(
            "2026-09-10T20:00:00+07:00"
        )
        ==
        "2026-09-10T13:00:00Z"
    )


def test_due_at_rejects_naive_time():
    assert (
        admin_app._normalize_due_at(
            "2026-09-10T20:00:00"
        )
        is None
    )


def test_note_category_normalizes():
    assert (
        admin_app
        ._normalize_note_category(
            "customer_contact"
        )
        == "CUSTOMER_CONTACT"
    )


def test_owner_can_create_note():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity(),
            None,
        ),
    ), patch.object(
        admin_app,
        "_project_record",
        return_value=project(),
    ), patch.object(
        admin_app,
        "_create_project_note",
        return_value=note(),
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-003/notes",
                payload={
                    "category":
                        "GENERAL",
                    "body":
                        "Client prefers garden venue.",
                },
            ),
            None,
        )

    assert response["statusCode"] == 201


def test_invalid_note_category_rejected():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity(),
            None,
        ),
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-003/notes",
                payload={
                    "category":
                        "MAGIC",
                    "body":
                        "Test",
                },
            ),
            None,
        )

    assert response["statusCode"] == 400


def test_owner_can_update_note():
    changed = {
        **note(),
        "category": "DECISION",
    }

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity(),
            None,
        ),
    ), patch.object(
        admin_app,
        "_project_child_record",
        return_value=note(),
    ), patch.object(
        admin_app,
        "_update_project_note",
        return_value=changed,
    ):
        response = admin_app.handler(
            event(
                "PATCH",
                "/v1/admin/projects/"
                "KAS-003/notes/NTE-1",
                payload={
                    "category":
                        "DECISION",
                    "body":
                        "Venue confirmed.",
                },
                extra={
                    "noteId": "NTE-1",
                },
            ),
            None,
        )

    assert response["statusCode"] == 200


def test_invalid_follow_up_due_rejected():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity(),
            None,
        ),
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-003/follow-ups",
                payload={
                    "title": "Call client",
                    "dueAt":
                        "2026-09-10T20:00:00",
                },
            ),
            None,
        )

    assert response["statusCode"] == 400


def test_create_follow_up_requires_active_member():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity(),
            None,
        ),
    ), patch.object(
        admin_app,
        "_project_record",
        return_value=project(),
    ), patch.object(
        admin_app,
        "_project_member_record",
        return_value=None,
    ), patch.object(
        admin_app,
        "_staff_record",
        return_value=None,
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-003/follow-ups",
                payload={
                    "title": "Call client",
                    "assigneeUserId":
                        "user-1",
                    "dueAt":
                        "2026-09-10T13:00:00Z",
                },
            ),
            None,
        )

    assert response["statusCode"] == 409


def test_owner_can_create_follow_up():
    membership = {
        "membershipStatus": "ACTIVE",
    }

    profile = {
        "status": "ACTIVE",
    }

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity(),
            None,
        ),
    ), patch.object(
        admin_app,
        "_project_record",
        return_value=project(),
    ), patch.object(
        admin_app,
        "_project_member_record",
        return_value=membership,
    ), patch.object(
        admin_app,
        "_staff_record",
        return_value=profile,
    ), patch.object(
        admin_app,
        "_create_project_follow_up",
        return_value=follow_up(),
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-003/follow-ups",
                payload={
                    "title": "Call client",
                    "assigneeUserId":
                        "user-1",
                    "dueAt":
                        "2026-09-10T13:00:00Z",
                },
            ),
            None,
        )

    assert response["statusCode"] == 201


def test_owner_can_complete_follow_up():
    changed = follow_up("DONE")

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity(),
            None,
        ),
    ), patch.object(
        admin_app,
        "_project_child_record",
        return_value=follow_up(),
    ), patch.object(
        admin_app,
        "_project_member_record",
        return_value={
            "membershipStatus":
                "ACTIVE",
        },
    ), patch.object(
        admin_app,
        "_staff_record",
        return_value={
            "status": "ACTIVE",
        },
    ), patch.object(
        admin_app,
        "_update_project_follow_up",
        return_value=changed,
    ):
        response = admin_app.handler(
            event(
                "PATCH",
                "/v1/admin/projects/"
                "KAS-003/follow-ups/FUP-1",
                payload={
                    "status": "DONE",
                },
                extra={
                    "followUpId":
                        "FUP-1",
                },
            ),
            None,
        )

    assert response["statusCode"] == 200

    assert (
        body(response)["followUp"][
            "status"
        ]
        == "DONE"
    )


def test_manager_can_list_global_followups():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("MANAGER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_list_open_follow_ups",
        return_value=[
            follow_up()
        ],
    ):
        response = admin_app.handler(
            event(
                "GET",
                "/v1/admin/follow-ups",
            ),
            None,
        )

    assert response["statusCode"] == 200
    assert body(response)["count"] == 1


def test_owner_can_list_activity():
    activity = {
        "recordType": "ACTIVITY",
        "activityId": "ACT-1",
        "projectId": "KAS-003",
        "activityType":
            "FOLLOWUP_CREATED",
        "summary":
            "Created follow-up",
        "actorUserId":
            "user-1",
        "createdAt":
            "2026-09-09T15:00:00Z",
        "metadata": {},
    }

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity(),
            None,
        ),
    ), patch.object(
        admin_app,
        "_project_record",
        return_value=project(),
    ), patch.object(
        admin_app,
        "_list_project_activity",
        return_value=[
            activity
        ],
    ):
        response = admin_app.handler(
            event(
                "GET",
                "/v1/admin/projects/"
                "KAS-003/activity",
            ),
            None,
        )

    assert response["statusCode"] == 200
    assert body(response)["count"] == 1
