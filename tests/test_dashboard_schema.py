from app.schemas.admin import DashboardOut


def test_dashboard_schema_accepts_activity_fields() -> None:
    dashboard = DashboardOut(
        groups=1,
        enabled_groups=1,
        join_requests=2,
        leave_events=1,
        announcements=3,
        files=4,
        essence_messages=5,
        total_members=100,
        today_join_requests=1,
        today_leave_events=1,
        today_admin_actions=2,
        today_messages=5,
        today_active_members=3,
        join_result_breakdown=[{"result": "approved", "count": 1}],
        activity_trend=[{"date": "2026-06-02", "admin_actions": 1, "messages": 5}],
        top_groups=[{"group_id": 1001, "current_members": 100}],
        active_groups=[{"group_id": 1001, "message_count": 5}],
        active_members=[{"group_id": 1001, "user_id": 42, "message_count": 5}],
        recent_leave_events=[{"group_id": 1001, "user_id": 42}],
        recent_audit_logs=[],
    )

    assert dashboard.total_members == 100
    assert dashboard.today_admin_actions == 2
    assert dashboard.today_messages == 5
