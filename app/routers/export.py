from fastapi import APIRouter, Response
from app.services.export_service import get_export_csv_bytes

router = APIRouter(tags=["export"])


@router.get("/api/export/csv")
async def export_current_csv():
    csv_bytes, export_name = get_export_csv_bytes()
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{export_name}"'}
    )
