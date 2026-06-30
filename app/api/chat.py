from fastapi import APIRouter
from app.schemas.chat import ChatRequest
from app.services.diagnosis_service import chat_with_agent

router = APIRouter()

@router.post("/chat")
async def chat(request: ChatRequest):
    return await chat_with_agent(user_id=request.user_id, user_message=request.message)