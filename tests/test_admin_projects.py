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
    "kasane_admin_projects_app",
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


def lead():
    return {
        "reference": "KAS-260909-ABC123",
        "recordType": "EVENT_BRIEF",
        "createdAt":
            "2026-09-09T12:00:00+00:00",
        "name": "Alya",
        "email": "alya@example.com",
        "phone": "+628123",
        "preferredContact": "WhatsApp",
        "eventType": "Wedding",
        "city": "Surabaya",
        "date": "2027-02-14",
        "guests": "500",
        "message": "Wedding brief.",
    }


def project():
    return {
        "PK": "PROJECT#KAS-001",
        "SK": "META",
        "recordType": "PROJECT",
        "projectId": "KAS-001",
        "name": "Alya · Wedding",
        "status": "ACTIVE",
        "phase": "PLANNING",
        "leadReference":
            "KAS-260909-ABC123",
        "clientName": "Alya",
        "eventType": "Wedding",
        "eventDate": "2027-02-14",
        "city": "Surabaya",
        "guests": "500",
        "createdAt":
            "2026-09-09T13:00:00+00:00",
        "updatedAt":
            "2026-09-09T13:00:00+00:00",
    }


def event(
    method,
    path,
    *,
    reference=None,
    project_id=None,
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
    }

    parameters = {}

    if reference is not None:
        parameters["reference"] = reference

    if project_id is not None:
        parameters["projectId"] = project_id

    if parameters:
        result["pathParameters"] = parameters

    if payload is not None:
        result["body"] = json.dumps(payload)

    return result


def body(response):
    return json.loads(response["body"])


def test_lead_defaults_to_new_pipeline():
    result = admin_app._public_lead(
        lead()
    )

    assert result["pipelineStatus"] == "NEW"
    assert result["convertedProjectId"] == ""


def test_lead_view_merges_pipeline_state():
    result = admin_app._public_lead(
        lead(),
        state={
            "status": "QUALIFIED",
            "convertedProjectId": "",
            "updatedAt": "now",
        },
    )

    assert (
        result["pipelineStatus"]
        == "QUALIFIED"
    )


def test_manager_can_change_lead_status():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("MANAGER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_lead_record",
        return_value=lead(),
    ), patch.object(
        admin_app,
        "_set_lead_status",
        return_value={
            "status": "CONTACTED",
        },
    ):
        response = admin_app.handler(
            event(
                "PATCH",
                "/v1/admin/leads/"
                "KAS-260909-ABC123/status",
                reference="KAS-260909-ABC123",
                payload={
                    "status": "CONTACTED",
                },
            ),
            None,
        )

    assert response["statusCode"] == 200
    assert (
        body(response)["lead"]
        ["pipelineStatus"]
        == "CONTACTED"
    )


def test_worker_cannot_change_lead_status():
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
                "PATCH",
                "/v1/admin/leads/"
                "KAS-260909-ABC123/status",
                reference="KAS-260909-ABC123",
                payload={
                    "status": "CONTACTED",
                },
            ),
            None,
        )

    assert response["statusCode"] == 403


def test_invalid_pipeline_status_rejected():
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
                "PATCH",
                "/v1/admin/leads/"
                "KAS-260909-ABC123/status",
                reference="KAS-260909-ABC123",
                payload={
                    "status": "BANANA",
                },
            ),
            None,
        )

    assert response["statusCode"] == 400
    assert (
        body(response)["error"]
        == "invalid_lead_status"
    )


def test_manager_can_convert_lead():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("MANAGER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_lead_record",
        return_value=lead(),
    ), patch.object(
        admin_app,
        "_convert_lead",
        return_value=(
            project(),
            True,
        ),
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/leads/"
                "KAS-260909-ABC123/convert",
                reference="KAS-260909-ABC123",
            ),
            None,
        )

    assert response["statusCode"] == 201
    assert body(response)["created"] is True
    assert (
        body(response)["project"]
        ["projectId"]
        == "KAS-001"
    )


def test_lost_lead_conversion_conflicts():
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
        return_value=lead(),
    ), patch.object(
        admin_app,
        "_convert_lead",
        side_effect=(
            admin_app.LeadConversionConflict(
                "lead_marked_lost"
            )
        ),
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/leads/"
                "KAS-260909-ABC123/convert",
                reference="KAS-260909-ABC123",
            ),
            None,
        )

    assert response["statusCode"] == 409
    assert (
        body(response)["error"]
        == "lead_marked_lost"
    )


def test_owner_can_list_projects():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("OWNER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_list_projects",
        return_value=[project()],
    ):
        response = admin_app.handler(
            event(
                "GET",
                "/v1/admin/projects",
            ),
            None,
        )

    assert response["statusCode"] == 200
    assert body(response)["count"] == 1


def test_worker_lists_assigned_projects_only():
    assigned = project()

    hidden = project()
    hidden["PK"] = "PROJECT#KAS-002"
    hidden["projectId"] = "KAS-002"

    def membership(
        project_id,
        user_id,
    ):
        if project_id == "KAS-001":
            return {
                "recordType":
                    "PROJECT_MEMBERSHIP",
                "projectId":
                    project_id,
                "userId":
                    user_id,
                "projectRole":
                    "WORKER",
                "membershipStatus":
                    "ACTIVE",
            }

        return None

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("WORKER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_list_projects",
        return_value=[
            assigned,
            hidden,
        ],
    ), patch.object(
        admin_app,
        "_project_member_record",
        side_effect=membership,
    ):
        response = admin_app.handler(
            event(
                "GET",
                "/v1/admin/projects",
            ),
            None,
        )

    assert response["statusCode"] == 200

    result = body(response)

    assert result["count"] == 1

    assert (
        result["items"][0]["projectId"]
        == "KAS-001"
    )


