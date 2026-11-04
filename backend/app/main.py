import secrets, re
from pathlib import Path
from io import BytesIO
from urllib.parse import quote
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from .db import Base, engine, get_db
from .models import Workspace, Lesson, Publication, Event, LessonVersion, Favorite, Template, AIUsageLog, AppSetting
from .schemas import WorkspaceCreate, WorkspaceCreated, LessonCreate, LessonUpdate, PublishRequest
from .security import digest, require_workspace_key, require_admin
from .schemas import LessonGenerateRequest, RegenerateRequest, MaterialGenerateRequest, VariantsRequest
from .ai.lesson_service import generate_lesson
from .ai.providers import AIConfigurationError
from .ai.block_service import regenerate_block, warnings_with_parts, AIOutputError
from .doc_model import (normalize_content, build_content_from_generated, check_document,
                        find_block, redact_terms)
from .export_docx import build_docx
from .ai.constructor_service import generate_material, generate_variants
from .doc_model import DOC_TYPES, build_material_content, blocks_from_variants, block_to_plain
from .schemas import PresentationGenerateRequest, SlideRegenerateRequest
from .ai.presentation_service import generate_presentation, regenerate_slide
from .presentation_model import (build_presentation_content, sanitize_presentation,
                                  check_presentation, find_slide, parse_presentation_markdown)
from .export_pptx import build_pptx
from .export_xlsx import build_xlsx
from .admin_settings import (
    get_ai_config, set_ai_config, get_subject_prompts, set_subject_prompts,
    get_base_prompt, set_base_prompt, ai_keys_status,
)
from .ai.prompts import set_runtime_prompts
from .ai.providers import set_usage_hook

from .schemas import PlanningGenerateRequest, FavoriteCreate, TemplateCreate, VersionRestoreRequest
from .ai.planning_service import generate_planning
from .doc_model import PLAN_TYPES

Base.metadata.create_all(bind=engine)

def _log_ai_usage(provider="", model="", status="ok", error_message="", latency_ms=0, **_):
    try:
        from .db import SessionLocal
        db = SessionLocal()
        try:
            db.add(AIUsageLog(
                provider=str(provider)[:40], model=str(model)[:80],
                status=str(status)[:20], error_message=str(error_message)[:500],
                latency_ms=int(latency_ms or 0), operation="generate",
            ))
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


def _install_ai_hooks():
    set_usage_hook(_log_ai_usage)
    try:
        from .db import SessionLocal
        db = SessionLocal()
        try:
            set_runtime_prompts(get_base_prompt(db), get_subject_prompts(db))
        finally:
            db.close()
    except Exception:
        pass


_install_ai_hooks()

app = FastAPI(title="USTAZ AI PRO MAX API", version="0.1.0")

def log(db, workspace_id, event_type, details=None):
    db.add(Event(workspace_id=workspace_id, event_type=event_type, details=details or {}))
    db.commit()

def get_workspace(db: Session, key_hash: str):
    ws = db.scalar(select(Workspace).where(Workspace.key_hash == key_hash))
    if not ws:
        raise HTTPException(404, "Workspace not found")
    return ws



def snapshot_version(db: Session, lesson: Lesson, note: str = ""):
    """Сохраняет снимок; хранит не более 20 последних версий урока."""
    db.add(LessonVersion(
        lesson_id=lesson.id, workspace_id=lesson.workspace_id,
        title=lesson.title or "", content=lesson.content or {}, note=(note or "")[:300],
    ))
    db.flush()
    ids = db.scalars(
        select(LessonVersion.id).where(LessonVersion.lesson_id == lesson.id)
        .order_by(LessonVersion.created_at.desc())
    ).all()
    for old_id in ids[20:]:
        old = db.get(LessonVersion, old_id)
        if old:
            db.delete(old)

def private_terms(ws):
    return [ws.teacher_name, ws.school_name]

def own_lesson(db: Session, key_hash: str, lesson_id: str):
    ws = get_workspace(db, key_hash)
    lesson = db.scalar(select(Lesson).where(Lesson.id == lesson_id, Lesson.workspace_id == ws.id))
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    return ws, lesson

@app.post("/api/lessons/generate")
async def generate_lesson_endpoint(payload: LessonGenerateRequest,
                                   key_hash: str = Depends(require_workspace_key),
                                   db: Session = Depends(get_db)):
    ws = get_workspace(db, key_hash)
    try:
        result = await generate_lesson(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except AIConfigurationError as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        raise HTTPException(502, "Ошибка AI-провайдера. Проверьте настройки сервера.")
    content = build_content_from_generated(result, payload.language, payload.room_conditions)
    lesson = Lesson(workspace_id=ws.id, title=f"КСП — {payload.topic}",
                    subject=payload.subject, grade=payload.grade, topic=payload.topic, content=content)
    db.add(lesson); db.commit(); db.refresh(lesson)
    log(db, ws.id, "lesson_generated", {"lesson_id": lesson.id, "subject": payload.subject, "grade": payload.grade})
    return {"id": lesson.id, "title": lesson.title, "warnings": check_document(content, private_terms(ws))}

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "USTAZ AI PRO MAX"}

