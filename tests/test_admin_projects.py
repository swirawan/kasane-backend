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


def test_worker_cannot_list_all_projects():
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
                "/v1/admin/projects",
            ),
            None,
        )

    assert response["statusCode"] == 403

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
