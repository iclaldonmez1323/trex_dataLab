import os
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["views"])


@router.get("/")
@router.get("/index.html")
async def serve_root():
    return FileResponse("static/index.html")


@router.get("/data-quality")
@router.get("/data-quality.html")
async def serve_data_quality():
    return FileResponse("static/data-quality.html")


@router.get("/preprocessing")
@router.get("/preprocessing.html")
async def serve_preprocessing():
    return FileResponse("static/preprocessing.html")


@router.get("/visualization")
@router.get("/visualization.html")
async def serve_visualization():
    return FileResponse("static/visualization.html")


@router.get("/portfolio")
@router.get("/portfolio.html")
async def serve_portfolio():
    return FileResponse("static/portfolio.html")


@router.get("/machine-learning")
@router.get("/machine-learning.html")
async def serve_machine_learning():
    return FileResponse("static/machine-learning.html")


@router.get("/settings")
@router.get("/settings.html")
async def serve_settings():
    return FileResponse("static/settings.html")


@router.get("/support")
@router.get("/support.html")
async def serve_support():
    return FileResponse("static/support.html")
