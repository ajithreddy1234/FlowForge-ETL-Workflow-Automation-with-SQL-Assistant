from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base, PipelineVersion, User, app_now
from api.pipeline_storage import list_pipeline_versions, save_index_pipeline


def test_each_save_creates_an_immutable_pipeline_version():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        user = User(
            login_id="admin",
            display_name="Admin",
            password_hash="unused",
            role="admin",
            is_active=True,
            created_at=app_now(),
        )
        session.add(user)
        session.commit()

        first = save_index_pipeline(
            session,
            {"report_name": "Revenue", "extract": {"queries": []}},
            user,
        )
        second = save_index_pipeline(
            session,
            {"report_name": "Revenue", "extract": {"queries": [{"index": 1, "name": "orders", "query": "SELECT 1"}]}},
            user,
            existing_name=first["name"],
        )

        assert first["version"] == 1
        assert second["version"] == 2
        versions = list_pipeline_versions(session, first["name"])
        assert [item["version"] for item in versions] == [2, 1]
        assert session.query(PipelineVersion).count() == 2
        assert versions[0]["content_hash"] != versions[1]["content_hash"]
    finally:
        session.close()
        engine.dispose()