def test_project_color_defaults_by_project_id():
    first = project()

    second = project()
    second["PK"] = "PROJECT#KAS-002"
    second["projectId"] = "KAS-002"

    third = project()
    third["PK"] = "PROJECT#KAS-003"
    third["projectId"] = "KAS-003"

    assert (
        admin_app._public_project(first)
        ["projectColor"]
        == "RUST"
    )

    assert (
        admin_app._public_project(second)
        ["projectColor"]
        == "BLUE"
    )

    assert (
        admin_app._public_project(third)
        ["projectColor"]
        == "OLIVE"
    )


def test_project_color_persisted_override_wins():
    item = project()
    item["projectColor"] = "PLUM"

    result = admin_app._public_project(
        item
    )

    assert result["projectColor"] == "PLUM"


def test_owner_can_change_project_color():
    updated = project()
    updated["projectColor"] = "PLUM"

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("OWNER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_update_project_color",
        return_value=updated,
    ) as update_color:
        response = admin_app.handler(
            event(
                "PATCH",
                "/v1/admin/projects/"
                "KAS-001/color",
                project_id="KAS-001",
                payload={
                    "color": "plum",
                },
            ),
            None,
        )

    assert response["statusCode"] == 200

    assert (
        body(response)["project"]
        ["projectColor"]
        == "PLUM"
    )

    update_color.assert_called_once_with(
        "KAS-001",
        "PLUM",
        "user-1",
    )


def test_invalid_project_color_rejected():
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
                "PATCH",
                "/v1/admin/projects/"
                "KAS-001/color",
                project_id="KAS-001",
                payload={
                    "color": "NEON",
                },
            ),
            None,
        )

    assert response["statusCode"] == 400

    result = body(response)

    assert (
        result["error"]
        == "invalid_project_color"
    )

    assert "RUST" in result["allowed"]
    assert "BLUE" in result["allowed"]
    assert "OLIVE" in result["allowed"]


def test_worker_cannot_change_project_color():
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
                "PATCH",
                "/v1/admin/projects/"
                "KAS-001/color",
                project_id="KAS-001",
                payload={
                    "color": "BLUE",
                },
            ),
            None,
        )

    assert response["statusCode"] == 403

    assert (
        body(response)["error"]
        == "manager_or_owner_required"
    )


def test_missing_project_color_update_returns_404():
    missing = admin_app.ClientError(
        {
            "Error": {
                "Code":
                    "ConditionalCheckFailedException",
                "Message":
                    "Project does not exist",
            },
        },
        "UpdateItem",
    )

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("OWNER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_update_project_color",
        side_effect=missing,
    ):
        response = admin_app.handler(
            event(
                "PATCH",
                "/v1/admin/projects/"
                "KAS-999/color",
                project_id="KAS-999",
                payload={
                    "color": "GOLD",
                },
            ),
            None,
        )

    assert response["statusCode"] == 404

    assert (
        body(response)["error"]
        == "project_not_found"
    )


def test_project_color_update_records_audit():
    updated = project()
    updated["projectColor"] = "TEAL"
    updated["updatedAt"] = (
        "2026-09-09T18:50:00+00:00"
    )
    updated["updatedBy"] = "user-1"

    with patch.object(
        admin_app,
        "_ops_table",
    ) as table_factory, patch.object(
        admin_app,
        "_utcnow",
        return_value=(
            "2026-09-09T18:50:00+00:00"
        ),
    ), patch.object(
        admin_app,
        "_record_activity",
    ) as record_activity:
        table = table_factory.return_value

        table.update_item.return_value = {
            "Attributes": updated,
        }

        result = (
            admin_app._update_project_color(
                "KAS-001",
                "TEAL",
                "user-1",
            )
        )

    assert result["projectColor"] == "TEAL"

    kwargs = (
        table.update_item
        .call_args.kwargs
    )

    assert kwargs["Key"] == {
        "PK": "PROJECT#KAS-001",
        "SK": "META",
    }

    values = (
        kwargs[
            "ExpressionAttributeValues"
        ]
    )

    assert values[":color"] == "TEAL"

    assert (
        values[":updated"]
        == "2026-09-09T18:50:00+00:00"
    )

    assert values[":actor"] == "user-1"

    record_activity.assert_called_once()

    activity_args = (
        record_activity
        .call_args.args
    )

    assert activity_args[0] == "KAS-001"
    assert activity_args[1] == "user-1"

    assert (
        activity_args[2]
        == "PROJECT_COLOR_CHANGED"
    )

    assert (
        activity_args[4]["projectColor"]
        == "TEAL"
    )


