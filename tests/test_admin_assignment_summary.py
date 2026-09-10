import importlib.util
from pathlib import Path
from unittest.mock import patch


ADMIN_APP = (
    Path(__file__).resolve().parent.parent
    / "admin"
    / "app.py"
)

SPEC = importlib.util.spec_from_file_location(
    "kasane_admin_assignment_summary_app",
    ADMIN_APP,
)

admin_app = importlib.util.module_from_spec(
    SPEC
)

assert SPEC.loader is not None
SPEC.loader.exec_module(admin_app)


class FakeTable:
    def __init__(
        self,
        *,
        query_items=None,
        update_attributes=None,
    ):
        self.query_items = (
            query_items
            if query_items is not None
            else []
        )

        self.update_attributes = (
            update_attributes
            if update_attributes is not None
            else {}
        )

        self.update_calls = []

    def query(self, **kwargs):
        return {
            "Items":
                self.query_items,
        }

    def update_item(self, **kwargs):
        self.update_calls.append(
            kwargs
        )

        return {
            "Attributes":
                self.update_attributes,
        }


def membership(
    user_id,
    role,
    status="ACTIVE",
):
    return {
        "PK":
            "PROJECT#KAS-001",
        "SK":
            f"MEMBER#{user_id}",
        "recordType":
            "PROJECT_MEMBERSHIP",
        "projectId":
            "KAS-001",
        "userId":
            user_id,
        "projectRole":
            role,
        "membershipStatus":
            status,
    }


def test_assignment_summary_counts_only_active_members():
    table = FakeTable(
        query_items=[
            membership(
                "lead-1",
                "PROJECT_LEAD",
            ),
            membership(
                "worker-1",
                "WORKER",
            ),
            membership(
                "old-lead",
                "PROJECT_LEAD",
                "UNASSIGNED",
            ),
            {
                "recordType":
                    "NOTE",
            },
        ]
    )

    with patch.object(
        admin_app,
        "_ops_table",
        return_value=table,
    ):
        result = (
            admin_app
            ._project_assignment_summary(
                "KAS-001"
            )
        )

    assert result == {
        "activeMemberUserIds": [
            "lead-1",
            "worker-1",
        ],
        "activeMemberCount": 2,
        "projectLeadUserIds": [
            "lead-1"
        ],
    }


def test_public_project_exposes_assignment_summary():
    result = admin_app._public_project(
        {
            "projectId":
                "KAS-001",
            "recordType":
                "PROJECT",
            "status":
                "ACTIVE",
            "activeMemberUserIds": [
                "lead-1",
                "worker-1",
                "worker-2",
            ],
            "activeMemberCount":
                3,
            "projectLeadUserIds": [
                "lead-1",
            ],
        }
    )

    assert (
        result["activeMemberUserIds"]
        == [
            "lead-1",
            "worker-1",
            "worker-2",
        ]
    )

    assert (
        result["activeMemberCount"]
        == 3
    )

    assert (
        result["projectLeadUserIds"]
        == ["lead-1"]
    )


def test_assign_refreshes_assignment_summary():
    table = FakeTable(
        update_attributes=
            membership(
                "worker-1",
                "WORKER",
            )
    )

    with patch.object(
        admin_app,
        "_project_member_record",
        return_value=None,
    ), patch.object(
        admin_app,
        "_ops_table",
        return_value=table,
    ), patch.object(
        admin_app,
        "_refresh_project_assignment_summary",
    ) as refresh:
        _, changed = (
            admin_app
            ._assign_project_member(
                "KAS-001",
                "worker-1",
                "WORKER",
                "owner-1",
            )
        )

    assert changed is True

    refresh.assert_called_once_with(
        "KAS-001"
    )


def test_role_change_refreshes_assignment_summary():
    updated = membership(
        "worker-1",
        "PROJECT_LEAD",
    )

    table = FakeTable(
        update_attributes=updated
    )

    with patch.object(
        admin_app,
        "_ops_table",
        return_value=table,
    ), patch.object(
        admin_app,
        "_refresh_project_assignment_summary",
    ) as refresh:
        result = (
            admin_app
            ._change_project_member_role(
                "KAS-001",
                "worker-1",
                "PROJECT_LEAD",
                "owner-1",
            )
        )

    assert (
        result["projectRole"]
        == "PROJECT_LEAD"
    )

    refresh.assert_called_once_with(
        "KAS-001"
    )


def test_unassign_refreshes_assignment_summary():
    existing = membership(
        "worker-1",
        "WORKER",
    )

    updated = {
        **existing,
        "membershipStatus":
            "UNASSIGNED",
    }

    table = FakeTable(
        update_attributes=updated
    )

    with patch.object(
        admin_app,
        "_project_member_record",
        return_value=existing,
    ), patch.object(
        admin_app,
        "_ops_table",
        return_value=table,
    ), patch.object(
        admin_app,
        "_refresh_project_assignment_summary",
    ) as refresh:
        _, changed = (
            admin_app
            ._unassign_project_member(
                "KAS-001",
                "worker-1",
                "owner-1",
            )
        )

    assert changed is True

    refresh.assert_called_once_with(
        "KAS-001"
    )