@app.post("/api/workspaces", response_model=WorkspaceCreated)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db)):
    raw_key = secrets.token_urlsafe(48)
    ws = Workspace(key_hash=digest(raw_key), teacher_name=payload.teacher_name.strip(),
                   school_name=payload.school_name.strip(), locality=payload.locality.strip(),
                   subjects=[s.strip() for s in payload.subjects if s.strip()])
    db.add(ws); db.commit(); db.refresh(ws)
    log(db, ws.id, "workspace_created", {"subjects_count": len(ws.subjects)})
    return {"workspace_id": ws.id, "workspace_key": raw_key, "message": "Сохраните ключ рабочего пространства. Он понадобится для восстановления доступа."}

@app.get("/api/workspaces/me")
def workspace_me(key_hash: str = Depends(require_workspace_key), db: Session = Depends(get_db)):
    ws = get_workspace(db, key_hash)
    return {"id": ws.id, "teacher_name": ws.teacher_name, "school_name": ws.school_name,
            "locality": ws.locality, "subjects": ws.subjects, "created_at": ws.created_at}

@app.post("/api/lessons")
def create_lesson(payload: LessonCreate, key_hash: str = Depends(require_workspace_key), db: Session = Depends(get_db)):
    ws = get_workspace(db, key_hash)
    lesson = Lesson(workspace_id=ws.id, title=payload.title, subject=payload.subject,
                    grade=payload.grade, topic=payload.topic, content=payload.content)
    db.add(lesson); db.commit(); db.refresh(lesson)
    log(db, ws.id, "lesson_created", {"lesson_id": lesson.id, "subject": lesson.subject, "grade": lesson.grade})
    return {"id": lesson.id, "title": lesson.title}

@app.get("/api/lessons")
def list_lessons(key_hash: str = Depends(require_workspace_key), db: Session = Depends(get_db)):
    ws = get_workspace(db, key_hash)
    rows = db.scalars(select(Lesson).where(Lesson.workspace_id == ws.id).order_by(Lesson.created_at.desc())).all()
    return [{"id": x.id, "title": x.title, "subject": x.subject, "grade": x.grade, "topic": x.topic,
             "content": x.content, "created_at": x.created_at} for x in rows]

def strip_private(obj):
    # Conservative first-pass redaction. Production publication must also inspect
    # DOCX/PDF metadata, headers/footers, embedded images and OCR before release.
    forbidden = re.compile(r"(фио|ф\.и\.о\.|учитель|школа|teacher|school|телефон|email|e-mail|@)", re.I)
    if isinstance(obj, dict):
        return {k: strip_private(v) for k, v in obj.items()
                if not forbidden.search(str(k))}
    if isinstance(obj, list):
        return [strip_private(v) for v in obj]
    if isinstance(obj, str):
        obj = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-zА-Яа-я]{2,}", "[СКРЫТО]", obj)
        obj = re.sub(r"\+?\d[\d()\- ]{7,}\d", "[СКРЫТО]", obj)
        return obj
    return obj

@app.post("/api/lessons/{lesson_id}/publish")
def publish_lesson(lesson_id: str, payload: PublishRequest,
                   key_hash: str = Depends(require_workspace_key), db: Session = Depends(get_db)):
    if not payload.confirm_anonymized:
        raise HTTPException(400, "Подтвердите проверку обезличенной копии")
    ws = get_workspace(db, key_hash)
    lesson = db.scalar(select(Lesson).where(Lesson.id == lesson_id, Lesson.workspace_id == ws.id))
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    public = Publication(lesson_id=lesson.id, public_title=lesson.title, public_subject=lesson.subject,
                         public_grade=lesson.grade, public_topic=lesson.topic,
                         public_content=redact_terms(strip_private(normalize_content(lesson.content)), private_terms(ws)),
                         status="pending_review")
    db.add(public); db.commit(); db.refresh(public)
    log(db, ws.id, "lesson_published", {"publication_id": public.id})
    return {"publication_id": public.id, "status": "pending_review", "note": "Материал ожидает проверки главным администратором. До одобрения он не виден в общей библиотеке."}

@app.get("/api/library")
def public_library(subject: str | None = None, grade: str | None = None, q: str | None = None,
                   db: Session = Depends(get_db)):
    stmt = select(Publication).where(Publication.status == "published")
    rows = db.scalars(stmt.order_by(Publication.created_at.desc()).limit(200)).all()
    out = []
    for x in rows:
        if subject and subject.lower() not in (x.public_subject or "").lower():
            continue
        if grade and grade.lower() not in (x.public_grade or "").lower():
            continue
        if q:
            blob = f"{x.public_title} {x.public_topic} {x.public_subject}".lower()
            if q.lower() not in blob:
                continue
        doc_type = (x.public_content or {}).get("doc_type", "ksp") if isinstance(x.public_content, dict) else "ksp"
        out.append({"id": x.id, "title": x.public_title, "subject": x.public_subject, "grade": x.public_grade,
                    "topic": x.public_topic, "content": x.public_content, "doc_type": doc_type,
                    "created_at": x.created_at})
    return out

@app.get("/api/admin/overview", dependencies=[Depends(require_admin)])
def admin_overview(db: Session = Depends(get_db)):
    ai_ok = db.scalar(select(func.count()).select_from(AIUsageLog).where(AIUsageLog.status == "ok")) or 0
    ai_err = db.scalar(select(func.count()).select_from(AIUsageLog).where(AIUsageLog.status == "error")) or 0
    pending = db.scalar(select(func.count()).select_from(Publication).where(Publication.status == "pending_review")) or 0
    return {
        "workspaces": db.scalar(select(func.count()).select_from(Workspace)) or 0,
        "lessons": db.scalar(select(func.count()).select_from(Lesson)) or 0,
        "publications": db.scalar(select(func.count()).select_from(Publication)) or 0,
        "pending_review": pending,
        "events": db.scalar(select(func.count()).select_from(Event)) or 0,
        "ai_ok": ai_ok,
        "ai_errors": ai_err,
    }