def test_archived_project_visible_to_historical_worker():
    archived = project()
    archived["status"] = "ARCHIVED"

    membership = {
        "recordType":
            "PROJECT_MEMBERSHIP",
        "projectId":
            "KAS-001",
        "userId":
            "user-1",
        "projectRole":
            "PRODUCTION",
        "membershipStatus":
            "UNASSIGNED",
    }

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("WORKER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_project_record",
        return_value=archived,
    ), patch.object(
        admin_app,
        "_project_member_record",
        return_value=membership,
    ):
        response = admin_app.handler(
            event(
                "GET",
                "/v1/admin/projects/KAS-001",
                project_id="KAS-001",
            ),
            None,
        )

    assert response["statusCode"] == 200


def test_unassigned_worker_cannot_view_active_project():
    membership = {
        "recordType":
            "PROJECT_MEMBERSHIP",
        "projectId":
            "KAS-001",
        "userId":
            "user-1",
        "projectRole":
            "PRODUCTION",
        "membershipStatus":
            "UNASSIGNED",
    }

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("WORKER"),
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
    ):
        response = admin_app.handler(
            event(
                "GET",
                "/v1/admin/projects/KAS-001",
                project_id="KAS-001",
            ),
            None,
        )

    assert response["statusCode"] == 403


def test_project_lead_can_complete_project():
    updated = project()
    updated["status"] = "COMPLETED"

    membership = {
        "recordType":
            "PROJECT_MEMBERSHIP",
        "projectId":
            "KAS-001",
        "userId":
            "user-1",
        "projectRole":
            "PROJECT_LEAD",
        "membershipStatus":
            "ACTIVE",
    }

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("WORKER"),
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
        "_project_open_work_summary",
        return_value={
            "openTasks": 0,
            "openFollowUps": 0,
        },
    ), patch.object(
        admin_app,
        "_transition_project",
        return_value=updated,
    ) as transition:
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/complete",
                project_id="KAS-001",
                payload={
                    "note":
                        "Event delivered.",
                },
            ),
            None,
        )

    assert response["statusCode"] == 200

    transition.assert_called_once()


def test_non_lead_worker_cannot_complete_project():
    membership = {
        "recordType":
            "PROJECT_MEMBERSHIP",
        "projectId":
            "KAS-001",
        "userId":
            "user-1",
        "projectRole":
            "PRODUCTION",
        "membershipStatus":
            "ACTIVE",
    }

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("WORKER"),
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
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/complete",
                project_id="KAS-001",
            ),
            None,
        )

    assert response["statusCode"] == 403


def test_complete_project_blocks_open_work():
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
        "_project_open_work_summary",
        return_value={
            "openTasks": 2,
            "openFollowUps": 1,
        },
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/complete",
                project_id="KAS-001",
            ),
            None,
        )

    assert response["statusCode"] == 409

    result = body(response)

    assert (
        result["error"]
        == "open_work_remaining"
    )

    assert result["openTasks"] == 2
    assert result["openFollowUps"] == 1


def test_owner_can_force_complete_with_open_work():
    updated = project()
    updated["status"] = "COMPLETED"

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
        "_project_open_work_summary",
        return_value={
            "openTasks": 2,
            "openFollowUps": 1,
        },
    ), patch.object(
        admin_app,
        "_transition_project",
        return_value=updated,
    ) as transition:
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/complete",
                project_id="KAS-001",
                payload={
                    "force": True,
                    "note":
                        "Approved override.",
                },
            ),
            None,
        )

    assert response["statusCode"] == 200

    transition.assert_called_once()


def test_cancel_requires_reason():
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
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/cancel",
                project_id="KAS-001",
            ),
            None,
        )

    assert response["statusCode"] == 400

    assert (
        body(response)["error"]
        == "reason_required"
    )


def test_worker_cannot_archive_project():
    completed = project()
    completed["status"] = "COMPLETED"

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("WORKER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_project_record",
        return_value=completed,
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/archive",
                project_id="KAS-001",
            ),
            None,
        )

    assert response["statusCode"] == 403


def test_lifecycle_transition_rules():
    assert (
        admin_app._lifecycle_target_status(
            "ACTIVE",
            "complete",
        )
        == "COMPLETED"
    )

    assert (
        admin_app._lifecycle_target_status(
            "ACTIVE",
            "cancel",
        )
        == "CANCELLED"
    )

    assert (
        admin_app._lifecycle_target_status(
            "COMPLETED",
            "reopen",
        )
        == "ACTIVE"
    )

    assert (
        admin_app._lifecycle_target_status(
            "COMPLETED",
            "archive",
        )
        == "ARCHIVED"
    )

    assert (
        admin_app._lifecycle_target_status(
            "ARCHIVED",
            "restore",
            "CANCELLED",
        )
        == "CANCELLED"
    )


def test_complete_transition_is_atomic_with_audit():
    current = project()

    updated = project()
    updated["status"] = "COMPLETED"
    updated["completedAt"] = (
        "2026-09-09T20:00:00+00:00"
    )

    with patch.object(
        admin_app,
        "_utcnow",
        return_value=(
            "2026-09-09T20:00:00+00:00"
        ),
    ), patch.object(
        admin_app.boto3,
        "client",
    ) as client_factory, patch.object(
        admin_app,
        "_project_record",
        return_value=updated,
    ):
        result = (
            admin_app._transition_project(
                current,
                "complete",
                "user-1",
                "Delivered.",
            )
        )

    assert result["status"] == "COMPLETED"

    client_factory.assert_called_once_with(
        "dynamodb"
    )

    transaction = (
        client_factory.return_value
        .transact_write_items
        .call_args.kwargs[
            "TransactItems"
        ]
    )

    assert len(transaction) == 2
    assert "Update" in transaction[0]
    assert "Put" in transaction[1]

    update = transaction[0]["Update"]

    assert (
        update[
            "ExpressionAttributeValues"
        ][":new_status"]["S"]
        == "COMPLETED"
    )

    activity = (
        transaction[1]["Put"]["Item"]
    )

    assert (
        activity["recordType"]["S"]
        == "ACTIVITY"
    )

    assert (
        activity["activityType"]["S"]
        == "PROJECT_COMPLETED"
    )



