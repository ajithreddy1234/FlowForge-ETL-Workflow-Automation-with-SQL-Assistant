from api.connection_profiles import connection_to_dict
from api.database import ConnectionProfile


def test_connection_response_never_contains_encrypted_password():
    profile = ConnectionProfile(
        id=7,
        created_by_user_id=1,
        name="Warehouse",
        db_type="mysql",
        host="db.internal",
        port="3306",
        database_name="analytics",
        username="reader",
        encrypted_password="must-never-leave-server",
        allowed_schemas_json='["analytics"]',
        status="active",
    )
    payload = connection_to_dict(profile)
    assert payload["id"] == 7
    assert "password" not in payload
    assert "encrypted_password" not in payload
