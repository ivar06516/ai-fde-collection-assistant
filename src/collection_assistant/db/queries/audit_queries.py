from sqlalchemy.orm import Session
from collection_assistant.db.models import WorkflowAudit


def create_audit_record(session: Session, record: WorkflowAudit) -> None:
    session.add(record)
    session.commit()


def get_audit_record(session: Session, workflow_id: str) -> WorkflowAudit | None:
    return session.get(WorkflowAudit, workflow_id)


def list_recent_audits(session: Session, limit: int = 20) -> list[WorkflowAudit]:
    return (
        session.query(WorkflowAudit)
        .order_by(WorkflowAudit.created_at.desc())
        .limit(limit)
        .all()
    )