def test_public_project_exposes_lifecycle_metadata():
    item = project()

    item.update({
        "status":
            "COMPLETED",
        "completedAt":
            "2026-09-10T00:00:00+00:00",
        "completedBy":
            "user-1",
        "completionNote":
            "Done.",
    })

    result = admin_app._public_project(
        item
    )

    assert result["status"] == "COMPLETED"

    assert (
        result["completedAt"]
        == "2026-09-10T00:00:00+00:00"
    )

    assert result["completedBy"] == "user-1"
    assert result["completionNote"] == "Done."

def test_project_lead_cannot_force_complete_open_work():
    membership = {
        "recordType":
            "PROJECT_MEMBERSHIP",
        "projectId":
            "KAS-001",
        "userId":
            "user-1",
        "projectRole":
            "PROJECT_LEAD",
        "membershipStatus":
            "ACTIVE",
    }

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("WORKER"),
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
        "_project_open_work_summary",
        return_value={
            "openTasks": 1,
            "openFollowUps": 1,
        },
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/complete",
                project_id="KAS-001",
                payload={
                    "force": True,
                    "note":
                        "Trying override.",
                },
            ),
            None,
        )

    assert response["statusCode"] == 403

    assert (
        body(response)["error"]
        == "project_force_complete_forbidden"
    )

def test_assigned_worker_can_read_project_children():
    membership = {
        "recordType":
            "PROJECT_MEMBERSHIP",
        "projectId":
            "KAS-001",
        "userId":
            "user-1",
        "projectRole":
            "PRODUCTION",
        "membershipStatus":
            "ACTIVE",
    }

    routes = (
        (
            "/notes",
            "_handle_list_project_notes",
        ),
        (
            "/follow-ups",
            "_handle_list_project_follow_ups",
        ),
        (
            "/activity",
            "_handle_list_project_activity",
        ),
        (
            "/tasks",
            "_handle_list_project_tasks",
        ),
        (
            "/members",
            "_handle_list_project_members",
        ),
    )

    for suffix, handler_name in routes:
        with patch.object(
            admin_app,
            "_authorize_identity",
            return_value=(
                identity("WORKER"),
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
            handler_name,
            return_value=
                admin_app._response(
                    200,
                    {"ok": True},
                ),
        ):
            response = admin_app.handler(
                event(
                    "GET",
                    (
                        "/v1/admin/projects/"
                        "KAS-001"
                        f"{suffix}"
                    ),
                    project_id="KAS-001",
                ),
                None,
            )

        assert response["statusCode"] == 200


def test_unassigned_worker_cannot_read_active_children():
    membership = {
        "recordType":
            "PROJECT_MEMBERSHIP",
        "projectId":
            "KAS-001",
        "userId":
            "user-1",
        "projectRole":
            "PRODUCTION",
        "membershipStatus":
            "UNASSIGNED",
    }

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("WORKER"),
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
        "_handle_list_project_activity",
    ) as activity_handler:
        response = admin_app.handler(
            event(
                "GET",
                (
                    "/v1/admin/projects/"
                    "KAS-001/activity"
                ),
                project_id="KAS-001",
            ),
            None,
        )

    assert response["statusCode"] == 403

    activity_handler.assert_not_called()


def test_historical_worker_can_read_archived_children():
    archived = project()
    archived["status"] = "ARCHIVED"

    membership = {
        "recordType":
            "PROJECT_MEMBERSHIP",
        "projectId":
            "KAS-001",
        "userId":
            "user-1",
        "projectRole":
            "PRODUCTION",
        "membershipStatus":
            "UNASSIGNED",
    }

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("WORKER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_project_record",
        return_value=archived,
    ), patch.object(
        admin_app,
        "_project_member_record",
        return_value=membership,
    ), patch.object(
        admin_app,
        "_handle_list_project_activity",
        return_value=
            admin_app._response(
                200,
                {"items": []},
            ),
    ):
        response = admin_app.handler(
            event(
                "GET",
                (
                    "/v1/admin/projects/"
                    "KAS-001/activity"
                ),
                project_id="KAS-001",
            ),
            None,
        )

    assert response["statusCode"] == 200

def test_force_complete_open_work_requires_note():
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
        "_project_open_work_summary",
        return_value={
            "openTasks": 1,
            "openFollowUps": 0,
        },
    ), patch.object(
        admin_app,
        "_transition_project",
    ) as transition:
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/complete",
                project_id="KAS-001",
                payload={
                    "force": True,
                },
            ),
            None,
        )

    assert response["statusCode"] == 400

    assert (
        body(response)["error"]
        == "completion_note_required"
    )

    transition.assert_not_called()