@app.get("/api/admin/workspaces", dependencies=[Depends(require_admin)])
def admin_workspaces(db: Session = Depends(get_db)):
    rows = db.scalars(select(Workspace).order_by(Workspace.created_at.desc())).all()
    return [{"id": w.id, "teacher_name": w.teacher_name, "school_name": w.school_name,
             "locality": w.locality, "subjects": w.subjects, "created_at": w.created_at} for w in rows]

@app.get("/api/admin/lessons", dependencies=[Depends(require_admin)])
def admin_lessons(db: Session = Depends(get_db)):
    rows = db.scalars(select(Lesson).order_by(Lesson.created_at.desc())).all()
    return [{"id": l.id, "workspace_id": l.workspace_id, "title": l.title, "subject": l.subject,
             "grade": l.grade, "topic": l.topic, "content": l.content, "created_at": l.created_at} for l in rows]


@app.get("/api/admin/publications", dependencies=[Depends(require_admin)])
def admin_publications(db: Session = Depends(get_db)):
    rows = db.scalars(select(Publication).order_by(Publication.created_at.desc())).all()
    return [{"id": p.id, "lesson_id": p.lesson_id, "title": p.public_title,
             "subject": p.public_subject, "grade": p.public_grade, "topic": p.public_topic,
             "content": p.public_content, "status": p.status, "created_at": p.created_at}
            for p in rows]

@app.post("/api/admin/publications/{publication_id}/approve", dependencies=[Depends(require_admin)])
def approve_publication(publication_id: str, db: Session = Depends(get_db)):
    publication = db.get(Publication, publication_id)
    if not publication:
        raise HTTPException(404, "Publication not found")
    publication.status = "published"
    db.add(publication)
    db.commit()
    log(db, None, "publication_approved", {"publication_id": publication.id})
    return {"id": publication.id, "status": publication.status}

@app.post("/api/admin/publications/{publication_id}/reject", dependencies=[Depends(require_admin)])
def reject_publication(publication_id: str, db: Session = Depends(get_db)):
    publication = db.get(Publication, publication_id)
    if not publication:
        raise HTTPException(404, "Publication not found")
    publication.status = "rejected"
    db.add(publication)
    db.commit()
    log(db, None, "publication_rejected", {"publication_id": publication.id})
    return {"id": publication.id, "status": publication.status}

@app.get("/api/admin/events", dependencies=[Depends(require_admin)])
def admin_events(db: Session = Depends(get_db)):
    rows = db.scalars(select(Event).order_by(Event.created_at.desc()).limit(1000)).all()
    return [{"id": e.id, "workspace_id": e.workspace_id, "event_type": e.event_type,
             "details": e.details, "created_at": e.created_at} for e in rows]



@app.post("/api/materials/generate")
async def generate_material_endpoint(payload: MaterialGenerateRequest,
                                     key_hash: str = Depends(require_workspace_key), db: Session = Depends(get_db)):
    ws = get_workspace(db, key_hash)
    context = ""
    if payload.lesson_id:
        _, src = own_lesson(db, key_hash, payload.lesson_id)
        src_content = normalize_content(src.content)
        first = next((b for b in src_content["blocks"] if b.get("module") == 1 or src_content["doc_type"] != "ksp"), None)
        context = block_to_plain(first, 2500) if first else ""
    data = payload.model_dump()
    try:
        text = await generate_material(payload.kind, data, context)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except AIConfigurationError as exc:
        raise HTTPException(503, str(exc))
    except Exception:
        raise HTTPException(502, "Ошибка AI-провайдера. Проверьте настройки сервера.")
    params = {"count": payload.count} if payload.kind in ("cards", "test", "rubric") else {}
    content = build_material_content(text, payload.kind, payload.language, payload.room_conditions, params)
    lesson = Lesson(workspace_id=ws.id, title=f"{DOC_TYPES[payload.kind]} — {payload.topic}"[:300],
                    subject=payload.subject, grade=payload.grade, topic=payload.topic, content=content)
    db.add(lesson); db.commit(); db.refresh(lesson)
    log(db, ws.id, "material_generated", {"lesson_id": lesson.id, "kind": payload.kind})
    return {"id": lesson.id, "title": lesson.title, "warnings": check_document(content, private_terms(ws))}

@app.post("/api/lessons/{lesson_id}/variants")
async def create_variants(lesson_id: str, payload: VariantsRequest,
                          key_hash: str = Depends(require_workspace_key), db: Session = Depends(get_db)):
    ws, lesson = own_lesson(db, key_hash, lesson_id)
    content = normalize_content(lesson.content)
    meta = {"subject": lesson.subject, "grade": lesson.grade, "topic": lesson.topic}
    try:
        text = await generate_variants(meta, content, payload.count, payload.instruction)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except AIConfigurationError as exc:
        raise HTTPException(503, str(exc))
    except Exception:
        raise HTTPException(502, "Ошибка AI-провайдера. Проверьте настройки сервера.")
    blocks = blocks_from_variants(text)
    log(db, ws.id, "variants_generated", {"lesson_id": lesson.id, "count": payload.count})
    return {"blocks": blocks}

