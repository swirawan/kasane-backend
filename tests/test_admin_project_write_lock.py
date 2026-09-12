import importlib.util
from pathlib import Path
from unittest.mock import patch


ADMIN_APP = (
    Path(__file__).resolve().parent.parent
    / "admin"
    / "app.py"
)

SPEC = importlib.util.spec_from_file_location(
    "kasane_admin_project_write_lock_app",
    ADMIN_APP,
)

admin_app = importlib.util.module_from_spec(
    SPEC
)

assert SPEC.loader is not None
SPEC.loader.exec_module(admin_app)


def event():
    return {
        "pathParameters": {
            "projectId": "KAS-001",
        },
    }


def project(status="ACTIVE"):
    return {
        "PK": "PROJECT#KAS-001",
        "SK": "META",
        "recordType": "PROJECT",
        "projectId": "KAS-001",
        "status": status,
    }


def test_completed_project_write_is_locked():
    with patch.object(
        admin_app,
        "OPS_TABLE_NAME",
        "kasane-ops-test",
    ), patch.object(
        admin_app,
        "_project_record",
        return_value=project("COMPLETED"),
    ):
        response = (
            admin_app
            ._project_write_lock_error(
                event(),
                "PATCH",
                "/v1/admin/projects/KAS-001/scope",
            )
        )

    assert response is not None
    assert response["statusCode"] == 409


def test_active_project_write_is_allowed():
    with patch.object(
        admin_app,
        "OPS_TABLE_NAME",
        "kasane-ops-test",
    ), patch.object(
        admin_app,
        "_project_record",
        return_value=project("ACTIVE"),
    ):
        response = (
            admin_app
            ._project_write_lock_error(
                event(),
                "PATCH",
                "/v1/admin/projects/KAS-001/scope",
            )
        )

    assert response is None


def test_reopen_bypasses_write_lock():
    with patch.object(
        admin_app,
        "OPS_TABLE_NAME",
        "kasane-ops-test",
    ), patch.object(
        admin_app,
        "_project_record",
    ) as project_record:
        response = (
            admin_app
            ._project_write_lock_error(
                event(),
                "POST",
                "/v1/admin/projects/KAS-001/reopen",
            )
        )

    assert response is None
    project_record.assert_not_called()


def test_preview_read_is_never_locked():
    with patch.object(
        admin_app,
        "OPS_TABLE_NAME",
        "kasane-ops-test",
    ), patch.object(
        admin_app,
        "_project_record",
    ) as project_record:
        response = (
            admin_app
            ._project_write_lock_error(
                event(),
                "GET",
                "/v1/admin/projects/KAS-001/client-preview",
            )
        )

    assert response is None
    project_record.assert_not_called()
