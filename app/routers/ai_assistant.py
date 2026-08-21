from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.core.state import state
from app.services.ai_service import chat_with_ai, reset_ai_session

router = APIRouter(tags=["ai-assistant"])


@router.post("/api/ai-assistant/settings")
async def set_ai_settings(payload: dict):
    key = (payload.get("apiKey") or "").strip()
    if key:
        state.user_gemini_api_key = key
        return JSONResponse(content={"ok": True, "message": "Gemini API anahtarı kaydedildi."})
    return JSONResponse(status_code=400, content={"ok": False, "message": "API anahtarı boş olamaz."})


@router.get("/api/ai-assistant/settings")
async def get_ai_settings():
    has_key = bool(state.user_gemini_api_key)
    masked_key = ""
    if has_key:
        masked_key = state.user_gemini_api_key[:4] + "..." + state.user_gemini_api_key[-4:] if len(state.user_gemini_api_key) > 8 else "***"
    return JSONResponse(content={"has_key": has_key, "masked_key": masked_key})


@router.post("/api/ai-assistant/chat")
async def ai_assistant_chat(payload: dict):
    result = chat_with_ai(payload)
    status_code = result.get("status_code", 200)
    return JSONResponse(status_code=status_code, content=result)


@router.post("/api/ai-assistant/reset")
async def reset_ai_session_endpoint(payload: dict):
    session_id = (payload.get("session_id") or "").strip()
    reset_ai_session(session_id)
    return JSONResponse(content={"ok": True})