@app.get("/api/lessons/{lesson_id}")
def get_lesson(lesson_id: str, key_hash: str = Depends(require_workspace_key), db: Session = Depends(get_db)):
    ws, lesson = own_lesson(db, key_hash, lesson_id)
    content = normalize_content(lesson.content)
    return {"id": lesson.id, "title": lesson.title, "subject": lesson.subject, "grade": lesson.grade,
            "topic": lesson.topic, "content": content, "warnings": check_document(content, private_terms(ws))}

@app.put("/api/lessons/{lesson_id}")
def update_lesson(lesson_id: str, payload: LessonUpdate,
                  key_hash: str = Depends(require_workspace_key), db: Session = Depends(get_db)):
    ws, lesson = own_lesson(db, key_hash, lesson_id)
    content = normalize_content(payload.content)  # лимиты, пять модулей, уникальные id
    # снимок до изменения (если уже было содержимое)
    if lesson.content:
        snapshot_version(db, lesson, "до сохранения")
    lesson.title = payload.title.strip()
    lesson.subject = payload.subject.strip()
    lesson.grade = payload.grade.strip()
    lesson.topic = payload.topic.strip()
    lesson.content = content
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    log(db, ws.id, "lesson_updated", {"lesson_id": lesson.id})
    return {"id": lesson.id, "title": lesson.title, "updated_at": lesson.updated_at,
            "content": content, "warnings": check_document(content, private_terms(ws))}

@app.post("/api/lessons/{lesson_id}/blocks/{block_id}/regenerate")
async def regenerate_lesson_block(lesson_id: str, block_id: str, payload: RegenerateRequest,
                                  key_hash: str = Depends(require_workspace_key), db: Session = Depends(get_db)):
    ws, lesson = own_lesson(db, key_hash, lesson_id)
    content = normalize_content(lesson.content)
    meta = {"subject": lesson.subject, "grade": lesson.grade, "topic": lesson.topic}
    try:
        parts = await regenerate_block(meta, content, block_id, payload.instruction)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except AIConfigurationError as exc:
        raise HTTPException(503, str(exc))
    except AIOutputError as exc:
        raise HTTPException(502, str(exc))
    except Exception:
        raise HTTPException(502, "Ошибка AI-провайдера. Проверьте настройки сервера.")
    block = find_block(content, block_id)
    log(db, ws.id, "block_regenerated", {"lesson_id": lesson.id, "module": block.get("module")})
    return {"parts": parts, "warnings": warnings_with_parts(content, block_id, parts, private_terms(ws))}

@app.get("/api/lessons/{lesson_id}/export.docx")
def export_lesson_docx(lesson_id: str, key_hash: str = Depends(require_workspace_key),
                       db: Session = Depends(get_db)):
    ws, lesson = own_lesson(db, key_hash, lesson_id)
    stream = build_docx({"title": lesson.title, "subject": lesson.subject, "grade": lesson.grade,
                         "topic": lesson.topic}, normalize_content(lesson.content))
    safe_name = re.sub(r"[^A-Za-zА-Яа-я0-9_-]+", "_", lesson.title or "KSP")[:60] or "KSP"
    log(db, ws.id, "lesson_exported_docx", {"lesson_id": lesson.id})
    return StreamingResponse(
        stream, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(safe_name)}.docx"})



@app.post("/api/presentations/generate")
async def generate_presentation_endpoint(payload: PresentationGenerateRequest,
                                         key_hash: str = Depends(require_workspace_key),
                                         db: Session = Depends(get_db)):
    ws = get_workspace(db, key_hash)
    context = ""
    if payload.lesson_id:
        _, src = own_lesson(db, key_hash, payload.lesson_id)
        src_content = normalize_content(src.content) if (src.content or {}).get("doc_type", "ksp") != "presentation" else src.content
        if isinstance(src_content, dict) and src_content.get("blocks"):
            first = next((b for b in src_content["blocks"] if b.get("module") == 1), src_content["blocks"][0])
            context = block_to_plain(first, 2500)
        elif isinstance(src_content, dict) and src_content.get("slides"):
            context = "\n".join(f"{s.get('title','')}: {s.get('body','')}" for s in src_content["slides"][:3])
    data = payload.model_dump()
    try:
        text = await generate_presentation(data, context)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except AIConfigurationError as exc:
        raise HTTPException(503, str(exc))
    except Exception:
        raise HTTPException(502, "Ошибка AI-провайдера. Проверьте настройки сервера.")
    content = build_presentation_content(text, payload.language, payload.room_conditions)
    lesson = Lesson(workspace_id=ws.id, title=f"Презентация — {payload.topic}"[:300],
                    subject=payload.subject, grade=payload.grade, topic=payload.topic, content=content)
    db.add(lesson); db.commit(); db.refresh(lesson)
    log(db, ws.id, "presentation_generated", {"lesson_id": lesson.id, "slides": len(content.get("slides") or [])})
    return {"id": lesson.id, "title": lesson.title, "warnings": check_presentation(content)}


@app.get("/api/presentations/{lesson_id}")
def get_presentation(lesson_id: str, key_hash: str = Depends(require_workspace_key), db: Session = Depends(get_db)):
    ws, lesson = own_lesson(db, key_hash, lesson_id)
    content = lesson.content or {}
    if content.get("doc_type") != "presentation":
        raise HTTPException(400, "Это не презентация")
    content = sanitize_presentation(content)
    return {"id": lesson.id, "title": lesson.title, "subject": lesson.subject, "grade": lesson.grade,
            "topic": lesson.topic, "content": content, "warnings": check_presentation(content)}