def test_completed_project_with_open_work_cannot_archive():
    completed = project()
    completed["status"] = "COMPLETED"

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
        return_value=completed,
    ), patch.object(
        admin_app,
        "_project_open_work_summary",
        return_value={
            "openTasks": 1,
            "openFollowUps": 1,
        },
    ), patch.object(
        admin_app,
        "_transition_project",
    ) as transition:
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/archive",
                project_id="KAS-001",
            ),
            None,
        )

    assert response["statusCode"] == 409

    assert (
        body(response)["error"]
        == "open_work_remaining"
    )

    transition.assert_not_called()


def test_force_archive_open_work_requires_note():
    completed = project()
    completed["status"] = "COMPLETED"

    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("MANAGER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_project_record",
        return_value=completed,
    ), patch.object(
        admin_app,
        "_project_open_work_summary",
        return_value={
            "openTasks": 1,
            "openFollowUps": 0,
        },
    ), patch.object(
        admin_app,
        "_transition_project",
    ) as transition:
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/archive",
                project_id="KAS-001",
                payload={
                    "force": True,
                },
            ),
            None,
        )

    assert response["statusCode"] == 400

    assert (
        body(response)["error"]
        == "archive_note_required"
    )

    transition.assert_not_called()



def test_project_scope_from_lead_is_preserved():
    item = lead()

    item.update({
        "package": "Plan + Coordinate",
        "product": "KASANE MUSUBI",
        "direction": "Quiet Luxury",
    })

    result = (
        admin_app
        ._project_scope_from_lead(item)
    )

    assert (
        result["package"]
        == "Plan + Coordinate"
    )
    assert (
        result["product"]
        == "KASANE MUSUBI"
    )
    assert (
        result["direction"]
        == "Quiet Luxury"
    )


def test_public_project_exposes_scope():
    item = project()

    item.update({
        "package": "Full KASANE",
        "product": "KASANE MUSUBI",
        "direction": "Quiet Luxury",
    })

    result = admin_app._public_project(
        item
    )

    assert result["package"] == "Full KASANE"
    assert result["product"] == "KASANE MUSUBI"
    assert result["direction"] == "Quiet Luxury"


def test_manager_can_update_project_scope():
    current = project()

    updated = {
        **current,
        "package": "Plan + Coordinate",
        "product": "",
        "direction": "Quiet Luxury",
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
        "_project_record",
        return_value=current,
    ), patch.object(
        admin_app,
        "_update_project_scope",
        return_value=(
            updated,
            True,
        ),
    ) as update_scope:
        response = admin_app.handler(
            event(
                "PATCH",
                "/v1/admin/projects/"
                "KAS-001/scope",
                project_id="KAS-001",
                payload={
                    "package":
                        "Plan + Coordinate",
                    "product":
                        "",
                    "direction":
                        "Quiet Luxury",
                },
            ),
            None,
        )

    assert response["statusCode"] == 200

    result = body(response)

    assert result["changed"] is True
    assert (
        result["project"]["package"]
        == "Plan + Coordinate"
    )

    update_scope.assert_called_once()


def test_worker_cannot_update_project_scope():
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
                "PATCH",
                "/v1/admin/projects/"
                "KAS-001/scope",
                project_id="KAS-001",
                payload={
                    "package":
                        "Full KASANE",
                },
            ),
            None,
        )

    assert response["statusCode"] == 403
    assert (
        body(response)["error"]
        ==
        "manager_or_owner_required"
    )


def test_project_scope_requires_a_field():
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
                "PATCH",
                "/v1/admin/projects/"
                "KAS-001/scope",
                project_id="KAS-001",
                payload={},
            ),
            None,
        )

    assert response["statusCode"] == 400
    assert (
        body(response)["error"]
        ==
        "scope_fields_required"
    )


def test_project_scope_update_records_activity():
    current = project()

    updated = {
        **current,
        "package":
            "Plan + Coordinate",
        "product":
            "",
        "direction":
            "",
        "updatedAt":
            "2026-09-10T22:00:00+00:00",
        "updatedBy":
            "user-1",
    }

    with patch.object(
        admin_app,
        "_ops_table",
    ) as table_factory, patch.object(
        admin_app,
        "_utcnow",
        return_value=(
            "2026-09-10T22:00:00+00:00"
        ),
    ), patch.object(
        admin_app,
        "_record_activity",
    ) as activity:
        table = table_factory.return_value

        table.update_item.return_value = {
            "Attributes": updated,
        }

        result, changed = (
            admin_app._update_project_scope(
                current,
                {
                    "package":
                        "Plan + Coordinate",
                },
                "user-1",
            )
        )

    assert changed is True
    assert (
        result["package"]
        == "Plan + Coordinate"
    )

    activity.assert_called_once()

    args = activity.call_args.args

    assert args[0] == "KAS-001"
    assert args[1] == "user-1"
    assert (
        args[2]
        == "PROJECT_SCOPE_UPDATED"
    )
    assert (
        "package"
        in args[4]["changedFields"]
    )



def test_project_client_brief_preserves_message():
    item = lead()
    item["message"] = (
        "500 guests.\n"
        "Need help with catering and stage."
    )

    result = (
        admin_app
        ._project_client_brief_from_lead(
            item
        )
    )

    assert result == (
        "500 guests.\n"
        "Need help with catering and stage."
    )


def test_public_project_exposes_client_brief():
    item = project()
    item["clientBrief"] = (
        "Elegant, not too floral."
    )

    result = admin_app._public_project(
        item
    )

    assert (
        result["clientBrief"]
        == "Elegant, not too floral."
    )


