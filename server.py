"""
FastAPI Server - веб-интерфейс и REST API для Stark AI
API: Обработка HTTP запросов, управление чатом через AI Agent, обслуживание веб-интерфейса
Основные возможности: REST API для чата, веб-интерфейс, управление историей диалогов
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import asyncio
from pydantic import BaseModel
import logging

# Импорт системы логирования
from database import add_activity_log
from agent_core import AIAgent

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Stark AI",
    description="Веб-интерфейс и API для AI ассистента",
    version="1.0.0"
)

# Глобальный экземпляр агента
agent = AIAgent()

class MessageRequest(BaseModel):
    user_id: str
    message: str

class ClearRequest(BaseModel):
    user_id: str

@app.on_event("startup")
async def startup_event():
    add_activity_log("INFO", "FastAPI сервер запущен", "system")
    logger.info("🚀 FastAPI сервер запущен на http://localhost:8000")

@app.post("/api/chat")
async def chat_endpoint(request: MessageRequest):
    try:
        add_activity_log("INFO", f"Веб-запрос от {request.user_id}: '{request.message}'", request.user_id)
        logger.info(f"Обработка веб-запроса от {request.user_id}")

        response = await agent.process_message(request.user_id, request.message)

        add_activity_log("INFO", f"Веб-ответ для {request.user_id} ({len(response)} символов)", request.user_id)
        logger.info(f"Ответ отправлен пользователю {request.user_id}")

        return {"response": response, "status": "success"}

    except Exception as e:
        error_msg = f"Ошибка обработки веб-запроса: {e}"
        add_activity_log("ERROR", error_msg, request.user_id)
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/api/clear")
async def clear_history(request: ClearRequest):
    try:
        success = agent.clear_conversation_history(request.user_id)

        if success:
            add_activity_log("INFO", f"История очищена для {request.user_id}", request.user_id)
            logger.info(f"История диалога очищена для пользователя {request.user_id}")
            return {"status": "success", "message": "История диалога очищена"}
        else:
            add_activity_log("WARNING", f"История не найдена для {request.user_id}", request.user_id)
            logger.warning(f"История не найдена для пользователя {request.user_id}")
            return {"status": "info", "message": "История диалога не найдена"}

    except Exception as e:
        error_msg = f"Ошибка очистки истории: {e}"
        add_activity_log("ERROR", error_msg, request.user_id)
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/api/health")
async def health_check():
    try:
        active_users = len(agent.get_active_users())
        return {
            "status": "healthy",
            "timestamp": str(asyncio.get_event_loop().time()),
            "active_users": active_users,
            "service": "Stark AI API"
        }
    except Exception as e:
        logger.error(f"Ошибка health check: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")

@app.get("/api/logs")
async def get_recent_logs(limit: int = 15):
    try:
        from database import get_recent_logs
        logs = get_recent_logs(limit)
        formatted_logs = []
        for log in logs:
            formatted_logs.append({
                'level': log.level,
                'message': log.message,
                'user_id': log.user_id or 'system',
                'timestamp': log.timestamp.strftime('%H:%M:%S') if log.timestamp else 'unknown'
            })
        return {"logs": formatted_logs, "status": "success", "total": len(formatted_logs)}
    except Exception as e:
        logger.error(f"Ошибка получения логов: {e}")
        return {"logs": [], "status": "error", "error": str(e)}

@app.get("/api/models")
async def get_available_models():
    try:
        await agent.ensure_initialized()
        models = []
        if hasattr(agent, 'model_ranking') and agent.model_ranking:
            for model in agent.model_ranking[:10]:
                models.append({
                    'name': model.get('name', 'Unknown'),
                    'provider': model.get('api_provider', 'Unknown'),
                    'description': model.get('description', '')[:100] + '...' if len(model.get('description', '')) > 100 else model.get('description', ''),
                    'context_length': model.get('context_length', 0)
                })
        return {"models": models, "status": "success", "total": len(models)}
    except Exception as e:
        logger.error(f"Ошибка получения моделей: {e}")
        return {"models": [], "status": "error", "error": str(e)}

@app.get("/")
async def web_interface():
    try:
        add_activity_log("INFO", "Запрос веб-интерфейса", "web_user")
        logger.info("Обслуживание веб-интерфейса")
        return FileResponse("static/index.html")
    except Exception as e:
        error_msg = f"Ошибка загрузки веб-интерфейса: {e}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

app.mount("/static", StaticFiles(directory="static"), name="static")

def run_server(host: str = "0.0.0.0", port: int = 8000):
    try:
        add_activity_log("INFO", f"Запуск сервера на {host}:{port}", "system")
        logger.info(f"Starting uvicorn server on {host}:{port}")
        uvicorn.run(app, host=host, port=port, workers=1, access_log=False, log_config=None)
    except Exception as e:
        error_msg = f"Ошибка запуска сервера: {e}"
        add_activity_log("ERROR", error_msg, "system")
        logger.error(error_msg)
        raise

if __name__ == "__main__":
    run_server()