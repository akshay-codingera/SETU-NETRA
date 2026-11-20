"""
documents.py: Document ingestion, retrieval, and management router with workspace scoping.
"""

import io
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image, ImageDraw
from pydantic import BaseModel, Field

from setu_netra.api.dependencies import (
    get_auth_service,
    get_current_user,
    get_doc_pipeline,
    get_pipeline_adapter,
    require_authenticated,
    require_csrf,
    require_permission,
)
from setu_netra.api.schemas import (
    DocumentBlockResponse,
    DocumentPageResponse,
    PageTextResponse,
    SolvePageQuestionRequest,
    SolveQuestionResponse,
)
from setu_netra.auth.roles import Permission, UserRole, has_permission
from setu_netra.auth.service import AuthService, AuthenticatedSession, UserRecord
from setu_netra.pipeline.document_pipeline import DocumentIntelligencePipeline
from setu_netra.qa.image_question_solver import ImageQuestionSolver

router = APIRouter(prefix="/api/v1/documents", tags=["Document Intelligence"])


class DocumentItemResponse(BaseModel):
    doc_id: str
    file_name: str
    file_type: str
    page_count: int
    created_at: str
    status: str
    workspace_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


@router.get("", response_model=List[DocumentItemResponse])
async def list_documents(
    workspace_id: Optional[str] = None,
    session: AuthenticatedSession = Depends(require_authenticated),
    doc_pipeline: DocumentIntelligencePipeline = Depends(get_doc_pipeline),
    auth_service: AuthService = Depends(get_auth_service),
) -> List[DocumentItemResponse]:
    """List documents isolated to the active workspace (or specified workspace if authorized)."""
    target_ws = workspace_id or session.session.active_workspace_id
    
    # Verify access to target workspace
    has_access = auth_service.verify_workspace_access(
        user_id=session.user.user_id,
        role=session.user.role,
        workspace_id=target_ws,
        require_write=False,
    )
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to documents in workspace '{target_ws}'.",
        )

    docs = doc_pipeline.store.list_documents(workspace_id=target_ws)
    return [
        DocumentItemResponse(
            doc_id=d.doc_id,
            file_name=d.file_name,
            file_type=getattr(d, "file_type", "UNKNOWN"),
            page_count=d.page_count,
            created_at=d.created_at,
            status=d.status,
            workspace_id=getattr(d, "workspace_id", target_ws),
            metadata=d.metadata,
        )
        for d in docs
    ]


@router.post("/upload", response_model=DocumentItemResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
async def upload_document(
    file: UploadFile = File(...),
    session: AuthenticatedSession = Depends(require_authenticated),
    doc_pipeline: DocumentIntelligencePipeline = Depends(get_doc_pipeline),
    auth_service: AuthService = Depends(get_auth_service),
) -> DocumentItemResponse:
    """Ingest a new document into the active workspace with evidence extraction."""
    # Enforce DOCUMENT_UPLOAD permission
    if not has_permission(session.user.role, Permission.DOCUMENT_UPLOAD):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{session.user.role.value}' is not permitted to upload documents.",
        )

    target_ws = session.session.active_workspace_id
    has_write_access = auth_service.verify_workspace_access(
        user_id=session.user.user_id,
        role=session.user.role,
        workspace_id=target_ws,
        require_write=True,
    )
    if not has_write_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Write access denied in workspace '{target_ws}'.",
        )

    # Persist uploaded file to durable uploads directory with preserved original name
    uploads_dir = Path("output/uploads")
    upload_subdir = uploads_dir / uuid.uuid4().hex[:8]
    upload_subdir.mkdir(parents=True, exist_ok=True)
    orig_name = Path(file.filename or "document.tmp").name
    dest_path = upload_subdir / orig_name
    
    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        stored_doc = doc_pipeline.ingest_document(
            file_path=dest_path,
            workspace_id=target_ws,
        )

        return DocumentItemResponse(
            doc_id=stored_doc.doc_id,
            file_name=stored_doc.file_name,
            file_type=getattr(stored_doc, "file_type", "UNKNOWN"),
            page_count=stored_doc.page_count,
            created_at=stored_doc.created_at,
            status=stored_doc.status,
            workspace_id=getattr(stored_doc, "workspace_id", target_ws),
            metadata=stored_doc.metadata,
        )
    except Exception as e:
        if dest_path.exists():
            try:
                dest_path.unlink()
            except Exception:
                pass
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Ingestion failed: {e}")


