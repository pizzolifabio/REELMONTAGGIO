from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc)


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    script: str = ""
    brief: str = ""  # indicazioni libere per il montaggio
    status: str = "draft"  # draft | processing | ready | error
    status_message: str = ""
    current_version: int = 0
    music_asset_id: Optional[int] = None
    created_at: datetime = Field(default_factory=now)


class Asset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: Optional[int] = Field(default=None, foreign_key="project.id", index=True)
    kind: str  # video | music | image
    label: str = ""
    filename: str
    path: str
    duration: float = 0
    width: int = 0
    height: int = 0
    has_audio: bool = True
    transcript: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    position: int = 0
    created_at: datetime = Field(default_factory=now)


class TimelineVersion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    version: int
    edl: dict[str, Any] = Field(sa_column=Column(JSON))
    note: str = ""
    render_path: str = ""
    render_status: str = "pending"  # pending | rendering | done | error
    render_error: str = ""
    created_at: datetime = Field(default_factory=now)


class Feedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    version: int
    timestamp: float
    text: str
    asset_id: Optional[int] = None
    status: str = "pending"  # pending | applying | applied | failed
    applied_in_version: Optional[int] = None
    consolidated: bool = False
    created_at: datetime = Field(default_factory=now)


class SkillProposal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    summary: str = ""
    changes: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    feedback_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    status: str = "pending"  # pending | approved | rejected
    created_at: datetime = Field(default_factory=now)


class Content(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True, unique=True)
    title: str = ""
    caption: str = ""
    hashtags: str = ""
    keyword: str = ""
    dm_message: str = ""
    lead_magnet: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    slug: str = ""
    pdf_path: str = ""
    resource_url: str = ""  # se vuoto si usa PUBLIC_BASE_URL/r/<slug>
    created_at: datetime = Field(default_factory=now)


class Account(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    platform: str = Field(index=True, unique=True)  # instagram | youtube | tiktok
    username: str = ""
    external_id: str = ""
    access_token: str = ""
    refresh_token: str = ""
    expires_at: Optional[datetime] = None
    extra: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    connected_at: datetime = Field(default_factory=now)


class ScheduledPost(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    version: int
    platform: str
    scheduled_at: datetime
    title: str = ""
    caption: str = ""
    privacy: str = "public"
    status: str = "scheduled"  # scheduled | publishing | published | failed | cancelled
    external_id: str = ""
    result_url: str = ""
    error: str = ""
    created_at: datetime = Field(default_factory=now)


class Automation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: Optional[int] = Field(default=None, foreign_key="project.id")
    name: str = ""
    ig_media_id: str = ""  # vuoto = vale per tutti i post
    keyword: str
    opening_message: str = "Ciao! Ecco la risorsa che hai chiesto 👇 Tocca il pulsante qui sotto per riceverla."
    button_label: str = "Inviamela"
    dm_message: str = "Eccola! 🎁"
    resource_url: str = ""
    require_follow: bool = True
    follow_message: str = "Per riceverla devi seguire la pagina 🙏 Seguici e poi tocca di nuovo il pulsante."
    public_reply: str = ""  # risposta pubblica al commento (opzionale)
    active: bool = True
    created_at: datetime = Field(default_factory=now)


class Lead(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    automation_id: int = Field(foreign_key="automation.id", index=True)
    igsid: str = Field(index=True)
    username: str = ""
    comment_id: str = ""
    comment_text: str = ""
    status: str = "contacted"  # contacted | awaiting_follow | sent | error
    error: str = ""
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str
    project_id: Optional[int] = Field(default=None, index=True)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "queued"  # queued | running | done | failed
    progress: float = 0
    message: str = ""
    error: str = ""
    created_at: datetime = Field(default_factory=now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class WebhookEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = "instagram"
    body: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    result: str = ""
    received_at: datetime = Field(default_factory=now)
