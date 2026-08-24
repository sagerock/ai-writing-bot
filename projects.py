"""FastAPI routes for owner-scoped, template-driven writing projects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Callable, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field, model_validator

from project_templates import (
    initial_project_draft,
    public_project_templates,
    validate_project_charge,
)
from project_store import (
    ChatNotFound,
    DraftVersionNotFound,
    ProjectNotFound,
    ProjectStore,
    SourceNotFound,
)
from source_extract import extract


DEFAULT_PROJECT_MODEL = "claude-sonnet-5"
MAX_DRAFT_BYTES = 900_000
SUPPORTED_SOURCE_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".csv": "text/csv",
}


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProjectCreate(RequestModel):
    name: str = Field(min_length=1, max_length=160)
    kind: Literal["memo", "research_paper", "article", "blog_post", "general_document"] = "memo"
    charge: dict[str, str]
    default_model: str = Field(default=DEFAULT_PROJECT_MODEL, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_charge_for_kind(self):
        self.charge = validate_project_charge(self.kind, self.charge)
        return self


class ProjectPatch(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    charge: dict[str, str] | None = None
    default_model: str | None = Field(default=None, min_length=1, max_length=100)
    archived: bool | None = None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one project field is required.")
        return self


class SourcePatch(RequestModel):
    label: str = Field(min_length=1, max_length=160)


class DraftSave(RequestModel):
    markdown: str = Field(max_length=MAX_DRAFT_BYTES)
    reason: str = Field(default="manual save", min_length=1, max_length=500)

    @model_validator(mode="after")
    def enforce_firestore_size(self):
        if len(self.markdown.encode("utf-8")) > MAX_DRAFT_BYTES:
            raise ValueError("Draft is too large to store.")
        return self


class DraftRestore(RequestModel):
    version: int = Field(ge=1)


class ChatCreate(RequestModel):
    title: str = Field(default="New chat", min_length=1, max_length=200)
    mode: Literal["brainstorm", "write"] = "brainstorm"
    model: str | None = Field(default=None, min_length=1, max_length=100)


def _translate_not_found(error: LookupError) -> HTTPException:
    if isinstance(error, ProjectNotFound):
        return HTTPException(status_code=404, detail="Project not found.")
    if isinstance(error, SourceNotFound):
        return HTTPException(status_code=404, detail="Source not found.")
    if isinstance(error, ChatNotFound):
        return HTTPException(status_code=404, detail="Chat not found.")
    if isinstance(error, DraftVersionNotFound):
        return HTTPException(status_code=404, detail="Draft version not found.")
    return HTTPException(status_code=404, detail="Not found.")


def _source_label(filename: str) -> str:
    return (Path(filename).stem or filename)[:160]


def create_projects_router(
    *,
    db,
    get_current_user: Callable,
    get_storage_bucket: Callable,
    get_rag_service: Callable,
    safe_filename: Callable[[str], str],
    estimate_tokens: Callable[[str], int],
    allowed_model_ids: set[str],
    max_upload_bytes: int,
    max_pdf_pages: int,
    full_context_tokens: int = 400_000,
) -> APIRouter:
    router = APIRouter(prefix="/projects", tags=["projects"])
    store = ProjectStore(db, full_context_tokens=full_context_tokens)

    def validate_model(model: str) -> str:
        if model not in allowed_model_ids:
            raise HTTPException(status_code=422, detail="Unsupported project model.")
        return model

    @router.post("")
    async def create_project(
        request: ProjectCreate,
        user: dict = Depends(get_current_user),
    ):
        model = validate_model(request.default_model)
        return store.create_project(
            user["user_id"],
            name=request.name,
            kind=request.kind,
            charge=request.charge,
            default_model=model,
            initial_draft=initial_project_draft(request.kind, request.name),
        )

    @router.get("")
    async def list_projects(
        include_archived: bool = Query(default=False),
        user: dict = Depends(get_current_user),
    ):
        return store.list_projects(user["user_id"], include_archived=include_archived)

    @router.get("/templates")
    async def list_project_templates(
        user: dict = Depends(get_current_user),
    ):
        del user
        return public_project_templates()

    @router.get("/{project_id}")
    async def get_project(
        project_id: str,
        user: dict = Depends(get_current_user),
    ):
        try:
            return store.get_project(user["user_id"], project_id)
        except LookupError as error:
            raise _translate_not_found(error) from error

    @router.patch("/{project_id}")
    async def patch_project(
        project_id: str,
        request: ProjectPatch,
        user: dict = Depends(get_current_user),
    ):
        changes = request.model_dump(exclude_unset=True, exclude_none=True)
        if request.charge is not None:
            try:
                project = store.get_project_record(user["user_id"], project_id)
                changes["charge"] = validate_project_charge(
                    str(project.get("kind", "memo")), request.charge
                )
            except LookupError as error:
                raise _translate_not_found(error) from error
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
        if request.default_model is not None:
            changes["default_model"] = validate_model(request.default_model)
        if not changes:
            raise HTTPException(
                status_code=422,
                detail="At least one project field is required.",
            )
        try:
            return store.update_project(user["user_id"], project_id, changes)
        except LookupError as error:
            raise _translate_not_found(error) from error

    @router.delete("/{project_id}")
    async def delete_project(
        project_id: str,
        user: dict = Depends(get_current_user),
    ):
        try:
            project = store.archive_project(user["user_id"], project_id)
            return {"message": "Project archived.", "project": project}
        except LookupError as error:
            raise _translate_not_found(error) from error

    @router.post("/{project_id}/sources")
    async def upload_source(
        project_id: str,
        file: Annotated[UploadFile, File(...)],
        label: Annotated[str | None, Form(max_length=160)] = None,
        user: dict = Depends(get_current_user),
    ):
        user_id = user["user_id"]
        try:
            project = store.get_project_record(user_id, project_id)
        except LookupError as error:
            raise _translate_not_found(error) from error

        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided.")
        filename = safe_filename(file.filename)
        extension = Path(filename).suffix.lower()
        extraction_type = SUPPORTED_SOURCE_TYPES.get(extension)
        if not extraction_type:
            raise HTTPException(
                status_code=400,
                detail="Project sources must be PDF, TXT, Markdown, DOCX, or CSV.",
            )
        data = await file.read(max_upload_bytes + 1)
        if len(data) > max_upload_bytes:
            raise HTTPException(status_code=413, detail="File exceeds the upload limit.")
        try:
            extraction = extract(data, extraction_type)
        except Exception as error:
            raise HTTPException(
                status_code=400,
                detail="Source text could not be extracted.",
            ) from error
        if extraction["kind"] == "page" and len(extraction["pages"]) > max_pdf_pages:
            raise HTTPException(status_code=413, detail="PDF has too many pages.")

        source = store.reserve_source(
            user_id,
            project_id,
            filename=filename,
            content_type=extraction_type,
            size=len(data),
            label=(label.strip() if label and label.strip() else _source_label(filename)),
        )
        source_id = source["id"]
        base_path = f"{user_id}/projects/{project_id}/sources/{source_id}"
        storage_path = f"{base_path}/{filename}"
        text_path = f"{base_path}.txt"
        pages_path = f"{base_path}.pages.json"

        try:
            bucket = get_storage_bucket()
            bucket.blob(storage_path).upload_from_string(
                data,
                content_type=extraction_type,
            )
            bucket.blob(text_path).upload_from_string(
                extraction["text"].encode("utf-8"),
                content_type="text/plain; charset=utf-8",
            )
            bucket.blob(pages_path).upload_from_string(
                json.dumps(extraction["pages"]).encode("utf-8"),
                content_type="application/json",
            )

            indexed_chunks = 0
            indexing_error = None
            try:
                rag = get_rag_service()
                if rag and extraction["text"]:
                    indexed_chunks = rag.index_document(
                        user_id,
                        filename,
                        extraction["text"],
                        project_name=project["name"],
                        project_id=project_id,
                        source_id=source_id,
                        page_map=extraction["pages"],
                    )
            except Exception as error:
                indexing_error = str(error)[:2000]

            page_count = len(extraction["pages"]) if extraction["kind"] == "page" else None
            source = store.finalize_source(
                user_id,
                project_id,
                source_id,
                {
                    "storage_path": storage_path,
                    "text_path": text_path,
                    "pages_path": pages_path,
                    "pages": page_count,
                    "paragraphs": (
                        len(extraction["pages"]) if extraction["kind"] == "paragraph" else None
                    ),
                    "map_kind": extraction["kind"],
                    "text_chars": len(extraction["text"]),
                    "estimated_tokens": estimate_tokens(extraction["text"]),
                    "indexed": indexed_chunks > 0,
                    "chunk_count": indexed_chunks,
                    "indexing_error": indexing_error,
                },
            )
            project = store.get_project_record(user_id, project_id)
            context = {
                "context_mode": project["context_mode"],
                "total_source_tokens": project["total_source_tokens"],
            }
            return {"source": source, **context}
        except HTTPException:
            raise
        except Exception as error:
            try:
                bucket = get_storage_bucket()
                for path in (storage_path, text_path, pages_path):
                    blob = bucket.blob(path)
                    if blob.exists():
                        blob.delete()
            except Exception:
                pass
            try:
                rag = get_rag_service()
                if rag:
                    rag.delete_document(user_id, filename, document_key=source_id)
            except Exception:
                pass
            store.fail_source(user_id, project_id, source_id, str(error))
            raise HTTPException(status_code=500, detail="Source upload failed.") from error

    @router.patch("/{project_id}/sources/{source_id}")
    async def patch_source(
        project_id: str,
        source_id: str,
        request: SourcePatch,
        user: dict = Depends(get_current_user),
    ):
        try:
            return store.update_source_label(
                user["user_id"], project_id, source_id, request.label
            )
        except LookupError as error:
            raise _translate_not_found(error) from error

    @router.delete("/{project_id}/sources/{source_id}")
    async def delete_source(
        project_id: str,
        source_id: str,
        user: dict = Depends(get_current_user),
    ):
        user_id = user["user_id"]
        try:
            source = store.get_source(user_id, project_id, source_id)
        except LookupError as error:
            raise _translate_not_found(error) from error

        bucket = get_storage_bucket()
        for path_key in ("storage_path", "text_path", "pages_path"):
            path = source.get(path_key)
            if path:
                blob = bucket.blob(path)
                if blob.exists():
                    blob.delete()
        try:
            rag = get_rag_service()
            if rag:
                rag.delete_document(user_id, source["filename"], document_key=source_id)
        except Exception:
            pass
        store.delete_source(user_id, project_id, source_id)
        return {"message": "Source deleted."}

    @router.get("/{project_id}/sources/{source_id}/text")
    async def get_source_text(
        project_id: str,
        source_id: str,
        page: int | None = Query(default=None, ge=1),
        user: dict = Depends(get_current_user),
    ):
        try:
            source = store.get_source(user["user_id"], project_id, source_id)
        except LookupError as error:
            raise _translate_not_found(error) from error
        if source.get("status") != "ready":
            raise HTTPException(status_code=409, detail="Source is not ready.")
        bucket = get_storage_bucket()
        text = bucket.blob(source["text_path"]).download_as_text(encoding="utf-8")
        page_map = json.loads(bucket.blob(source["pages_path"]).download_as_text(encoding="utf-8"))
        selected = None
        if page is not None:
            location_key = "page" if source.get("map_kind") == "page" else "paragraph"
            selected = next((entry for entry in page_map if entry.get(location_key) == page), None)
            if selected is None:
                raise HTTPException(status_code=404, detail="Source location not found.")
            text = text[selected["start"] : selected["end"]]
        return {
            "source_id": source_id,
            "filename": source["filename"],
            "kind": source.get("map_kind"),
            "text": text,
            "location": selected,
            "pages": page_map if page is None else None,
        }

    @router.get("/{project_id}/draft")
    async def get_draft(
        project_id: str,
        user: dict = Depends(get_current_user),
    ):
        try:
            return store.get_draft(user["user_id"], project_id)
        except LookupError as error:
            raise _translate_not_found(error) from error

    @router.put("/{project_id}/draft")
    async def put_draft(
        project_id: str,
        request: DraftSave,
        user: dict = Depends(get_current_user),
    ):
        try:
            return store.save_draft(
                user["user_id"],
                project_id,
                markdown=request.markdown,
                reason=request.reason,
            )
        except LookupError as error:
            raise _translate_not_found(error) from error

    @router.get("/{project_id}/draft/versions")
    async def get_draft_versions(
        project_id: str,
        user: dict = Depends(get_current_user),
    ):
        try:
            return store.list_draft_versions(user["user_id"], project_id)
        except LookupError as error:
            raise _translate_not_found(error) from error

    @router.post("/{project_id}/draft/restore")
    async def restore_draft(
        project_id: str,
        request: DraftRestore,
        user: dict = Depends(get_current_user),
    ):
        try:
            return store.restore_draft(user["user_id"], project_id, request.version)
        except LookupError as error:
            raise _translate_not_found(error) from error

    @router.post("/{project_id}/chats")
    async def create_chat(
        project_id: str,
        request: ChatCreate | None = None,
        user: dict = Depends(get_current_user),
    ):
        request = request or ChatCreate()
        if request.model:
            validate_model(request.model)
        try:
            return store.create_chat(
                user["user_id"],
                project_id,
                title=request.title,
                mode=request.mode,
                model=request.model,
            )
        except LookupError as error:
            raise _translate_not_found(error) from error

    @router.get("/{project_id}/chats/{chat_id}")
    async def get_chat(
        project_id: str,
        chat_id: str,
        user: dict = Depends(get_current_user),
    ):
        try:
            return store.get_chat(user["user_id"], project_id, chat_id)
        except LookupError as error:
            raise _translate_not_found(error) from error

    @router.delete("/{project_id}/chats/{chat_id}")
    async def delete_chat(
        project_id: str,
        chat_id: str,
        user: dict = Depends(get_current_user),
    ):
        try:
            store.delete_chat(user["user_id"], project_id, chat_id)
            return {"message": "Chat deleted."}
        except LookupError as error:
            raise _translate_not_found(error) from error

    return router