@router.get("/{doc_id}", response_model=DocumentItemResponse)
async def get_document(
    doc_id: str,
    session: AuthenticatedSession = Depends(require_authenticated),
    doc_pipeline: DocumentIntelligencePipeline = Depends(get_doc_pipeline),
    auth_service: AuthService = Depends(get_auth_service),
) -> DocumentItemResponse:
    """Retrieve document details by doc_id with workspace boundary verification."""
    doc = doc_pipeline.store.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found.")

    doc_ws = getattr(doc, "workspace_id", "default")
    has_access = auth_service.verify_workspace_access(
        user_id=session.user.user_id,
        role=session.user.role,
        workspace_id=doc_ws,
        require_write=False,
    )
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to document in workspace '{doc_ws}'.",
        )

    return DocumentItemResponse(
        doc_id=doc.doc_id,
        file_name=doc.file_name,
        file_type=getattr(doc, "file_type", "UNKNOWN"),
        page_count=doc.page_count,
        created_at=doc.created_at,
        status=doc.status,
        workspace_id=doc_ws,
        metadata=doc.metadata,
    )


@router.get("/{doc_id}/pages", response_model=List[DocumentPageResponse])
async def get_document_pages(
    doc_id: str,
    session: AuthenticatedSession = Depends(require_authenticated),
    doc_pipeline: DocumentIntelligencePipeline = Depends(get_doc_pipeline),
    auth_service: AuthService = Depends(get_auth_service),
) -> List[DocumentPageResponse]:
    """Retrieve pages of a document with spatial dimensions."""
    doc = doc_pipeline.store.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found.")

    doc_ws = getattr(doc, "workspace_id", "default")
    has_access = auth_service.verify_workspace_access(
        user_id=session.user.user_id,
        role=session.user.role,
        workspace_id=doc_ws,
        require_write=False,
    )
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to document in workspace '{doc_ws}'.",
        )

    pages = doc_pipeline.store.get_pages(doc_id)
    return [
        DocumentPageResponse(
            page_id=p.page_id,
            doc_id=p.doc_id,
            page_number=p.page_number,
            width=p.width,
            height=p.height,
            metadata=p.metadata,
        )
        for p in pages
    ]


@router.get("/{doc_id}/pages/{page_number}/blocks", response_model=List[DocumentBlockResponse])
async def get_page_blocks(
    doc_id: str,
    page_number: int,
    session: AuthenticatedSession = Depends(require_authenticated),
    doc_pipeline: DocumentIntelligencePipeline = Depends(get_doc_pipeline),
    auth_service: AuthService = Depends(get_auth_service),
) -> List[DocumentBlockResponse]:
    """Retrieve geometric reconstructed blocks with bounding boxes and confidence for a page."""
    doc = doc_pipeline.store.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found.")

    doc_ws = getattr(doc, "workspace_id", "default")
    has_access = auth_service.verify_workspace_access(
        user_id=session.user.user_id,
        role=session.user.role,
        workspace_id=doc_ws,
        require_write=False,
    )
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to document in workspace '{doc_ws}'.",
        )

    blocks = doc_pipeline.store.get_blocks(doc_id=doc_id, page_number=page_number, workspace_id=doc_ws)
    return [
        DocumentBlockResponse(
            block_id=b["block_id"],
            page_number=b["page_number"],
            block_type=b["block_type"],
            text=b["text"],
            confidence=b["confidence"],
            bounding_box=list(b["bounding_box"]),
            source_detection_indices=b.get("source_detection_indices", []),
        )
        for b in blocks
    ]