@app.put("/api/presentations/{lesson_id}")
def update_presentation(lesson_id: str, payload: LessonUpdate,
                        key_hash: str = Depends(require_workspace_key), db: Session = Depends(get_db)):
    ws, lesson = own_lesson(db, key_hash, lesson_id)
    content = sanitize_presentation(payload.content)
    if lesson.content:
        snapshot_version(db, lesson, "до сохранения презентации")
    lesson.title = payload.title.strip()
    lesson.subject = payload.subject.strip()
    lesson.grade = payload.grade.strip()
    lesson.topic = payload.topic.strip()
    lesson.content = content
    db.add(lesson); db.commit(); db.refresh(lesson)
    log(db, ws.id, "presentation_updated", {"lesson_id": lesson.id})
    return {"id": lesson.id, "title": lesson.title, "updated_at": lesson.updated_at,
            "content": content, "warnings": check_presentation(content)}


@app.post("/api/presentations/{lesson_id}/slides/{slide_id}/regenerate")
async def regenerate_presentation_slide(lesson_id: str, slide_id: str, payload: SlideRegenerateRequest,
                                        key_hash: str = Depends(require_workspace_key), db: Session = Depends(get_db)):
    ws, lesson = own_lesson(db, key_hash, lesson_id)
    content = sanitize_presentation(lesson.content or {})
    slide = find_slide(content, slide_id)
    if not slide:
        raise HTTPException(404, "Слайд не найден")
    meta = {"subject": lesson.subject, "grade": lesson.grade, "topic": lesson.topic}
    try:
        text = await regenerate_slide(meta, content, slide, payload.instruction)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except AIConfigurationError as exc:
        raise HTTPException(503, str(exc))
    except Exception:
        raise HTTPException(502, "Ошибка AI-провайдера. Проверьте настройки сервера.")
    parsed = parse_presentation_markdown(text)
    if not parsed:
        raise HTTPException(502, "AI вернул пустой слайд. Повторите.")
    new_slide = parsed[0]
    new_slide["id"] = slide_id
    log(db, ws.id, "slide_regenerated", {"lesson_id": lesson.id, "slide_id": slide_id})
    return {"slide": new_slide, "warnings": check_presentation({**content, "slides": [
        new_slide if s["id"] == slide_id else s for s in content["slides"]
    ]})}


@app.get("/api/presentations/{lesson_id}/export.pptx")
def export_presentation_pptx(lesson_id: str, key_hash: str = Depends(require_workspace_key),
                             db: Session = Depends(get_db)):
    ws, lesson = own_lesson(db, key_hash, lesson_id)
    content = sanitize_presentation(lesson.content or {})
    if content.get("doc_type") != "presentation":
        raise HTTPException(400, "Это не презентация")
    stream = build_pptx({"title": lesson.title, "subject": lesson.subject,
                         "grade": lesson.grade, "topic": lesson.topic}, content)
    safe_name = re.sub(r"[^A-Za-zА-Яа-я0-9_-]+", "_", lesson.title or "Presentation")[:60] or "Presentation"
    log(db, ws.id, "presentation_exported_pptx", {"lesson_id": lesson.id})
    return StreamingResponse(
        stream, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(safe_name)}.pptx"})



@app.post("/api/planning/generate")
async def generate_planning_endpoint(payload: PlanningGenerateRequest,
                                     key_hash: str = Depends(require_workspace_key),
                                     db: Session = Depends(get_db)):
    ws = get_workspace(db, key_hash)
    context = ""
    if payload.lesson_id:
        _, src = own_lesson(db, key_hash, payload.lesson_id)
        src_content = normalize_content(src.content)
        if src_content.get("blocks"):
            first = next((b for b in src_content["blocks"] if b.get("module") == 1), src_content["blocks"][0])
            context = block_to_plain(first, 2500)
        elif src_content.get("slides"):
            context = "\n".join(f"{s.get('title','')}" for s in src_content["slides"][:5])
    data = payload.model_dump()
    try:
        text = await generate_planning(payload.kind, data, context)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except AIConfigurationError as exc:
        raise HTTPException(503, str(exc))
    except Exception:
        raise HTTPException(502, "Ошибка AI-провайдера. Проверьте настройки сервера.")
    params = {"hours": payload.hours}
    content = build_material_content(text, payload.kind, payload.language, payload.room_conditions, params)
    lesson = Lesson(workspace_id=ws.id, title=f"{DOC_TYPES[payload.kind]} — {payload.topic}"[:300],
                    subject=payload.subject, grade=payload.grade, topic=payload.topic, content=content)
    db.add(lesson); db.commit(); db.refresh(lesson)
    log(db, ws.id, "planning_generated", {"lesson_id": lesson.id, "kind": payload.kind})
    return {"id": lesson.id, "title": lesson.title, "warnings": check_document(content, private_terms(ws))}



# ---------- Этап 8: история, избранное, шаблоны, клон из библиотеки ----------

@app.get("/api/lessons/{lesson_id}/versions")
def list_versions(lesson_id: str, key_hash: str = Depends(require_workspace_key), db: Session = Depends(get_db)):
    ws, lesson = own_lesson(db, key_hash, lesson_id)
    rows = db.scalars(
        select(LessonVersion).where(LessonVersion.lesson_id == lesson.id)
        .order_by(LessonVersion.created_at.desc()).limit(20)
    ).all()
    return [{"id": v.id, "title": v.title, "note": v.note, "created_at": v.created_at,
             "doc_type": (v.content or {}).get("doc_type", "ksp") if isinstance(v.content, dict) else "ksp"}
            for v in rows]


