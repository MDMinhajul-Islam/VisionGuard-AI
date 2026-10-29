from sqlalchemy import create_engine, text

from app.database.migrations import LEGACY_RESEARCH_ORG_ID, LEGACY_RESEARCH_SITE_ID, run_non_destructive_migrations
from app.database.session import Base


def test_legacy_video_migration_is_idempotent_and_preserves_ids(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE videos (id VARCHAR(36) PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE candidate_events (id VARCHAR(36) PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE exported_clips (id VARCHAR(36) PRIMARY KEY)"))
        connection.execute(text("INSERT INTO videos (id) VALUES ('legacy-video')"))
    # Create only the new ownership/session/audit tables around the intentionally old core tables.
    for table in Base.metadata.sorted_tables:
        if table.name not in {"users", "videos", "candidate_events", "exported_clips"}:
            table.create(engine, checkfirst=True)
    first = run_non_destructive_migrations(engine)
    second = run_non_destructive_migrations(engine)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT id, organization_id, site_id FROM videos WHERE id='legacy-video'" )).one()
    assert row == ("legacy-video", LEGACY_RESEARCH_ORG_ID, LEGACY_RESEARCH_SITE_ID)
    assert first["legacy_videos_scoped"] == 1
    assert second["legacy_videos_scoped"] == 0