@router.get("/{doc_id}/pages/{page_number}/image")
async def get_page_image(
    doc_id: str,
    page_number: int,
    session: AuthenticatedSession = Depends(require_authenticated),
    doc_pipeline: DocumentIntelligencePipeline = Depends(get_doc_pipeline),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Render page image non-destructively for the spatial document viewer."""
    doc = doc_pipeline.store.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found.")

    doc_ws = getattr(doc, "workspace_id", "default")
    has_access = auth_service.verify_workspace_access(
        user_id=session.user.user_id,
        role=session.user.role,
        workspace_id=doc_ws,
        require_write=False,
    )
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to document in workspace '{doc_ws}'.",
        )

    file_path = Path(doc.file_path)
    if not file_path.is_file():
        candidates = [
            Path("sample_data") / file_path.name,
            Path("output") / file_path.name,
            Path("output/uploads") / file_path.name,
        ]
        for c in candidates:
            if c.is_file():
                file_path = c
                break

    if file_path.is_file():
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            try:
                import pypdfium2 as pdfium
                pdf = pdfium.PdfDocument(str(file_path))
                if 1 <= page_number <= len(pdf):
                    page = pdf.get_page(page_number - 1)
                    pil_image = page.render(scale=2.0).to_pil()
                    buf = io.BytesIO()
                    pil_image.save(buf, format="PNG")
                    return Response(content=buf.getvalue(), media_type="image/png")
            except Exception:
                pass
        elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"]:
            try:
                with Image.open(file_path) as img:
                    buf = io.BytesIO()
                    img.convert("RGB").save(buf, format="PNG")
                    return Response(content=buf.getvalue(), media_type="image/png")
            except Exception:
                pass

    # High quality procedural parchment fallback canvas if original file missing or non-raster
    pages = doc_pipeline.store.get_pages(doc_id)
    width, height = 800, 1100
    for p in pages:
        if p.page_number == page_number:
            width, height = max(400, p.width), max(500, p.height)
            break

    img = Image.new("RGB", (width, height), color=(249, 246, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, width - 10, height - 10], outline=(226, 221, 210), width=2)
    blocks = doc_pipeline.store.get_blocks(doc_id=doc_id, page_number=page_number)
    for b in blocks:
        bbox = b.get("bounding_box", (0, 0, 0, 0))
        text = b.get("text", "")
        draw.rectangle([bbox[0], bbox[1], bbox[2], bbox[3]], outline=(210, 200, 190), width=1)
        if text:
            draw.text((bbox[0] + 4, bbox[1] + 4), text[:50], fill=(26, 25, 24))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@router.delete("/{doc_id}", dependencies=[Depends(require_csrf)])
async def delete_document(
    doc_id: str,
    session: AuthenticatedSession = Depends(require_authenticated),
    doc_pipeline: DocumentIntelligencePipeline = Depends(get_doc_pipeline),
    auth_service: AuthService = Depends(get_auth_service),
) -> Dict[str, Any]:
    """Delete document and all indexed blocks with authorization and workspace boundary verification."""
    if not has_permission(session.user.role, Permission.DOCUMENT_DELETE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{session.user.role.value}' is not permitted to delete documents.",
        )

    doc = doc_pipeline.store.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found.")

    doc_ws = getattr(doc, "workspace_id", "default")
    has_write_access = auth_service.verify_workspace_access(
        user_id=session.user.user_id,
        role=session.user.role,
        workspace_id=doc_ws,
        require_write=True,
    )
    if not has_write_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Delete permission denied in workspace '{doc_ws}'.",
        )

    success = doc_pipeline.store.delete_document(doc_id=doc_id, workspace_id=doc_ws)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not delete document.")

    return {"status": "success", "deleted_doc_id": doc_id}


@router.get("/{doc_id}/pages/{page_number}/text", response_model=PageTextResponse)
async def get_page_text(
    doc_id: str,
    page_number: int,
    session: AuthenticatedSession = Depends(require_authenticated),
    doc_pipeline: DocumentIntelligencePipeline = Depends(get_doc_pipeline),
    auth_service: AuthService = Depends(get_auth_service),
) -> PageTextResponse:
    """Retrieve complete extracted text, OCR transcript, and detected questions for a page."""
    doc = doc_pipeline.store.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found.")

    doc_ws = getattr(doc, "workspace_id", "default")
    has_access = auth_service.verify_workspace_access(
        user_id=session.user.user_id,
        role=session.user.role,
        workspace_id=doc_ws,
        require_write=False,
    )
    if not has_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Access denied to workspace '{doc_ws}'.")

    page = doc_pipeline.store.get_page(doc_id, page_number)
    blocks = doc_pipeline.store.get_blocks(doc_id=doc_id, page_number=page_number)

    if page and page.metadata:
        full_text = page.metadata.get("full_text") or "\n\n".join(b.get("text", "") for b in blocks)
        raw_transcript = page.metadata.get("raw_transcript") or full_text
        ocr_status = page.metadata.get("ocr_status") or "SUCCESS"
        detected_questions = page.metadata.get("detected_questions") or []
        warnings = page.metadata.get("warnings") or []
    else:
        full_text = "\n\n".join(b.get("text", "") for b in blocks)
        raw_transcript = full_text
        ocr_status = "SUCCESS" if blocks else "EMPTY"
        detected_questions = []
        warnings = []

    return PageTextResponse(
        doc_id=doc_id,
        page_number=page_number,
        full_text=full_text,
        raw_transcript=raw_transcript,
        blocks_count=len(blocks),
        ocr_status=ocr_status,
        detected_questions=detected_questions,
        warnings=warnings,
    )


@router.post("/{doc_id}/pages/{page_number}/solve", response_model=SolveQuestionResponse)
async def solve_page_question(
    doc_id: str,
    page_number: int,
    request: SolvePageQuestionRequest,
    session: AuthenticatedSession = Depends(require_authenticated),
    doc_pipeline: DocumentIntelligencePipeline = Depends(get_doc_pipeline),
    adapter=Depends(get_pipeline_adapter),
    auth_service: AuthService = Depends(get_auth_service),
) -> SolveQuestionResponse:
    """Solve the question depicted on a document page (supports user-edited text review)."""
    doc = doc_pipeline.store.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' not found.")

    doc_ws = getattr(doc, "workspace_id", "default")
    has_access = auth_service.verify_workspace_access(
        user_id=session.user.user_id,
        role=session.user.role,
        workspace_id=doc_ws,
        require_write=False,
    )
    if not has_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Access denied to workspace '{doc_ws}'.")

    solver = ImageQuestionSolver(
        ocr_engine=doc_pipeline.ocr_engine,
        reconstructor=doc_pipeline.reconstructor,
        inference_pipeline=getattr(adapter, "inference_pipeline", None),
    )

    if request.edited_text and request.edited_text.strip():
        # User provided edited or reviewed OCR text
        solution = solver.solve_image(
            image_or_text=request.edited_text.strip(),
            model_id=request.model_id,
            think=request.think,
            workspace_id=doc_ws,
        )
    else:
        # Load page image from disk or storage
        file_path = Path(doc.file_path)
        if not file_path.exists():
            for loc in [Path("output/uploads"), Path("uploads")]:
                candidate = loc / file_path.name
                if candidate.exists():
                    file_path = candidate
                    break

        if not file_path.exists():
            # Fallback to page text from store
            page = doc_pipeline.store.get_page(doc_id, page_number)
            blocks = doc_pipeline.store.get_blocks(doc_id=doc_id, page_number=page_number)
            text = (page.metadata.get("full_text") if page else "") or "\n\n".join(b.get("text", "") for b in blocks)
            solution = solver.solve_image(
                image_or_text=text,
                model_id=request.model_id,
                think=request.think,
                workspace_id=doc_ws,
            )
        else:
            ext = file_path.suffix.lower()
            if ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"]:
                with Image.open(file_path) as img:
                    solution = solver.solve_image(
                        image_or_text=img.copy(),
                        model_id=request.model_id,
                        think=request.think,
                        workspace_id=doc_ws,
                    )
            elif ext == ".pdf":
                try:
                    import pypdfium2 as pdfium
                    pdf = pdfium.PdfDocument(str(file_path))
                    if 1 <= page_number <= len(pdf):
                        page = pdf.get_page(page_number - 1)
                        pil_image = page.render(scale=2.0).to_pil()
                        solution = solver.solve_image(
                            image_or_text=pil_image,
                            model_id=request.model_id,
                            think=request.think,
                            workspace_id=doc_ws,
                        )
                    else:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Page {page_number} out of range.")
                except Exception as e:
                    page = doc_pipeline.store.get_page(doc_id, page_number)
                    blocks = doc_pipeline.store.get_blocks(doc_id=doc_id, page_number=page_number)
                    text = (page.metadata.get("full_text") if page else "") or "\n\n".join(b.get("text", "") for b in blocks)
                    solution = solver.solve_image(
                        image_or_text=text,
                        model_id=request.model_id,
                        think=request.think,
                        workspace_id=doc_ws,
                    )
            else:
                # Text-based document
                page = doc_pipeline.store.get_page(doc_id, page_number)
                blocks = doc_pipeline.store.get_blocks(doc_id=doc_id, page_number=page_number)
                text = (page.metadata.get("full_text") if page else "") or "\n\n".join(b.get("text", "") for b in blocks)
                solution = solver.solve_image(
                    image_or_text=text,
                    model_id=request.model_id,
                    think=request.think,
                    workspace_id=doc_ws,
                )

    return SolveQuestionResponse(**solution.to_dict())

