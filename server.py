from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import asyncio
from agent_core import AIAgent
from config import HOST, PORT

app = FastAPI(title="Stark AI")
agent = AIAgent()

# Запускаем фоновую проверку при старте
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(agent.background_model_checker())

class MessageRequest(BaseModel):
    user_id: str
    message: str

@app.post("/api/chat")
async def chat_endpoint(request: MessageRequest):
    response = await agent.process_message(request.user_id, request.message)
    return {"response": response}

@app.post("/api/clear")
async def clear_history(user_id: str):
    agent.clear_history(user_id)
    return {"status": "ok"}

@app.get("/")
async def web_interface():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")

def run_server():
    uvicorn.run(app, host=HOST, port=PORT, workers=1, access_log=False)