def test_public_project_defaults_client_brief_blank():
    result = admin_app._public_project(
        project()
    )

    assert result["clientBrief"] == ""



# PHASE 7 CLIENT PROJECT ACCESS

def test_client_access_partition_key_normalizes_email():
    first = (
        admin_app
        ._client_access_partition_key(
            " Alya@Example.COM "
        )
    )

    second = (
        admin_app
        ._client_access_partition_key(
            "alya@example.com"
        )
    )

    assert first == second

    assert first.startswith(
        "CLIENT#EMAIL#"
    )

    assert (
        "alya@example.com"
        not in first
    )


def test_client_access_item_requires_email():
    item = lead()
    item["email"] = ""

    result = (
        admin_app
        ._client_project_access_item(
            item,
            "KAS-001",
            "2026-09-11T12:00:00+00:00",
            "user-1",
        )
    )

    assert result is None


def test_conversion_transaction_creates_client_access():
    with (
        patch.object(
            admin_app,
            "_lead_state",
            return_value=None,
        ),
        patch.object(
            admin_app,
            "_next_project_id",
            return_value="KAS-001",
        ),
        patch.object(
            admin_app,
            "_utcnow",
            return_value=(
                "2026-09-11T12:00:00+00:00"
            ),
        ),
        patch.object(
            admin_app.boto3,
            "client",
        ) as client_factory,
    ):
        converted, created = (
            admin_app._convert_lead(
                lead(),
                "user-1",
            )
        )

    assert created is True
    assert (
        converted["projectId"]
        == "KAS-001"
    )

    dynamodb = (
        client_factory.return_value
    )

    dynamodb.transact_write_items\
        .assert_called_once()

    transaction_items = (
        dynamodb
        .transact_write_items
        .call_args
        .kwargs[
            "TransactItems"
        ]
    )

    assert len(
        transaction_items
    ) == 3

    access_item = (
        transaction_items[1]
        ["Put"]["Item"]
    )

    assert (
        access_item[
            "recordType"
        ]["S"]
        == "CLIENT_PROJECT_ACCESS"
    )

    assert (
        access_item[
            "projectId"
        ]["S"]
        == "KAS-001"
    )

    assert (
        access_item[
            "clientEmail"
        ]["S"]
        == "alya@example.com"
    )

    assert (
        access_item["SK"]["S"]
        == "PROJECT#KAS-001"
    )

    assert (
        access_item["PK"]["S"]
        .startswith(
            "CLIENT#EMAIL#"
        )
    )

    assert (
        "alya@example.com"
        not in
        access_item["PK"]["S"]
    )


def test_conversion_without_email_skips_client_access():
    item = lead()
    item["email"] = ""

    with (
        patch.object(
            admin_app,
            "_lead_state",
            return_value=None,
        ),
        patch.object(
            admin_app,
            "_next_project_id",
            return_value="KAS-001",
        ),
        patch.object(
            admin_app,
            "_utcnow",
            return_value=(
                "2026-09-11T12:00:00+00:00"
            ),
        ),
        patch.object(
            admin_app.boto3,
            "client",
        ) as client_factory,
    ):
        converted, created = (
            admin_app._convert_lead(
                item,
                "user-1",
            )
        )

    assert created is True

    transaction_items = (
        client_factory
        .return_value
        .transact_write_items
        .call_args
        .kwargs[
            "TransactItems"
        ]
    )

    assert len(
        transaction_items
    ) == 2

    record_types = [
        tx.get("Put", {})
        .get("Item", {})
        .get(
            "recordType",
            {},
        )
        .get("S")
        for tx in transaction_items
        if "Put" in tx
    ]

    assert (
        "CLIENT_PROJECT_ACCESS"
        not in record_types
    )



# PHASE 7 CLIENT PORTAL ADMIN ACCESS

def test_owner_can_enable_client_portal_access():
    item = project()
    item["email"] = "alya@example.com"

    access = {
        "projectId": "KAS-001",
        "clientEmail":
            "alya@example.com",
        "status": "ACTIVE",
    }

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
        return_value=item,
    ), patch.object(
        admin_app,
        "_invite_client_to_project",
        return_value=(
            access,
            True,
        ),
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/client-access",
                project_id="KAS-001",
            ),
            None,
        )

    assert response["statusCode"] == 201

    result = body(response)

    assert (
        result["clientAccess"]["email"]
        == "alya@example.com"
    )

    assert (
        result["clientAccess"]["status"]
        == "ACTIVE"
    )

    assert (
        result["clientUserCreated"]
        is True
    )


def test_worker_cannot_enable_client_portal_access():
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
                "POST",
                "/v1/admin/projects/"
                "KAS-001/client-access",
                project_id="KAS-001",
            ),
            None,
        )

    assert response["statusCode"] == 403


def test_client_portal_access_requires_project_email():
    item = project()
    item["email"] = ""

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
        return_value=item,
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/client-access",
                project_id="KAS-001",
            ),
            None,
        )

    assert response["statusCode"] == 409

    assert (
        body(response)["error"]
        == "client_email_required"
    )


