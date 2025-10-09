import os
import logging
import json
import time
import asyncio
import httpx
from datetime import datetime
from openai import OpenAI
from config import OPENROUTER_API_KEY, HUGGINGFACE_API_KEY, API_ENDPOINTS, MODEL_RANKING

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/root/stark/agent.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

llm_metrics_logger = logging.getLogger('llm_metrics')
llm_metrics_logger.setLevel(logging.INFO)
llm_metrics_handler = logging.FileHandler('/root/stark/llm_metrics.log', encoding='utf-8')
llm_metrics_handler.setFormatter(logging.Formatter('%(message)s'))
llm_metrics_logger.addHandler(llm_metrics_handler)
llm_metrics_logger.propagate = False

activity_logs = []
MAX_LOG_ENTRIES = 1000

def add_activity_log(level: str, message: str, user_id: str = "system"):
    """
    API: Добавление записи в лог активности системы
    Вход: level (уровень), message (сообщение), user_id (идентификатор пользователя)
    Выход: None (запись добавляется в глобальный лог)
    Логика: Сохраняет до MAX_LOG_ENTRIES записей, автоматически удаляет старые
    """
    log_entry = {
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'level': level,
        'user_id': user_id,
        'message': message
    }
    activity_logs.append(log_entry)

    if len(activity_logs) > MAX_LOG_ENTRIES:
        activity_logs.pop(0)

    logger.info(f"[{user_id}] {message}")

def log_llm_metrics(metrics_data: dict):
    """
    API: Логирование метрик LLM запросов
    Вход: metrics_data (словарь с метриками запроса)
    Выход: None (данные записываются в отдельный лог-файл)
    Логика: JSON-логирование в llm_metrics.log для анализа производительности
    """
    try:
        llm_metrics_logger.info(json.dumps(metrics_data, ensure_ascii=False))
    except Exception as e:
        logger.error(f"Ошибка логирования метрик LLM: {e}")