@app.post("/api/lessons/{lesson_id}/versions/{version_id}/restore")
def restore_version(lesson_id: str, version_id: str,
                    key_hash: str = Depends(require_workspace_key), db: Session = Depends(get_db)):
    ws, lesson = own_lesson(db, key_hash, lesson_id)
    ver = db.scalar(select(LessonVersion).where(
        LessonVersion.id == version_id, LessonVersion.lesson_id == lesson.id))
    if not ver:
        raise HTTPException(404, "Версия не найдена")
    snapshot_version(db, lesson, "перед восстановлением")
    content = normalize_content(ver.content)
    lesson.title = ver.title or lesson.title
    lesson.content = content
    db.add(lesson); db.commit(); db.refresh(lesson)
    log(db, ws.id, "version_restored", {"lesson_id": lesson.id, "version_id": version_id})
    return {"id": lesson.id, "title": lesson.title, "content": content,
            "warnings": check_document(content, private_terms(ws))}


@app.get("/api/favorites")
def list_favorites(key_hash: str = Depends(require_workspace_key), db: Session = Depends(get_db)):
    ws = get_workspace(db, key_hash)
    rows = db.scalars(select(Favorite).where(Favorite.workspace_id == ws.id)
                      .order_by(Favorite.created_at.desc())).all()
    out = []
    for f in rows:
        item = {"id": f.id, "target_type": f.target_type, "target_id": f.target_id, "created_at": f.created_at}
        if f.target_type == "publication":
            pub = db.get(Publication, f.target_id)
            if pub and pub.status == "published":
                item.update({"title": pub.public_title, "subject": pub.public_subject,
                             "grade": pub.public_grade, "topic": pub.public_topic})
            else:
                continue
        else:
            les = db.scalar(select(Lesson).where(Lesson.id == f.target_id, Lesson.workspace_id == ws.id))
            if les:
                item.update({"title": les.title, "subject": les.subject, "grade": les.grade, "topic": les.topic})
            else:
                continue
        out.append(item)
    return out


@app.post("/api/favorites")
def add_favorite(payload: FavoriteCreate, key_hash: str = Depends(require_workspace_key),
                 db: Session = Depends(get_db)):
    ws = get_workspace(db, key_hash)
    if payload.target_type == "publication":
        pub = db.get(Publication, payload.target_id)
        if not pub or pub.status != "published":
            raise HTTPException(404, "Публикация не найдена")
    else:
        les = db.scalar(select(Lesson).where(Lesson.id == payload.target_id, Lesson.workspace_id == ws.id))
        if not les:
            raise HTTPException(404, "Урок не найден")
    exists = db.scalar(select(Favorite).where(
        Favorite.workspace_id == ws.id, Favorite.target_type == payload.target_type,
        Favorite.target_id == payload.target_id))
    if exists:
        return {"id": exists.id, "status": "exists"}
    fav = Favorite(workspace_id=ws.id, target_type=payload.target_type, target_id=payload.target_id)
    db.add(fav); db.commit(); db.refresh(fav)
    log(db, ws.id, "favorite_added", {"favorite_id": fav.id, "target_type": payload.target_type})
    return {"id": fav.id, "status": "created"}


@app.delete("/api/favorites/{favorite_id}")
def remove_favorite(favorite_id: str, key_hash: str = Depends(require_workspace_key),
                    db: Session = Depends(get_db)):
    ws = get_workspace(db, key_hash)
    fav = db.scalar(select(Favorite).where(Favorite.id == favorite_id, Favorite.workspace_id == ws.id))
    if not fav:
        raise HTTPException(404, "Не найдено")
    db.delete(fav); db.commit()
    log(db, ws.id, "favorite_removed", {"favorite_id": favorite_id})
    return {"ok": True}


@app.get("/api/templates")
def list_templates(key_hash: str = Depends(require_workspace_key), db: Session = Depends(get_db)):
    ws = get_workspace(db, key_hash)
    rows = db.scalars(select(Template).where(Template.workspace_id == ws.id)
                      .order_by(Template.created_at.desc())).all()
    return [{"id": x.id, "title": x.title, "subject": x.subject, "grade": x.grade,
             "topic": x.topic, "doc_type": (x.content or {}).get("doc_type", "ksp"),
             "created_at": x.created_at} for x in rows]


@app.post("/api/templates")
def create_template(payload: TemplateCreate, key_hash: str = Depends(require_workspace_key),
                    db: Session = Depends(get_db)):
    ws, lesson = own_lesson(db, key_hash, payload.lesson_id)
    content = normalize_content(lesson.content)
    # обезличить на всякий случай
    content = redact_terms(content, private_terms(ws))
    title = (payload.title or lesson.title or "Шаблон").strip()[:300]
    tpl = Template(workspace_id=ws.id, title=title, subject=lesson.subject,
                   grade=lesson.grade, topic=lesson.topic, content=content)
    db.add(tpl); db.commit(); db.refresh(tpl)
    log(db, ws.id, "template_created", {"template_id": tpl.id, "from_lesson": lesson.id})
    return {"id": tpl.id, "title": tpl.title}