def test_client_portal_user_is_passwordless():
    item = project()
    item["email"] = "Alya@Example.COM"

    client = type(
        "Client",
        (),
        {},
    )()

    not_found = admin_app.ClientError(
        {
            "Error": {
                "Code":
                    "UserNotFoundException",
                "Message":
                    "Not found",
            },
        },
        "AdminGetUser",
    )

    from unittest.mock import Mock

    client.admin_get_user = Mock(
        side_effect=not_found
    )

    client.admin_create_user = Mock(
        return_value={
            "User": {
                "Username":
                    "client-user-1"
            }
        }
    )

    table = Mock()

    table.update_item.return_value = {
        "Attributes": {
            "projectId":
                "KAS-001",
            "clientEmail":
                "alya@example.com",
            "status":
                "ACTIVE",
        }
    }

    with patch.object(
        admin_app,
        "_client_cognito",
        return_value=client,
    ), patch.object(
        admin_app,
        "_ops_table",
        return_value=table,
    ), patch.object(
        admin_app,
        "_utcnow",
        return_value=(
            "2026-09-11T14:00:00+00:00"
        ),
    ), patch.object(
        admin_app,
        "_record_activity",
    ):
        access, created = (
            admin_app
            ._invite_client_to_project(
                item,
                "user-1",
            )
        )

    assert created is True

    kwargs = (
        client.admin_create_user
        .call_args.kwargs
    )

    assert (
        kwargs["MessageAction"]
        == "SUPPRESS"
    )

    assert (
        "TemporaryPassword"
        not in kwargs
    )

    assert (
        kwargs["Username"]
        == "alya@example.com"
    )

    assert (
        access["status"]
        == "ACTIVE"
    )



# PHASE 7 — PRIVATE PORTAL SHARE LINKS

def test_portal_share_id_is_unpredictable():
    first = (
        admin_app
        ._new_portal_share_id()
    )

    second = (
        admin_app
        ._new_portal_share_id()
    )

    assert first != second
    assert len(first) >= 30

    assert (
        "KAS-001"
        not in first
    )

    assert (
        "alya"
        not in first.lower()
    )


def test_public_portal_share_never_exposes_bearer_token():
    item = project()

    item[
        "portalShareStatus"
    ] = "ACTIVE"

    item[
        "portalShareKey"
    ] = (
        "PORTAL#SHARE#"
        + "a" * 64
    )

    item[
        "portalShareSuffix"
    ] = "ABC123"

    result = (
        admin_app
        ._public_portal_share(
            item
        )
    )

    assert result == {
        "status": "ACTIVE",
        "shareSuffix": "ABC123",
    }

    assert "shareId" not in result
    assert "path" not in result
    assert "portalShareKey" not in result

    item[
        "portalShareStatus"
    ] = "DISABLED"

    disabled = (
        admin_app
        ._public_portal_share(
            item
        )
    )

    assert disabled == {
        "status": "DISABLED",
        "shareSuffix": "",
    }


def test_worker_cannot_enable_portal_share():
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
                "POST",
                "/v1/admin/projects/"
                "KAS-001/portal-share",
                project_id="KAS-001",
            ),
            None,
        )

    assert response["statusCode"] == 403


def test_manager_can_enable_portal_share():
    response_body = {
        "portalShare": {
            "status": "ACTIVE",
            "shareId":
                "private-share-id-123456789012",
            "path":
                "/p/private-share-id-123456789012",
        },
        "changed": True,
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
        "_handle_enable_portal_share",
        return_value=
            admin_app._response(
                201,
                response_body,
            ),
    ):
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/portal-share",
                project_id="KAS-001",
            ),
            None,
        )

    assert response["statusCode"] == 201

    assert (
        body(response)[
            "portalShare"
        ]["status"]
        == "ACTIVE"
    )


def test_manager_can_regenerate_portal_share():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("MANAGER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_handle_enable_portal_share",
        return_value=
            admin_app._response(
                201,
                {
                    "portalShare": {
                        "status":
                            "ACTIVE",
                    },
                    "changed":
                        True,
                },
            ),
    ) as mocked:
        response = admin_app.handler(
            event(
                "POST",
                "/v1/admin/projects/"
                "KAS-001/portal-share/"
                "regenerate",
                project_id="KAS-001",
            ),
            None,
        )

    assert response["statusCode"] == 201

    assert (
        mocked.call_args.kwargs[
            "regenerate"
        ]
        is True
    )



# PHASE 7 — PROJECT PHASE / CLIENT CONTACT / PREVIEW

def test_project_phase_normalization():
    assert (
        admin_app
        ._normalize_project_phase(
            "event ready"
        )
        == "EVENT_READY"
    )

    assert (
        admin_app
        ._normalize_project_phase(
            "banana"
        )
        == ""
    )


def test_company_email_guard_rejects_personal_email():
    assert (
        admin_app
        ._safe_client_contact_email(
            "stanley@gmail.com"
        )
        == ""
    )

    assert (
        admin_app
        ._safe_client_contact_email(
            " Stanley@KasaneCollective.com "
        )
        ==
        "stanley@kasanecollective.com"
    )


def test_client_safe_project_does_not_leak_customer_contact():
    value = project()

    value["email"] = (
        "client@example.com"
    )
    value["phone"] = "+628123"

    with patch.object(
        admin_app,
        "_resolved_client_contact",
        return_value={
            "userId": "staff-1",
            "name": "Davin",
            "role": "Event Lead",
            "email":
                "davin@kasanecollective.com",
        },
    ):
        public = (
            admin_app
            ._client_safe_project(
                value
            )
        )

    assert "email" not in public
    assert "phone" not in public

    assert public[
        "clientContact"
    ] == {
        "userId": "staff-1",
        "name": "Davin",
        "role": "Event Lead",
        "email":
            "davin@kasanecollective.com",
    }


