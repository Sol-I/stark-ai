from openai import OpenAI
import logging
import asyncio
import time
import json
from datetime import datetime
from config import OPENROUTER_API_KEY, MODEL_RANKING

# Настройка логирования в файл
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/root/stark/agent.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Глобальный список для хранения логов (для веб-интерфейса)
activity_logs = []
MAX_LOG_ENTRIES = 1000


def add_activity_log(level: str, message: str, user_id: str = "system"):
    """Добавляет запись в лог активности"""
    log_entry = {
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'level': level,
        'user_id': user_id,
        'message': message
    }
    activity_logs.append(log_entry)

    # Ограничиваем размер лога
    if len(activity_logs) > MAX_LOG_ENTRIES:
        activity_logs.pop(0)

    logger.info(f"[{user_id}] {message}")


class AIAgent:
    def __init__(self, api_key: str = OPENROUTER_API_KEY):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        self.conversations = {}
        self.max_history = 3

        add_activity_log("INFO", "AI Agent инициализирован")

    async def handle_rate_limit(self, error_msg: str, user_id: str) -> str:
        """Обрабатывает лимиты и возвращает сообщение или None если нужно продолжить"""
        if "free-models-per-day" in error_msg:
            # Дневной лимит исчерпан
            add_activity_log("WARNING", "Дневной лимит OpenRouter исчерпан", user_id)
            return "⚠️ **Дневной лимит OpenRouter исчерпан** (50 запросов/день). Лимит сбросится в 03:00 по МСК."

        elif "free-models-per-min" in error_msg:
            # Минутный лимит - извлекаем время сброса
            try:
                error_data = json.loads(error_msg.split(" - ")[-1])
                reset_time = int(error_data['error']['metadata']['headers']['X-RateLimit-Reset'])
                current_time = int(time.time() * 1000)
                wait_seconds = max(1, (reset_time - current_time) // 1000)

                add_activity_log("INFO", f"Минутный лимит, ждем {wait_seconds} сек", user_id)
                await asyncio.sleep(wait_seconds)
                return None  # Продолжаем попытки

            except Exception as e:
                add_activity_log("ERROR", f"Ошибка парсинга лимита: {e}", user_id)
                await asyncio.sleep(60)  # Fallback - ждем минуту
                return None

        elif "Rate limit exceeded" in error_msg:
            # Общий лимит - ждем 60 секунд
            add_activity_log("WARNING", "Общий лимит OpenRouter, ждем 60 сек", user_id)
            await asyncio.sleep(60)
            return None

        return None

    async def try_model_request(self, model: dict, messages: list, user_id: str) -> tuple:
        """Пытается сделать запрос к конкретной модели с обработкой ошибок"""
        try:
            add_activity_log("DEBUG", f"Попытка запроса к {model['name']}", user_id)

            completion = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "http://94.228.123.86:8000",
                    "X-Title": "Stark AI",
                },
                model=model["name"],
                messages=messages,
                max_tokens=1024
            )

            ai_response = completion.choices[0].message.content
            model_info = f"\n\n---\n*Отвечает {model['provider']} ({model['params']}B параметров)*"

            add_activity_log("INFO", f"Успешный ответ от {model['provider']}", user_id)
            return ai_response + model_info, True

        except Exception as e:
            error_msg = str(e)
            add_activity_log("ERROR", f"Ошибка {model['name']}: {error_msg}", user_id)
            return error_msg, False

    async def process_message(self, user_id: str, message: str) -> str:
        add_activity_log("INFO", f"Получено сообщение: '{message}'", user_id)

        if user_id not in self.conversations:
            self.conversations[user_id] = []
            add_activity_log("DEBUG", f"Создана новая сессия для пользователя", user_id)

        current_history = self.conversations[user_id][-self.max_history:]
        current_history.append({"role": "user", "content": message})

        # Пробуем модели по порядку
        for model_index, model in enumerate(MODEL_RANKING):
            add_activity_log("DEBUG", f"Пробуем модель #{model_index + 1}: {model['name']}", user_id)

            response, success = await self.try_model_request(model, current_history, user_id)

            if success:
                # Успешный ответ
                current_history.append({"role": "assistant", "content": response})
                self.conversations[user_id] = current_history[-self.max_history:]
                add_activity_log("INFO", "Ответ сгенерирован успешно", user_id)
                return response

            else:
                # Обработка ошибок
                rate_limit_msg = await self.handle_rate_limit(response, user_id)
                if rate_limit_msg:
                    return rate_limit_msg  # Возвращаем сообщение о лимите

                # Если это не лимит, продолжаем с следующей моделью
                add_activity_log("INFO", f"Модель {model['name']} недоступна, пробуем следующую", user_id)
                continue

        # Если все модели не сработали
        error_msg = "❌ Все модели временно недоступны. Попробуйте позже."
        add_activity_log("ERROR", "Все модели недоступны", user_id)
        return error_msg

    async def background_model_checker(self):
        """Заглушка - фоновая проверка отключена"""
        add_activity_log("INFO", "Фоновая проверка моделей отключена")
        while True:
            await asyncio.sleep(3600)  # Просто спим

    def clear_history(self, user_id: str):
        if user_id in self.conversations:
            del self.conversations[user_id]
            add_activity_log("INFO", "История диалога очищена", user_id)


def get_activity_logs():
    """Возвращает логи для веб-интерфейса"""
    return activity_logs