@app.post("/api/templates/{template_id}/use")
def use_template(template_id: str, key_hash: str = Depends(require_workspace_key),
                 db: Session = Depends(get_db)):
    ws = get_workspace(db, key_hash)
    tpl = db.scalar(select(Template).where(Template.id == template_id, Template.workspace_id == ws.id))
    if not tpl:
        raise HTTPException(404, "Шаблон не найден")
    content = normalize_content(tpl.content)
    lesson = Lesson(workspace_id=ws.id, title=f"{tpl.title} (копия)"[:300],
                    subject=tpl.subject, grade=tpl.grade, topic=tpl.topic, content=content)
    db.add(lesson); db.commit(); db.refresh(lesson)
    log(db, ws.id, "template_used", {"template_id": tpl.id, "lesson_id": lesson.id})
    return {"id": lesson.id, "title": lesson.title}


@app.delete("/api/templates/{template_id}")
def delete_template(template_id: str, key_hash: str = Depends(require_workspace_key),
                    db: Session = Depends(get_db)):
    ws = get_workspace(db, key_hash)
    tpl = db.scalar(select(Template).where(Template.id == template_id, Template.workspace_id == ws.id))
    if not tpl:
        raise HTTPException(404, "Шаблон не найден")
    db.delete(tpl); db.commit()
    return {"ok": True}


@app.post("/api/library/{publication_id}/clone")
def clone_from_library(publication_id: str, key_hash: str = Depends(require_workspace_key),
                       db: Session = Depends(get_db)):
    """Копирует одобренную публикацию в личное пространство учителя."""
    ws = get_workspace(db, key_hash)
    pub = db.get(Publication, publication_id)
    if not pub or pub.status != "published":
        raise HTTPException(404, "Публикация не найдена или не одобрена")
    content = normalize_content(pub.public_content)
    lesson = Lesson(workspace_id=ws.id, title=f"{pub.public_title} (из библиотеки)"[:300],
                    subject=pub.public_subject, grade=pub.public_grade, topic=pub.public_topic,
                    content=content)
    db.add(lesson); db.commit(); db.refresh(lesson)
    log(db, ws.id, "library_cloned", {"publication_id": pub.id, "lesson_id": lesson.id})
    return {"id": lesson.id, "title": lesson.title}


@app.get("/api/library/{publication_id}")
def get_library_item(publication_id: str, db: Session = Depends(get_db)):
    pub = db.get(Publication, publication_id)
    if not pub or pub.status != "published":
        raise HTTPException(404, "Не найдено")
    return {"id": pub.id, "title": pub.public_title, "subject": pub.public_subject,
            "grade": pub.public_grade, "topic": pub.public_topic, "content": pub.public_content,
            "created_at": pub.created_at}



# ---------- Этап 9: админ — AI, промпты, статистика, аудит ----------

@app.get("/api/admin/ai-config", dependencies=[Depends(require_admin)])
def admin_get_ai_config(db: Session = Depends(get_db)):
    cfg = get_ai_config(db)
    return {"config": cfg, "keys": ai_keys_status(),
            "providers": ["gemini", "openai", "anthropic", "xai"]}


@app.put("/api/admin/ai-config", dependencies=[Depends(require_admin)])
def admin_put_ai_config(payload: dict, db: Session = Depends(get_db)):
    cfg = set_ai_config(db, payload if isinstance(payload, dict) else {})
    log(db, None, "admin_ai_config_updated", {"provider": cfg.get("provider"), "model": cfg.get("model")})
    return {"config": cfg, "keys": ai_keys_status()}


@app.get("/api/admin/prompts", dependencies=[Depends(require_admin)])
def admin_get_prompts(db: Session = Depends(get_db)):
    return {"base": get_base_prompt(db), "subjects": get_subject_prompts(db)}


@app.put("/api/admin/prompts", dependencies=[Depends(require_admin)])
def admin_put_prompts(payload: dict, db: Session = Depends(get_db)):
    base = payload.get("base")
    subjects = payload.get("subjects")
    out = {}
    if isinstance(base, str):
        out["base"] = set_base_prompt(db, base)
    if isinstance(subjects, dict):
        out["subjects"] = set_subject_prompts(db, subjects)
    else:
        out["subjects"] = get_subject_prompts(db)
    if "base" not in out:
        out["base"] = get_base_prompt(db)
    set_runtime_prompts(out["base"], out["subjects"])
    log(db, None, "admin_prompts_updated", {"subjects": list((out.get("subjects") or {}).keys())[:20]})
    return out


@app.get("/api/admin/ai-usage", dependencies=[Depends(require_admin)])
def admin_ai_usage(limit: int = 100, db: Session = Depends(get_db)):
    limit = max(1, min(500, limit))
    rows = db.scalars(select(AIUsageLog).order_by(AIUsageLog.created_at.desc()).limit(limit)).all()
    return [{"id": r.id, "provider": r.provider, "model": r.model, "operation": r.operation,
             "status": r.status, "error_message": r.error_message, "latency_ms": r.latency_ms,
             "created_at": r.created_at} for r in rows]


@app.get("/api/admin/stats", dependencies=[Depends(require_admin)])
def admin_stats(db: Session = Depends(get_db)):
    # doc_type breakdown
    lessons = db.scalars(select(Lesson)).all()
    by_type = {}
    by_subject = {}
    for l in lessons:
        dt = (l.content or {}).get("doc_type", "ksp") if isinstance(l.content, dict) else "ksp"
        by_type[dt] = by_type.get(dt, 0) + 1
        subj = (l.subject or "—").strip() or "—"
        by_subject[subj] = by_subject.get(subj, 0) + 1
    avg_latency = db.scalar(select(func.avg(AIUsageLog.latency_ms)).where(AIUsageLog.status == "ok")) or 0
    return {
        "by_doc_type": by_type,
        "by_subject": dict(sorted(by_subject.items(), key=lambda x: -x[1])[:30]),
        "ai_avg_latency_ms": int(avg_latency),
        "templates": db.scalar(select(func.count()).select_from(Template)) or 0,
        "versions": db.scalar(select(func.count()).select_from(LessonVersion)) or 0,
        "favorites": db.scalar(select(func.count()).select_from(Favorite)) or 0,
    }


