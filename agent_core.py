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
        self.model_ranking = MODEL_RANKING
        self.current_model_index = 0
        self.last_request_time = 0
        self.request_delay = 8  # Задержка 8 секунд между запросами

        add_activity_log("INFO", "AI Agent инициализирован")

    async def rate_limit_delay(self):
        """Добавляет задержку между запросами для соблюдения лимитов"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.request_delay:
            sleep_time = self.request_delay - time_since_last_request
            add_activity_log("DEBUG", f"Задержка {sleep_time:.2f} сек перед запросом")
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()

    async def check_model_availability(self, model_name: str) -> bool:
        """Проверяет доступность модели"""
        try:
            await self.rate_limit_delay()

            add_activity_log("DEBUG", f"Проверка доступности модели: {model_name}")

            test_message = [{"role": "user", "content": "test"}]
            completion = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "http://94.228.123.86:8000",
                    "X-Title": "Stark AI",
                },
                model=model_name,
                messages=test_message,
                max_tokens=10
            )

            add_activity_log("INFO", f"Модель {model_name} доступна")
            return True

        except Exception as e:
            add_activity_log("WARNING", f"Модель {model_name} недоступна: {str(e)}")
            return False

    async def process_message(self, user_id: str, message: str) -> str:
        add_activity_log("INFO", f"Получено сообщение: '{message}'", user_id)

        if user_id not in self.conversations:
            self.conversations[user_id] = []
            add_activity_log("DEBUG", f"Создана новая сессия для пользователя", user_id)

        current_history = self.conversations[user_id][-self.max_history:]
        current_history.append({"role": "user", "content": message})

        try:
            await self.rate_limit_delay()

            current_model = self.model_ranking[self.current_model_index]
            add_activity_log("DEBUG", f"Используется модель: {current_model['name']}", user_id)

            # Пробуем текущую модель
            try:
                add_activity_log("DEBUG", "Отправка запроса к API", user_id)

                completion = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "http://94.228.123.86:8000",
                        "X-Title": "Stark AI",
                    },
                    model=current_model["name"],
                    messages=current_history,
                    max_tokens=1024
                )

                ai_response = completion.choices[0].message.content
                model_info = f"\n\n---\n*Отвечает {current_model['provider']} ({current_model['params']}B параметров)*"

                add_activity_log("INFO", f"Успешный ответ от {current_model['provider']}", user_id)

            except Exception as e:
                error_msg = str(e)
                add_activity_log("ERROR", f"Ошибка модели {current_model['name']}: {error_msg}", user_id)

                if "429" in error_msg:
                    return "⚠️ Слишком много запросов. Подожди 1 минуту и попробуй снова."

                # Если текущая модель не работает, ищем лучшую доступную
                add_activity_log("INFO", "Поиск альтернативной модели", user_id)
                best_model_name = await self.find_best_available_model()
                best_model = self.model_ranking[self.current_model_index]

                completion = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "http://94.228.123.86:8000",
                        "X-Title": "Stark AI",
                    },
                    model=best_model_name,
                    messages=current_history,
                    max_tokens=1024
                )

                ai_response = completion.choices[0].message.content
                model_info = f"\n\n---\n*Автоматически переключился на {best_model['provider']} ({best_model['params']}B)*"

                add_activity_log("INFO", f"Переключился на модель: {best_model['name']}", user_id)

            current_history.append({"role": "assistant", "content": ai_response})
            self.conversations[user_id] = current_history[-self.max_history:]

            add_activity_log("INFO", "Ответ сгенерирован успешно", user_id)
            return ai_response + model_info

        except Exception as e:
            error_msg = f"Критическая ошибка: {str(e)}"
            add_activity_log("ERROR", error_msg, user_id)
            return f"Ошибка: {str(e)}"

    async def find_best_available_model(self) -> str:
        """Находит лучшую доступную модель"""
        add_activity_log("INFO", "Поиск лучшей доступной модели")

        for i, model in enumerate(self.model_ranking):
            if await self.check_model_availability(model["name"]):
                self.current_model_index = i
                add_activity_log("INFO", f"Выбрана модель: {model['name']} ({model['params']}B)")
                return model["name"]

        # Если ничего не доступно, возвращаем последнюю работающую
        fallback_model = self.model_ranking[-1]["name"]
        add_activity_log("WARNING", f"Все модели недоступны, используем fallback: {fallback_model}")
        return fallback_model

    async def background_model_checker(self):
        """Фоновая проверка доступности лучших моделей"""
        add_activity_log("INFO", "Запущена фоновая проверка моделей")

        while True:
            try:
                # Проверяем доступность моделей с высоким рейтингом
                for i in range(3):  # Проверяем топ-3 модели
                    if i != self.current_model_index and await self.check_model_availability(
                            self.model_ranking[i]["name"]):
                        if i < self.current_model_index:  # Если нашли модель лучше текущей
                            self.current_model_index = i
                            add_activity_log("INFO", f"Вернулся к лучшей модели: {self.model_ranking[i]['name']}")
                            break

                await asyncio.sleep(300)  # Проверяем каждые 5 минут

            except Exception as e:
                add_activity_log("ERROR", f"Ошибка в фоновой проверке: {str(e)}")
                await asyncio.sleep(60)

    def clear_history(self, user_id: str):
        if user_id in self.conversations:
            del self.conversations[user_id]
            add_activity_log("INFO", "История диалога очищена", user_id)


def get_activity_logs():
    """Возвращает логи для веб-интерфейса"""
    return activity_logs