import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def now():
    return datetime.now(timezone.utc)

class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    teacher_name: Mapped[str] = mapped_column(String(200))
    school_name: Mapped[str] = mapped_column(String(250))
    locality: Mapped[str] = mapped_column(String(200))
    subjects: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    lessons = relationship("Lesson", back_populates="workspace", cascade="all, delete-orphan")

class Lesson(Base):
    __tablename__ = "lessons"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    subject: Mapped[str] = mapped_column(String(120))
    grade: Mapped[str] = mapped_column(String(40))
    topic: Mapped[str] = mapped_column(String(300))
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    workspace = relationship("Workspace", back_populates="lessons")

class Publication(Base):
    __tablename__ = "publications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    public_title: Mapped[str] = mapped_column(String(300))
    public_subject: Mapped[str] = mapped_column(String(120))
    public_grade: Mapped[str] = mapped_column(String(40))
    public_topic: Mapped[str] = mapped_column(String(300))
    public_content: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="published")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Event(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class LessonVersion(Base):
    """Снимок документа для истории и восстановления."""
    __tablename__ = "lesson_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Favorite(Base):
    """Избранное: ссылка на публикацию или свой урок."""
    __tablename__ = "favorites"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(20))  # publication | lesson
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Template(Base):
    """Шаблон рабочего пространства (копия структуры без персональных данных)."""
    __tablename__ = "templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    subject: Mapped[str] = mapped_column(String(120), default="")
    grade: Mapped[str] = mapped_column(String(40), default="")
    topic: Mapped[str] = mapped_column(String(300), default="")
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class AppSetting(Base):
    """Ключ-значение для админ-настроек (AI, промпты, флаги)."""
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class AIUsageLog(Base):
    """Учёт вызовов AI: успех, ошибка, провайдер, тип операции."""
    __tablename__ = "ai_usage_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    provider: Mapped[str] = mapped_column(String(40), default="")
    model: Mapped[str] = mapped_column(String(80), default="")
    operation: Mapped[str] = mapped_column(String(80), default="")  # lesson | material | presentation | block | ...
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok | error
    error_message: Mapped[str] = mapped_column(String(500), default="")
    tokens_in: Mapped[int] = mapped_column(default=0)
    tokens_out: Mapped[int] = mapped_column(default=0)
    latency_ms: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
