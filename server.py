"""
FastAPI Server - веб-интерфейс и REST API для AI Agent
Основные эндпоинты:
- /api/chat - основной чат
- /api/clear - очистка истории
- /api/logs - получение логов
- /api/metrics - статистика использования
- / - веб-интерфейс
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import asyncio
from pydantic import BaseModel
from agent_core import AIAgent, add_activity_log, get_activity_logs, get_llm_metrics_sample
from config import HOST, PORT

app = FastAPI(title="Stark AI")
agent = AIAgent()

class MessageRequest(BaseModel):
    """
    Модель данных для запроса чата
    Поля:
    - user_id: идентификатор пользователя для контекста
    - message: текст сообщения пользователя
    """
    user_id: str
    message: str

@app.on_event("startup")
async def startup_event():
    """
    API: Обработчик запуска сервера
    Вход: None
    Выход: None
    Логика: Запускает фоновую проверку моделей при старте сервера
    """
    asyncio.create_task(agent.background_model_checker())
    add_activity_log("INFO", "Сервер запущен")

@app.post("/api/chat")
async def chat_endpoint(request: MessageRequest):
    """
    API: Основной эндпоинт чата
    Вход: MessageRequest (user_id, message)
    Выход: JSON {response: str}
    Логика: Вызывает agent.process_message(), сохраняет контекст по user_id
    """
    response = await agent.process_message(request.user_id, request.message)
    return {"response": response}

@app.post("/api/clear")
async def clear_history(user_id: str):
    """
    API: Очистка истории диалога
    Вход: user_id (идентификатор пользователя)
    Выход: JSON {status: "ok"}
    Логика: Вызывает agent.clear_history() для указанного пользователя
    """
    agent.clear_history(user_id)
    return {"status": "ok"}

@app.get("/api/logs")
async def get_logs():
    """
    API: Получение логов активности
    Вход: None
    Выход: JSON {logs: list}
    Логика: Возвращает последние записи из системного лога
    """
    return {"logs": get_activity_logs()}

@app.get("/api/metrics")
async def get_metrics():
    """
    API: Получение метрик LLM запросов
    Вход: None
    Выход: JSON {usage_statistics: dict, recent_requests: list}
    Логика: Статистика использования и последние запросы к моделям
    """
    return {
        "usage_statistics": agent.get_usage_statistics(),
        "recent_requests": get_llm_metrics_sample(20)
    }

@app.get("/")
async def web_interface():
    """
    API: Веб-интерфейс приложения
    Вход: None
    Выход: HTML страница (static/index.html)
    Логика: Отдает статический файл веб-интерфейса
    """
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")

def run_server():
    """
    API: Запуск сервера uvicorn
    Вход: None
    Выход: None (блокирующий вызов)
    Логика: Запускает FastAPI приложение с указанными параметрами
    """
    uvicorn.run(app, host=HOST, port=PORT, workers=1, access_log=False)