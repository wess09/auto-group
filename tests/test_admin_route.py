from app.core.config import Settings


def test_admin_route_prefix_is_normalized() -> None:
    assert Settings(admin_route_prefix="secret").normalized_admin_route_prefix == "/secret"
    assert Settings(admin_route_prefix="/secret/").normalized_admin_route_prefix == "/secret"
    assert Settings(admin_route_prefix="").normalized_admin_route_prefix == "/admin"
