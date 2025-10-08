from openai import OpenAI
import logging
import asyncio
import time
import json
from datetime import datetime
from config import OPENROUTER_API_KEY, MODEL_RANKING

# Настройка основного логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/root/stark/agent.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Настройка отдельного логгера для LLM метрик
llm_metrics_logger = logging.getLogger('llm_metrics')
llm_metrics_logger.setLevel(logging.INFO)
llm_metrics_handler = logging.FileHandler('/root/stark/llm_metrics.log', encoding='utf-8')
llm_metrics_handler.setFormatter(logging.Formatter('%(message)s'))
llm_metrics_logger.addHandler(llm_metrics_handler)
llm_metrics_logger.propagate = False

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


def log_llm_metrics(metrics_data: dict):
    """Логирует метрики LLM запросов в отдельный файл"""
    try:
        llm_metrics_logger.info(json.dumps(metrics_data, ensure_ascii=False))
    except Exception as e:
        logger.error(f"Ошибка логирования метрик LLM: {e}")


class AIAgent:
    def __init__(self, api_key: str = OPENROUTER_API_KEY):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        self.conversations = {}
        self.max_history = 3
        self.total_requests = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

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
        """Пытается сделать запрос к конкретной модели с обработкой ошибок и логированием метрик"""
        start_time = time.time()
        request_metrics = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'model': model['name'],
            'provider': model['provider'],
            'model_params': model['params'],
            'messages_count': len(messages),
            'last_user_message': messages[-1]['content'] if messages else '',
            'status': 'success',
            'error_type': None,
            'response_time_ms': 0,
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'cost_estimate': 0
        }

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

            # Извлекаем метрики из ответа
            if hasattr(completion, 'usage'):
                request_metrics.update({
                    'input_tokens': completion.usage.prompt_tokens,
                    'output_tokens': completion.usage.completion_tokens,
                    'total_tokens': completion.usage.total_tokens
                })

                # Обновляем общую статистику
                self.total_requests += 1
                self.total_input_tokens += completion.usage.prompt_tokens
                self.total_output_tokens += completion.usage.completion_tokens

            ai_response = completion.choices[0].message.content
            model_info = f"\n\n---\n*Отвечает {model['provider']} ({model['params']}B параметров)*"

            # Расчет времени ответа
            request_metrics['response_time_ms'] = int((time.time() - start_time) * 1000)

            # Примерная оценка стоимости (для бесплатных моделей = 0)
            request_metrics['cost_estimate'] = 0.0

            add_activity_log("INFO", f"Успешный ответ от {model['provider']}", user_id)

            # Логируем успешный запрос
            log_llm_metrics(request_metrics)

            return ai_response + model_info, True

        except Exception as e:
            error_msg = str(e)
            request_metrics.update({
                'status': 'error',
                'error_type': self._classify_error(error_msg),
                'response_time_ms': int((time.time() - start_time) * 1000)
            })

            # Логируем неудачный запрос
            log_llm_metrics(request_metrics)

            add_activity_log("ERROR", f"Ошибка {model['name']}: {error_msg}", user_id)
            return error_msg, False

    def _classify_error(self, error_msg: str) -> str:
        """Классифицирует тип ошибки"""
        if "429" in error_msg and "free-models-per-day" in error_msg:
            return "daily_rate_limit"
        elif "429" in error_msg and "free-models-per-min" in error_msg:
            return "minute_rate_limit"
        elif "429" in error_msg:
            return "rate_limit"
        elif "404" in error_msg:
            return "model_not_found"
        elif "401" in error_msg:
            return "auth_error"
        elif "500" in error_msg:
            return "server_error"
        else:
            return "unknown_error"

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

    def get_usage_statistics(self) -> dict:
        """Возвращает статистику использования"""
        return {
            'total_requests': self.total_requests,
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'total_tokens': self.total_input_tokens + self.total_output_tokens,
            'avg_input_tokens_per_request': self.total_input_tokens / max(1, self.total_requests),
            'avg_output_tokens_per_request': self.total_output_tokens / max(1, self.total_requests)
        }

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


def get_llm_metrics_sample(n: int = 10):
    """Возвращает последние N записей из лога метрик LLM"""
    try:
        with open('/root/stark/llm_metrics.log', 'r', encoding='utf-8') as f:
            lines = f.readlines()[-n:]
            return [json.loads(line.strip()) for line in lines if line.strip()]
    except Exception as e:
        logger.error(f"Ошибка чтения лога метрик: {e}")
        return []