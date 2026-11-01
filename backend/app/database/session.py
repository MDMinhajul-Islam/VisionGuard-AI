from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
_engine_options = {"pool_pre_ping": True}
if settings.db_url.startswith("sqlite"):
    _engine_options["connect_args"] = {"check_same_thread": False}
engine = create_engine(settings.db_url, **_engine_options)

_actor_id: ContextVar[str | None] = ContextVar("visionguard_actor_id", default=None)
_organization_id: ContextVar[str | None] = ContextVar("visionguard_organization_id", default=None)
_site_ids: ContextVar[tuple[str, ...]] = ContextVar("visionguard_site_ids", default=())


if settings.db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def _postgresql(session: Session) -> bool:
    return session.get_bind().dialect.name == "postgresql"


def bind_actor_context(session: Session, user_id: str) -> None:
    session.info["actor_id"] = user_id
    if _postgresql(session):
        session.execute(text("SELECT visionguard_context.set_actor_context(:user_id)"), {"user_id": user_id})


def bind_tenant_context(session: Session, user_id: str, organization_id: str, site_ids: list[str] | tuple[str, ...]) -> None:
    session.info.update(actor_id=user_id, organization_id=organization_id, site_ids=tuple(site_ids))
    if _postgresql(session):
        session.execute(
            text("SELECT visionguard_context.set_tenant_context(:user_id, :organization_id, CAST(:site_ids AS text[]))"),
            {"user_id": user_id, "organization_id": organization_id, "site_ids": list(site_ids)},
        )


def bind_object_context(session: Session, user_id: str, object_kind: str, object_id: str) -> None:
    session.info.update(actor_id=user_id, object_kind=object_kind, object_id=object_id)
    if _postgresql(session):
        session.execute(
            text("SELECT visionguard_context.set_object_context(:user_id, :object_kind, :object_id)"),
            {"user_id": user_id, "object_kind": object_kind, "object_id": object_id},
        )


def bind_job_context(session: Session, job_id: str) -> None:
    session.info["job_id"] = job_id
    if _postgresql(session):
        session.execute(text("SELECT visionguard_context.set_job_context(:job_id)"), {"job_id": job_id})


@contextmanager
def request_database_context(user_id: str | None, organization_id: str | None = None, site_ids: tuple[str, ...] = ()):
    tokens = (_actor_id.set(user_id), _organization_id.set(organization_id), _site_ids.set(site_ids))
    try:
        yield
    finally:
        _site_ids.reset(tokens[2])
        _organization_id.reset(tokens[1])
        _actor_id.reset(tokens[0])


@event.listens_for(SessionLocal, "after_begin")
def apply_request_context(session, _transaction, connection):
    if not _postgresql(session) or session.info.get("context_bound"):
        return
    actor = session.info.get("actor_id") or _actor_id.get()
    organization = session.info.get("organization_id") or _organization_id.get()
    sites = session.info.get("site_ids") or _site_ids.get()
    session.info["context_bound"] = True
    job_id = session.info.get("job_id")
    if job_id:
        connection.execute(text("SELECT visionguard_context.set_job_context(:job_id)"), {"job_id": job_id})
    elif actor and organization:
        connection.execute(
            text("SELECT visionguard_context.set_tenant_context(:user_id, :organization_id, CAST(:site_ids AS text[]))"),
            {"user_id": actor, "organization_id": organization, "site_ids": list(sites)},
        )
    elif actor:
        connection.execute(text("SELECT visionguard_context.set_actor_context(:user_id)"), {"user_id": actor})


@event.listens_for(SessionLocal, "after_transaction_end")
def clear_transaction_context_marker(session, transaction):
    if not transaction.nested:
        session.info.pop("context_bound", None)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.database import models  # noqa: F401
    from app.database.migrations import run_non_destructive_migrations

    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)
        run_non_destructive_migrations(engine)
        return
    if "alembic_version" not in inspect(engine).get_table_names():
        raise RuntimeError("PostgreSQL schema is not migrated; run alembic upgrade head with the migration role")