def test_worker_cannot_change_project_phase():
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
                "PATCH",
                "/v1/admin/projects/"
                "KAS-001/phase",
                project_id="KAS-001",
                payload={
                    "phase": "DESIGN",
                },
            ),
            None,
        )

    assert response[
        "statusCode"
    ] == 403


def test_manager_routes_project_phase_update():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("MANAGER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_handle_update_project_phase",
        return_value=
            admin_app._response(
                200,
                {
                    "project": {
                        "phase":
                            "DESIGN"
                    },
                    "changed":
                        True,
                },
            ),
    ) as mocked:
        response = admin_app.handler(
            event(
                "PATCH",
                "/v1/admin/projects/"
                "KAS-001/phase",
                project_id="KAS-001",
                payload={
                    "phase": "DESIGN",
                },
            ),
            None,
        )

    assert response[
        "statusCode"
    ] == 200

    mocked.assert_called_once()


def test_manager_routes_client_contact_update():
    with patch.object(
        admin_app,
        "_authorize_identity",
        return_value=(
            identity("MANAGER"),
            None,
        ),
    ), patch.object(
        admin_app,
        "_handle_set_client_contact",
        return_value=
            admin_app._response(
                200,
                {
                    "clientContact": {
                        "name":
                            "Davin",
                    }
                },
            ),
    ) as mocked:
        response = admin_app.handler(
            event(
                "PATCH",
                "/v1/admin/projects/"
                "KAS-001/client-contact",
                project_id="KAS-001",
                payload={
                    "userId": "staff-1",
                    "clientRole":
                        "Event Lead",
                    "email":
                        "davin@"
                        "kasanecollective.com",
                },
            ),
            None,
        )

    assert response[
        "statusCode"
    ] == 200

    mocked.assert_called_once()


def test_view_as_client_uses_safe_serializer():
    with (
        patch.object(
            admin_app,
            "_project_record",
            return_value=project(),
        ),
        patch.object(
            admin_app,
            "_can_view_project",
            return_value=True,
        ),
        patch.object(
            admin_app,
            "_resolved_client_contact",
            return_value={
                "userId": "staff-1",
                "name": "Davin",
                "role": "Event Lead",
                "email":
                    "davin@kasanecollective.com",
            },
        ),
    ):
        response = (
            admin_app
            ._handle_client_preview(
                event(
                    "GET",
                    "/v1/admin/projects/"
                    "KAS-001/client-preview",
                    project_id="KAS-001",
                ),
                identity("OWNER"),
            )
        )

    result = body(response)[
        "project"
    ]

    assert response[
        "statusCode"
    ] == 200

    assert "phone" not in result
    assert "email" not in result

    assert (
        result["clientContact"]
        ["name"]
        == "Davin"
    )



def test_admin_portal_share_returns_recoverable_active_link():
    item = project()

    item["portalShareStatus"] = "ACTIVE"
    item["portalShareSuffix"] = "ABC123"
    item["portalShareId"] = (
        "private-share-id-123456789012"
    )

    public = (
        admin_app._public_portal_share(
            item
        )
    )

    assert "shareId" not in public
    assert "path" not in public

    managed = (
        admin_app._admin_portal_share(
            item
        )
    )

    assert managed == {
        "status": "ACTIVE",
        "shareSuffix": "ABC123",
        "shareId":
            "private-share-id-123456789012",
        "path":
            "/p/private-share-id-123456789012",
    }


def test_admin_portal_share_hides_id_when_disabled():
    item = project()

    item["portalShareStatus"] = "DISABLED"
    item["portalShareId"] = (
        "private-share-id-123456789012"
    )

    managed = (
        admin_app._admin_portal_share(
            item
        )
    )

    assert managed == {
        "status": "DISABLED",
        "shareSuffix": "",
    }


def test_existing_active_portal_share_returns_stored_id():
    item = project()

    item["portalShareStatus"] = "ACTIVE"
    item["portalShareKey"] = (
        "PORTAL#SHARE#" + "a" * 64
    )
    item["portalShareId"] = (
        "private-share-id-123456789012"
    )

    updated, changed, share_id = (
        admin_app._enable_portal_share(
            item,
            "user-1",
        )
    )

    assert updated is item
    assert changed is False
    assert (
        share_id
        == "private-share-id-123456789012"
    )


def test_get_portal_share_returns_stored_id():
    item = project()

    item["portalShareStatus"] = "ACTIVE"
    item["portalShareSuffix"] = "ABC123"
    item["portalShareId"] = (
        "private-share-id-123456789012"
    )

    with patch.object(
        admin_app,
        "_project_record",
        return_value=item,
    ):
        response = (
            admin_app
            ._handle_get_portal_share(
                event(
                    "GET",
                    "/v1/admin/projects/"
                    "KAS-001/portal-share",
                    project_id="KAS-001",
                )
            )
        )

    assert response["statusCode"] == 200

    result = body(response)["portalShare"]

    assert (
        result["shareId"]
        == "private-share-id-123456789012"
    )

    assert (
        result["path"]
        == "/p/private-share-id-123456789012"
    )