@app.get("/api/admin/lessons/{lesson_id}", dependencies=[Depends(require_admin)])
def admin_lesson_detail(lesson_id: str, db: Session = Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(404, "Не найдено")
    return {"id": lesson.id, "workspace_id": lesson.workspace_id, "title": lesson.title,
            "subject": lesson.subject, "grade": lesson.grade, "topic": lesson.topic,
            "content": lesson.content, "created_at": lesson.created_at, "updated_at": lesson.updated_at}



# ---------- Этап 10: экспорт XLSX, резервная копия workspace ----------

@app.get("/api/lessons/{lesson_id}/export.xlsx")
def export_lesson_xlsx(lesson_id: str, key_hash: str = Depends(require_workspace_key),
                       db: Session = Depends(get_db)):
    ws, lesson = own_lesson(db, key_hash, lesson_id)
    content = normalize_content(lesson.content)
    stream = build_xlsx({"title": lesson.title, "subject": lesson.subject,
                         "grade": lesson.grade, "topic": lesson.topic}, content)
    safe_name = re.sub(r"[^A-Za-zА-Яа-я0-9_-]+", "_", lesson.title or "export")[:60] or "export"
    log(db, ws.id, "lesson_exported_xlsx", {"lesson_id": lesson.id})
    return StreamingResponse(
        stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(safe_name)}.xlsx"})


@app.get("/api/presentations/{lesson_id}/export.xlsx")
def export_presentation_xlsx(lesson_id: str, key_hash: str = Depends(require_workspace_key),
                             db: Session = Depends(get_db)):
    ws, lesson = own_lesson(db, key_hash, lesson_id)
    content = sanitize_presentation(lesson.content or {})
    stream = build_xlsx({"title": lesson.title, "subject": lesson.subject,
                         "grade": lesson.grade, "topic": lesson.topic}, content)
    safe_name = re.sub(r"[^A-Za-zА-Яа-я0-9_-]+", "_", lesson.title or "presentation")[:60] or "presentation"
    log(db, ws.id, "presentation_exported_xlsx", {"lesson_id": lesson.id})
    return StreamingResponse(
        stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(safe_name)}.xlsx"})


@app.get("/api/workspace/backup")
def workspace_backup(key_hash: str = Depends(require_workspace_key), db: Session = Depends(get_db)):
    """Полный JSON-бэкап личного пространства (уроки + шаблоны + избранное). Без ключа доступа."""
    import json
    from datetime import datetime, timezone
    ws = get_workspace(db, key_hash)
    lessons = db.scalars(select(Lesson).where(Lesson.workspace_id == ws.id)).all()
    templates = db.scalars(select(Template).where(Template.workspace_id == ws.id)).all()
    favorites = db.scalars(select(Favorite).where(Favorite.workspace_id == ws.id)).all()
    payload = {
        "format": "ustaz-backup-v1",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "workspace": {
            "id": ws.id,
            "teacher_name": ws.teacher_name,
            "school_name": ws.school_name,
            "locality": ws.locality,
            "subjects": ws.subjects,
        },
        "lessons": [
            {"id": l.id, "title": l.title, "subject": l.subject, "grade": l.grade,
             "topic": l.topic, "content": l.content, "created_at": str(l.created_at),
             "updated_at": str(l.updated_at)}
            for l in lessons
        ],
        "templates": [
            {"id": t.id, "title": t.title, "subject": t.subject, "grade": t.grade,
             "topic": t.topic, "content": t.content, "created_at": str(t.created_at)}
            for t in templates
        ],
        "favorites": [
            {"id": f.id, "target_type": f.target_type, "target_id": f.target_id,
             "created_at": str(f.created_at)}
            for f in favorites
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    log(db, ws.id, "workspace_backup", {"lessons": len(lessons)})
    return StreamingResponse(
        BytesIO(raw), media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=ustaz-backup-{ws.id[:8]}.json"})


@app.post("/api/workspace/restore")
async def workspace_restore(payload: dict, key_hash: str = Depends(require_workspace_key),
                            db: Session = Depends(get_db)):
    """Импорт уроков из бэкапа в текущее пространство (добавление, без удаления)."""
    ws = get_workspace(db, key_hash)
    if not isinstance(payload, dict) or payload.get("format") != "ustaz-backup-v1":
        raise HTTPException(400, "Неверный формат бэкапа")
    created = 0
    for item in (payload.get("lessons") or [])[:200]:
        if not isinstance(item, dict):
            continue
        content = normalize_content(item.get("content") or {})
        title = str(item.get("title") or "Импорт")[:300]
        lesson = Lesson(
            workspace_id=ws.id, title=title,
            subject=str(item.get("subject") or "")[:120],
            grade=str(item.get("grade") or "")[:40],
            topic=str(item.get("topic") or "")[:300],
            content=content,
        )
        db.add(lesson)
        created += 1
    db.commit()
    log(db, ws.id, "workspace_restored", {"created": created})
    return {"created": created}


app.mount("/", StaticFiles(directory=str(Path(__file__).resolve().parents[2] / "frontend"), html=True), name="frontend")
