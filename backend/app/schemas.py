from pydantic import BaseModel, Field
from typing import Any, Literal

class WorkspaceCreate(BaseModel):
    teacher_name: str = Field(min_length=3, max_length=200)
    school_name: str = Field(min_length=2, max_length=250)
    locality: str = Field(min_length=2, max_length=200)
    subjects: list[str] = Field(min_length=1)

class WorkspaceCreated(BaseModel):
    workspace_id: str
    workspace_key: str
    message: str

class LessonCreate(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    subject: str
    grade: str
    topic: str
    content: dict[str, Any] = {}

class LessonGenerateRequest(BaseModel):
    subject: str = Field(min_length=1)
    grade: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    room_conditions: str = Field(min_length=1)
    language: str = Field(min_length=1)
    methodical_profile: str = ""
    lesson_minutes: int = 45

class PublishRequest(BaseModel):
    confirm_anonymized: bool = False


class LessonUpdate(BaseModel):
    title: str
    subject: str
    grade: str
    topic: str
    content: dict


class RegenerateRequest(BaseModel):
    instruction: str = Field(default="", max_length=1000)


class MaterialGenerateRequest(BaseModel):
    kind: Literal["tasks_abc", "cards", "worksheet", "test", "rubric"]
    subject: str = Field(min_length=1, max_length=120)
    grade: str = Field(min_length=1, max_length=40)
    topic: str = Field(min_length=1, max_length=300)
    language: str = Field(min_length=1)
    room_conditions: str = Field(default="", max_length=500)
    methodical_profile: str = Field(default="", max_length=500)
    instruction: str = Field(default="", max_length=1000)
    count: int = Field(default=6, ge=1, le=20)
    test_format: str = Field(default="выбор ответа", max_length=60)
    lesson_id: str | None = None


class VariantsRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=4)
    instruction: str = Field(default="", max_length=1000)


class PresentationGenerateRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    grade: str = Field(min_length=1, max_length=40)
    topic: str = Field(min_length=1, max_length=300)
    language: str = Field(min_length=1)
    room_conditions: str = Field(default="", max_length=500)
    methodical_profile: str = Field(default="", max_length=500)
    instruction: str = Field(default="", max_length=1000)
    slide_count: int = Field(default=10, ge=6, le=14)
    lesson_id: str | None = None


class SlideRegenerateRequest(BaseModel):
    instruction: str = Field(default="", max_length=1000)


class PlanningGenerateRequest(BaseModel):
    kind: Literal["ktp", "sor", "soch", "diagnostic", "year_plan", "theme_plan"]
    subject: str = Field(min_length=1, max_length=120)
    grade: str = Field(min_length=1, max_length=40)
    topic: str = Field(min_length=1, max_length=300)
    language: str = Field(min_length=1)
    room_conditions: str = Field(default="", max_length=500)
    methodical_profile: str = Field(default="", max_length=500)
    instruction: str = Field(default="", max_length=1000)
    hours: int = Field(default=8, ge=1, le=140)
    lesson_id: str | None = None


class FavoriteCreate(BaseModel):
    target_type: Literal["publication", "lesson"]
    target_id: str = Field(min_length=8, max_length=40)


class TemplateCreate(BaseModel):
    lesson_id: str = Field(min_length=8, max_length=40)
    title: str = Field(default="", max_length=300)


class VersionRestoreRequest(BaseModel):
    note: str = Field(default="", max_length=300)