class AIAgent:
    """
    AI Agent - ядро интеллектуального ассистента
    API: Обработка сообщений пользователя через каскад LLM моделей
    Основные возможности: автоматический выбор модели, обработка лимитов, логирование
    """
    def __init__(self):
        """
        API: Инициализация AI Agent
        Вход: None (использует конфигурацию из config.py)
        Выход: None (создает экземпляр агента)
        Логика: Настраивает клиенты API, инициализирует хранилище конверсаций
        """
        self.openrouter_client = OpenAI(
            base_url=API_ENDPOINTS["openrouter"],
            api_key=OPENROUTER_API_KEY,
        )
        self.huggingface_headers = {
            "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
            "Content-Type": "application/json"
        }
        self.conversations = {}
        self.max_history = 3
        self.total_requests = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        add_activity_log("INFO", "AI Agent инициализирован с поддержкой OpenRouter и HuggingFace")

    async def make_openrouter_request(self, model: dict, messages: list) -> dict:
        """
        API: Запрос к OpenRouter API
        Вход: model (конфиг модели), messages (история диалога в формате OpenAI)
        Выход: dict {response: str, usage: объект использования токенов}
        Логика: Создает chat completion с указанной моделью и параметрами
        """
        completion = self.openrouter_client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "http://94.228.123.86:8000",
                "X-Title": "Stark AI",
            },
            model=model["name"],
            messages=messages,
            max_tokens=1024,
            temperature=0.7
        )

        return {
            "response": completion.choices[0].message.content,
            "usage": completion.usage if hasattr(completion, 'usage') else None
        }

    async def make_huggingface_request(self, model: dict, messages: list) -> dict:
        """
        API: Запрос к HuggingFace Inference API
        Вход: model (конфиг модели), messages (история диалога)
        Выход: dict {response: str, usage: None}
        Логика: Форматирует промпт для HF моделей, обрабатывает различные форматы ответов
        """
        formatted_messages = []
        for msg in messages:
            if msg["role"] == "user":
                formatted_messages.append(f"<|user|>\n{msg['content']}")
            elif msg["role"] == "assistant":
                formatted_messages.append(f"<|assistant|>\n{msg['content']}")

        prompt = "\n".join(formatted_messages) + "\n<|assistant|>\n"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_ENDPOINTS['huggingface']}/models/{model['name']}",
                headers=self.huggingface_headers,
                json={
                    "inputs": prompt,
                    "parameters": {
                        "max_new_tokens": 1024,
                        "temperature": 0.7,
                        "do_sample": True
                    }
                },
                timeout=30.0
            )

            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    if 'generated_text' in result[0]:
                        generated_text = result[0]['generated_text']
                        ai_response = generated_text.replace(prompt, "").strip()
                    else:
                        ai_response = str(result[0])
                else:
                    ai_response = str(result)

                return {
                    "response": ai_response,
                    "usage": None
                }
            else:
                raise Exception(f"HuggingFace API error: {response.status_code} - {response.text}")

    async def handle_rate_limit(self, error_msg: str, user_id: str) -> str:
        """
        API: Обработка лимитов запросов API
        Вход: error_msg (текст ошибки), user_id (идентификатор пользователя)
        Выход: str или None (сообщение пользователю или None для повторной попытки)
        Логика: Анализирует тип лимита, возвращает сообщение или делает паузу
        """
        if "free-models-per-day" in error_msg:
            add_activity_log("WARNING", "Дневной лимит OpenRouter исчерпан", user_id)
            return "⚠️ **Дневной лимит OpenRouter исчерпан** (50 запросов/день). Лимит сбросится в 03:00 по МСК."

        elif "free-models-per-min" in error_msg:
            try:
                error_data = json.loads(error_msg.split(" - ")[-1])
                reset_time = int(error_data['error']['metadata']['headers']['X-RateLimit-Reset'])
                current_time = int(time.time() * 1000)
                wait_seconds = max(1, (reset_time - current_time) // 1000)

                add_activity_log("INFO", f"Минутный лимит, ждем {wait_seconds} сек", user_id)
                await asyncio.sleep(wait_seconds)
                return None

            except Exception as e:
                add_activity_log("ERROR", f"Ошибка парсинга лимита: {e}", user_id)
                await asyncio.sleep(60)
                return None

        elif "Rate limit exceeded" in error_msg or "429" in error_msg:
            add_activity_log("WARNING", "Общий лимит, ждем 60 сек", user_id)
            await asyncio.sleep(60)
            return None

        return None

    async def try_model_request(self, model: dict, messages: list, user_id: str) -> tuple:
        """
        API: Попытка запроса к конкретной LLM модели
        Вход: model (конфиг модели), messages (история диалога), user_id
        Выход: tuple (ответ: str, успех: bool)
        Логика: Выбор провайдера API, логирование метрик, обработка ошибок
        """
        start_time = time.time()
        request_metrics = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'model': model['name'],
            'provider': model['provider'],
            'api_provider': model['api_provider'],
            'model_params': model['params'],
            'messages_count': len(messages),
            'last_user_message': messages[-1]['content'][:100] if messages and messages[-1].get('content') else '',
            'status': 'success',
            'error_type': None,
            'response_time_ms': 0,
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'cost_estimate': 0
        }

        try:
            add_activity_log("DEBUG", f"Попытка запроса к {model['name']} ({model['api_provider']})", user_id)

            if model['api_provider'] == 'openrouter':
                result = await self.make_openrouter_request(model, messages)
            elif model['api_provider'] == 'huggingface':
                result = await self.make_huggingface_request(model, messages)
            else:
                raise ValueError(f"Unknown API provider: {model['api_provider']}")

            ai_response = result["response"]

            if result["usage"]:
                request_metrics.update({
                    'input_tokens': result["usage"].prompt_tokens,
                    'output_tokens': result["usage"].completion_tokens,
                    'total_tokens': result["usage"].total_tokens
                })

                self.total_requests += 1
                self.total_input_tokens += result["usage"].prompt_tokens
                self.total_output_tokens += result["usage"].completion_tokens

            model_info = f"\n\n---\n*Отвечает {model['provider']} ({model['params']}B параметров) через {model['api_provider'].upper()}*"

            request_metrics['response_time_ms'] = int((time.time() - start_time) * 1000)
            request_metrics['cost_estimate'] = 0.0

            add_activity_log("INFO", f"Успешный ответ от {model['provider']} через {model['api_provider']}", user_id)

            log_llm_metrics(request_metrics)

            return ai_response + model_info, True

        except Exception as e:
            error_msg = str(e)
            request_metrics.update({
                'status': 'error',
                'error_type': self._classify_error(error_msg),
                'response_time_ms': int((time.time() - start_time) * 1000)
            })

            log_llm_metrics(request_metrics)

            add_activity_log("ERROR", f"Ошибка {model['name']} ({model['api_provider']}): {error_msg}", user_id)
            return error_msg, False

    def _classify_error(self, error_msg: str) -> str:
        """
        API: Классификация ошибок API
        Вход: error_msg (текст ошибки)
        Выход: str (тип ошибки)
        Логика: Анализирует текст ошибки для определения категории проблемы
        """
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
        """
        API: Основной метод обработки сообщений пользователя
        Вход: user_id (идентификатор сессии), message (текст сообщения)
        Выход: str (ответ ИИ)
        Логика: Последовательно пробует модели из MODEL_RANKING, сохраняет историю диалога
        """
        add_activity_log("INFO", f"Получено сообщение: '{message}'", user_id)

        if user_id not in self.conversations:
            self.conversations[user_id] = []
            add_activity_log("DEBUG", f"Создана новая сессия для пользователя", user_id)

        current_history = self.conversations[user_id][-self.max_history:]
        current_history.append({"role": "user", "content": message})

        for model_index, model in enumerate(MODEL_RANKING):
            add_activity_log("DEBUG", f"Пробуем модель #{model_index + 1}: {model['name']} ({model['api_provider']})",
                             user_id)

            response, success = await self.try_model_request(model, current_history, user_id)

            if success:
                current_history.append({"role": "assistant", "content": response})
                self.conversations[user_id] = current_history[-self.max_history:]
                add_activity_log("INFO", "Ответ сгенерирован успешно", user_id)
                return response

            else:
                rate_limit_msg = await self.handle_rate_limit(response, user_id)
                if rate_limit_msg:
                    return rate_limit_msg

                add_activity_log("INFO", f"Модель {model['name']} недоступна, пробуем следующую", user_id)
                continue

        error_msg = "❌ Все модели временно недоступны. Попробуйте позже."
        add_activity_log("ERROR", "Все модели недоступны", user_id)
        return error_msg

    def get_usage_statistics(self) -> dict:
        """
        API: Получение статистики использования
        Вход: None
        Выход: dict (статистика запросов и токенов)
        Логика: Агрегирует данные по всем выполненным запросам
        """
        return {
            'total_requests': self.total_requests,
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'total_tokens': self.total_input_tokens + self.total_output_tokens,
            'avg_input_tokens_per_request': self.total_input_tokens / max(1, self.total_requests),
            'avg_output_tokens_per_request': self.total_output_tokens / max(1, self.total_requests)
        }

    async def background_model_checker(self):
        """
        API: Фоновая проверка доступности моделей
        Вход: None
        Выход: None (бесконечный цикл)
        Логика: Периодически проверяет доступность топ-5 моделей раз в час
        """
        add_activity_log("INFO", "Фоновая проверка моделей запущена")
        while True:
            try:
                for i in range(min(5, len(MODEL_RANKING))):
                    model = MODEL_RANKING[i]
                    try:
                        test_message = [{"role": "user", "content": "test"}]
                        if model['api_provider'] == 'openrouter':
                            await asyncio.wait_for(
                                self.openrouter_client.chat.completions.create(
                                    model=model["name"],
                                    messages=test_message,
                                    max_tokens=5
                                ),
                                timeout=10.0
                            )
                        else:
                            async with httpx.AsyncClient() as client:
                                await client.get(
                                    f"{API_ENDPOINTS['huggingface']}/models/{model['name']}",
                                    headers=self.huggingface_headers,
                                    timeout=10.0
                                )
                        add_activity_log("DEBUG", f"Модель {model['name']} доступна")
                    except Exception:
                        add_activity_log("DEBUG", f"Модель {model['name']} недоступна")

                await asyncio.sleep(3600)

            except Exception as e:
                add_activity_log("ERROR", f"Ошибка в фоновой проверке: {e}")
                await asyncio.sleep(300)

    def clear_history(self, user_id: str):
        """
        API: Очистка истории диалога пользователя
        Вход: user_id (идентификатор пользователя)
        Выход: None
        Логика: Удаляет историю сообщений для указанного пользователя
        """
        if user_id in self.conversations:
            del self.conversations[user_id]
            add_activity_log("INFO", "История диалога очищена", user_id)

def get_activity_logs():
    """
    API: Получение логов активности системы
    Вход: None
    Выход: list (список записей лога)
    """
    return activity_logs

def get_llm_metrics_sample(n: int = 10):
    """
    API: Получение выборки метрик LLM запросов
    Вход: n (количество последних записей)
    Выход: list (список метрик в формате JSON)
    """
    try:
        with open('/root/stark/llm_metrics.log', 'r', encoding='utf-8') as f:
            lines = f.readlines()[-n:]
            return [json.loads(line.strip()) for line in lines if line.strip()]
    except Exception as e:
        logger.error(f"Ошибка чтения лога метрик: {e}")
        return []