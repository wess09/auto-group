from sqlmodel import Session, SQLModel, create_engine

from app.api.admin import _status_value
from app.models import DedupeJob
from app.models.entities import TaskStatus


def test_dedupe_status_value_is_plain_enum_value() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        job = DedupeJob(status=TaskStatus.preview)
        session.add(job)
        session.commit()
        session.refresh(job)

    assert _status_value(job.status) == "preview"
