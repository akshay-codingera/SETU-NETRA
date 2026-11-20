"""
query.py: Asynchronous inquiry and question answering endpoint (/api/v1/query).
"""

import io
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from PIL import Image

from setu_netra.api.dependencies import (
    get_auth_service,
    get_current_session,
    get_current_user,
    get_doc_pipeline,
    get_pipeline_adapter,
)
from setu_netra.api.pipeline_adapter import AsyncPipelineAdapter
from setu_netra.api.schemas import ImageQueryResponse, QueryRequest, QueryResponse
from setu_netra.auth.roles import Permission, has_permission
from setu_netra.auth.service import AuthService, AuthenticatedSession, UserRecord
from setu_netra.pipeline.document_pipeline import DocumentIntelligencePipeline
from setu_netra.qa.image_question_solver import ImageQuestionSolver

router = APIRouter(prefix="/query", tags=["Inference & Query"])


@router.post("", response_model=QueryResponse)
async def execute_query(
    request: Request,
    body: QueryRequest,
    adapter: AsyncPipelineAdapter = Depends(get_pipeline_adapter),
    session: Optional[AuthenticatedSession] = Depends(get_current_session),
    user: UserRecord = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> QueryResponse:
    """
    Execute evidence-grounded question answering asynchronously with workspace scoping and RBAC.
    
    Guarantees:
    - Bounded Thread Execution: Synchronous inference runs in anyio worker pool.
    - Model Concurrency: Respects Ollama 1-concurrency semaphore.
    - Workspace Sandboxing: Evidence retrieval is strictly bounded to the active workspace.
    - Provenance: Returns citation bounding blocks and Tripartite classification.
    """
    if not has_permission(user.role, Permission.QUERY_EXECUTE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{user.role.value}' is not permitted to execute queries.",
        )

    correlation_id = getattr(request.state, "correlation_id", "corr_unknown")
    workspace_id = session.session.active_workspace_id if session else "default"

    # If doc_id specified, verify workspace access
    if body.doc_id:
        doc = adapter.qa_engine.retriever.store.get_document_by_id(body.doc_id)
        if doc:
            doc_ws = getattr(doc, "workspace_id", "default")
            has_access = auth_service.verify_workspace_access(
                user_id=user.user_id,
                role=user.role,
                workspace_id=doc_ws,
                require_write=False,
            )
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied to document '{body.doc_id}' in workspace '{doc_ws}'.",
                )

    result = await adapter.answer_question(
        query=body.query,
        doc_id=body.doc_id,
        model_id=body.model_id,
        think=body.think,
        top_k=body.top_k,
        threshold=body.threshold,
        correlation_id=correlation_id,
        workspace_id=workspace_id,
    )

    return QueryResponse(
        query=result["query"],
        answer_text=result["answer_text"],
        epistemic_status=result["epistemic_status"],
        citations=result["citations"],
        grounding_score=result["grounding_score"],
        executing_model_id=result.get("executing_model_id"),
        executing_worker_id=result.get("executing_worker_id"),
        execution_time_ms=result["execution_time_ms"],
        explanation=result.get("explanation"),
        thinking=result.get("thinking"),
        correlation_id=correlation_id,
        pipeline_telemetry=result.get("pipeline_telemetry"),
        domain=result.get("domain", "DOCUMENT_QA"),
        reconstructed_question=result.get("reconstructed_question"),
        verification_method=result.get("verification_method"),
        step_by_step_explanation=result.get("step_by_step_explanation"),
        options=result.get("options", []),
        selected_option=result.get("selected_option"),
        selected_option_text=result.get("selected_option_text"),
        option_analysis=result.get("option_analysis", {}),
    )


@router.post("/image", response_model=ImageQueryResponse)
async def execute_image_query(
    request: Request,
    file: UploadFile = File(...),
    doc_id: Optional[str] = Form(None),
    model_id: Optional[str] = Form(None),
    think: Optional[str] = Form(None),
    top_k: int = Form(3),
    threshold: float = Form(0.20),
    adapter: AsyncPipelineAdapter = Depends(get_pipeline_adapter),
    doc_pipeline: DocumentIntelligencePipeline = Depends(get_doc_pipeline),
    session: Optional[AuthenticatedSession] = Depends(get_current_session),
    user: UserRecord = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> ImageQueryResponse:
    """
    Image-based question answering:
    Ingests an image of a handwritten or printed question, executes OCR layout detection,
    extracts the inquiry text, routes to the grounded QA engine, and returns the verified answer.
    """
    if not has_permission(user.role, Permission.QUERY_EXECUTE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{user.role.value}' is not permitted to execute queries.",
        )

    correlation_id = getattr(request.state, "correlation_id", "corr_unknown")
    workspace_id = session.session.active_workspace_id if session else "default"

    contents = await file.read()
    try:
        pil_img = Image.open(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image file for question ingestion: {e}",
        )

    # If doc_id specified, verify workspace access
    if doc_id:
        doc = adapter.qa_engine.retriever.store.get_document_by_id(doc_id)
        if doc:
            doc_ws = getattr(doc, "workspace_id", "default")
            has_access = auth_service.verify_workspace_access(
                user_id=user.user_id,
                role=user.role,
                workspace_id=doc_ws,
                require_write=False,
            )
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied to document '{doc_id}' in workspace '{doc_ws}'.",
                )

    think_bool = None
    if think is not None:
        think_bool = think.lower() in ("true", "1", "yes", "keep")

    solver = ImageQuestionSolver(
        ocr_engine=doc_pipeline.ocr_engine,
        reconstructor=doc_pipeline.reconstructor,
        inference_pipeline=getattr(adapter, "inference_pipeline", None),
    )

    solution = solver.solve_image(
        image_or_text=pil_img,
        model_id=model_id,
        think=think_bool,
        workspace_id=workspace_id,
    )

    return ImageQueryResponse(
        query=solution.normalized_question,
        extracted_question=solution.normalized_question,
        ocr_confidence=round(solution.confidence, 4),
        ocr_detections_count=len(solution.uncertain_spans) + 1,
        answer_text=solution.final_answer,
        epistemic_status=solution.epistemic_status,
        citations=[],
        grounding_score=round(solution.confidence, 4),
        executing_model_id=solution.model_id,
        executing_worker_id=solution.model_id,
        execution_time_ms=solution.execution_time_ms,
        explanation=solution.step_by_step_explanation,
        thinking=None,
        correlation_id=correlation_id,
        lifecycle_state=solution.lifecycle_state,
        domain=solution.domain,
        category=solution.category,
        is_mcq=solution.is_mcq,
        options=solution.options,
        selected_option=solution.selected_option,
        selected_option_text=solution.selected_option_text,
        step_by_step_explanation=solution.step_by_step_explanation,
        option_analysis=solution.option_analysis,
        sql_clauses=solution.sql_clauses,
        uncertain_spans=solution.uncertain_spans,
        raw_ocr_text=solution.raw_ocr_text,
    )

