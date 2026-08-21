from typing import Dict, Any
from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from app.services.preprocessing_service import (
    build_preprocessing_state_response,
    apply_preprocessing_op,
    undo_preprocessing_op,
    reset_preprocessing_ops
)
from app.services.export_service import get_cleaned_csv_bytes

router = APIRouter(tags=["preprocessing"])


@router.get("/api/preprocessing")
async def get_preprocessing_data():
    return JSONResponse(content=build_preprocessing_state_response())


@router.post("/api/preprocessing/apply")
async def apply_preprocessing(payload: Dict[str, Any]):
    return JSONResponse(content=apply_preprocessing_op(payload))


@router.post("/api/preprocessing/undo")
async def undo_preprocessing():
    return JSONResponse(content=undo_preprocessing_op())


@router.post("/api/preprocessing/reset")
async def reset_preprocessing():
    return JSONResponse(content=reset_preprocessing_ops())


@router.get("/api/preprocessing/download")
async def download_cleaned_csv():
    csv_bytes, cleaned_name = get_cleaned_csv_bytes()
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{cleaned_name}"'}
    )
