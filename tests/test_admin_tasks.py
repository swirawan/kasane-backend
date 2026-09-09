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
    "kasane_admin_tasks_app",
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


def project():
    return {
        "PK": "PROJECT#KAS-001",
        "SK": "META",
        "recordType": "PROJECT",
        "projectId": "KAS-001",
        "status": "ACTIVE",
    }


def task():
    return {
        "PK": "PROJECT#KAS-001",
        "SK": "TASK#TASK-001",
        "recordType": "TASK",
        "taskId": "TASK-001",
        "projectId": "KAS-001",
        "title": "Confirm venue",
        "description": "",
        "status": "TODO",
        "priority": "HIGH",
        "assigneeUserId": "user-1",
        "dueDate": "2026-09-20",
        "createdAt": "now",
        "updatedAt": "now",
    }


def event(
    method,
    path,
    *,
    payload=None,
):
    result = {
        "version": "2.0",
        "rawPath": path,
        "requestContext": {
            "http": {
                "method": method,
                "path": path,
            },
        },
        "pathParameters": {
            "projectId": "KAS-001",
        },
    }

    if "TASK-001" in path:
        result["pathParameters"][
            "taskId"
        ] = "TASK-001"

    if payload is not None:
        result["body"] = json.dumps(
            payload
        )

    return result


def body(response):
    return json.loads(
        response["body"]
    )


def test_task_public_view_safe():
    result = admin_app._public_task(
        {
            **task(),
            "createdBy": "private",
            "GSI1PK": "private",
            "GSI3PK": "private",
        }
    )

    assert set(result) == {
        "taskId",
        "projectId",
        "title",
        "description",
        "status",
        "priority",
        "assigneeUserId",
        "dueDate",
        "createdAt",
        "updatedAt",
    }


def test_manager_can_list_tasks():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("MANAGER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_list_all_tasks",
        return_value=[task()],
    ):
        response = admin_app.handler(
            event(
                "GET",
                "/v1/admin/tasks",
            ),
            None,
        )

    assert response["statusCode"] == 200
    assert body(response)["count"] == 1


def test_worker_cannot_list_global_tasks():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("WORKER"),
            None,
        ),
    ):
        response = admin_app.handler(
            event(
                "GET",
                "/v1/admin/tasks",
            ),
            None,
        )

    assert response["statusCode"] == 403


def test_owner_can_create_task():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("OWNER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_project_record",
        return_value=project(),
    ), patch.object(
        admin_app,
        "_create_project_task",
        return_value=task(),
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/tasks",
                payload={
                    "title":
                        "Confirm venue",
                    "priority":
                        "HIGH",
                },
            ),
            None,
        )

    assert response["statusCode"] == 201
    assert (
        body(response)["task"]["status"]
        == "TODO"
    )


def test_invalid_task_status_rejected():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("OWNER"),
            None,
        ),
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/tasks",
                payload={
                    "title": "Test",
                    "status": "MAGIC",
                },
            ),
            None,
        )

    assert response["statusCode"] == 400
    assert (
        body(response)["error"]
        == "invalid_task_status"
    )


def test_assignee_must_be_project_member():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("OWNER"),
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
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/tasks",
                payload={
                    "title": "Test",
                    "assigneeUserId":
                        "user-1",
                },
            ),
            None,
        )

    assert response["statusCode"] == 409
    assert (
        body(response)["error"]
        ==
        "assignee_not_project_member"
    )


def test_manager_can_update_task_status():
    changed = {
        **task(),
        "status": "IN_PROGRESS",
    }

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("MANAGER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_task_record",
        return_value=task(),
    ), patch.object(
        admin_app,
        "_update_project_task",
        return_value=changed,
    ):
        response = admin_app.handler(
            event(
                "PATCH",
                "/v1/admin/projects/"
                "KAS-001/tasks/"
                "TASK-001",
                payload={
                    "status":
                        "IN_PROGRESS",
                },
            ),
            None,
        )

    assert response["statusCode"] == 200
    assert (
        body(response)["task"]["status"]
        == "IN_PROGRESS"
    )


def test_task_priority_normalizer():
    assert (
        admin_app
        ._normalize_task_priority(
            "urgent"
        )
        == "URGENT"
    )

    assert (
        admin_app
        ._normalize_task_priority(
            "banana"
        )
        is None
    )


def test_task_status_normalizer():
    assert (
        admin_app
        ._normalize_task_status(
            "waiting_blocked"
        )
        == "WAITING_BLOCKED"
    )
