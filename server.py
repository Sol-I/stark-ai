from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import asyncio
from agent_core import AIAgent, get_activity_logs, add_activity_log, get_llm_metrics_sample
from config import HOST, PORT

app = FastAPI(title="Stark AI")
agent = AIAgent()

class MessageRequest(BaseModel):
    user_id: str
    message: str

# Запускаем фоновую проверку при старте
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(agent.background_model_checker())
    add_activity_log("INFO", "Сервер запущен")

@app.post("/api/chat")
async def chat_endpoint(request: MessageRequest):
    response = await agent.process_message(request.user_id, request.message)
    return {"response": response}

@app.post("/api/clear")
async def clear_history(user_id: str):
    agent.clear_history(user_id)
    return {"status": "ok"}

@app.get("/api/logs")
async def get_logs():
    """Endpoint для получения логов"""
    return {"logs": get_activity_logs()}

@app.get("/api/metrics")
async def get_metrics():
    """Endpoint для получения метрик LLM"""
    return {
        "usage_statistics": agent.get_usage_statistics(),
        "recent_requests": get_llm_metrics_sample(20)
    }

@app.get("/")
async def web_interface():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")

def run_server():
    uvicorn.run(app, host=HOST, port=PORT, workers=1, access_log=False)