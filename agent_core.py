"""
AI Agent Core - ядро системы искусственного интеллекта
API: Универсальный обработчик запросов к LLM провайдерам с мониторингом лимитов
Основные возможности: ротация моделей, трекинг использования, обработка ошибок, логирование в БД
"""

import logging
import asyncio
import time
import json
import aiohttp
from typing import Dict, List, Tuple, Optional, Any

# Конфигурация системы
from config import (
    OPENROUTER_API_KEY,
    HUGGINGFACE_API_KEY,
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    GOOGLE_API_KEY,
    MODEL_RANKING,
    MAX_HISTORY_LENGTH,
    REQUEST_TIMEOUT
)

# Импорт системы логирования
from database import add_activity_log, create_llm_request

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AIAgent:
    """
    AI Agent - основной класс обработки запросов к LLM провайдерам
    API: Управление диалогами, ротация моделей, мониторинг лимитов, логирование операций
    Основные возможности: отказоустойчивость, многомодельность, трекинг использования, аналитика
    """

    def __init__(self):
        """
        API: Инициализация AI Agent
        Вход: None
        Выход: None (создает экземпляр агента)
        Логика: Инициализация кэшей, истории диалогов, метрик использования
        """
        self.conversations: Dict[str, List[Dict]] = {}
        self.max_history = MAX_HISTORY_LENGTH or 10
        self.request_timeout = REQUEST_TIMEOUT or 30
        self.last_request_time = 0
        self.min_request_interval = 0.1

        add_activity_log("INFO", "AI Agent инициализирован с системой мониторинга лимитов", "system")
        logger.info("AI Agent initialized with %d models", len(MODEL_RANKING))

    async def process_message(self, user_id: str, message: str, endpoint: str = "unknown",
                              process_type: str = "chat",
                              process_details: str = None) -> str:
        """
        API: Основной метод обработки сообщений пользователя
        Вход: user_id (идентификатор сессии), message (текст сообщения), endpoint (источник запроса), process_type (тип процесса), process_details (детали)
        Выход: str (ответ ИИ или сообщение об ошибке)
        Логика: Последовательно пробует модели из MODEL_RANKING, логирует все операции в БД
        """
        try:
            add_activity_log("INFO", f"Получено сообщение через {endpoint}: '{message[:100]}...'", user_id)

            # Защита от слишком частых запросов
            await self._rate_limit_protection()

            # Инициализация сессии пользователя
            if user_id not in self.conversations:
                self.conversations[user_id] = []
                add_activity_log("DEBUG", f"Создана новая сессия пользователя", user_id)

            # Обновление истории диалога
            current_history = self.conversations[user_id][-self.max_history:]
            current_history.append({"role": "user", "content": message})

            # Последовательная попытка моделей по приоритету
            for model_index, model in enumerate(MODEL_RANKING):
                model_info = f"{model['name']} ({model['api_provider']})"
                add_activity_log("DEBUG", f"Попытка #{model_index + 1}: {model_info}", user_id)

                response, success = await self._try_model_request(model, current_history, user_id, endpoint,
                                                                  process_type, process_details)

                if success:
                    # Успешный ответ - сохраняем историю и возвращаем результат
                    current_history.append({"role": "assistant", "content": response})
                    self.conversations[user_id] = current_history[-self.max_history:]
                    add_activity_log("INFO", f"Успешный ответ от {model_info}", user_id)
                    return response
                else:
                    # Обработка ограничений лимитов
                    limit_msg = await self._handle_api_limits(response, user_id)
                    if limit_msg:
                        return limit_msg

                    add_activity_log("INFO", f"Модель {model_info} недоступна", user_id)
                    continue

            # Все модели недоступны
            error_msg = "❌ Все модели временно недоступны. Попробуйте позже."
            add_activity_log("ERROR", "Все модели в ротации недоступны", user_id)
            return error_msg

        except Exception as e:
            error_msg = f"❌ Системная ошибка обработки сообщения: {str(e)}"
            add_activity_log("ERROR", f"Критическая ошибка process_message: {e}", user_id)
            return error_msg

    async def _try_model_request(self, model: Dict[str, Any], history: List[Dict],
                                 user_id: str, endpoint: str,
                                 process_type: str = "chat", process_details: str = None) -> Tuple[str, bool]:
        """
        API: Попытка запроса к конкретной модели с полным логированием
        Вход: model (конфиг модели), history (история диалога), user_id (идентификатор),
              endpoint (источник), process_type (тип процесса), process_details (детали процесса)
        Выход: tuple (response, success) - ответ и статус успеха
        Логика: Выполняет запрос к API с трекингом токенов, времени и ошибок
        """
        start_time = time.time()
        prompt = self._build_prompt(history)

        try:
            add_activity_log("DEBUG", f"Запрос к {model['name']}", user_id)

            # Универсальный вызов API
            response = await self._call_universal_api(model, prompt, user_id)

            # Обработка успешного ответа
            if response and response.strip():
                duration_ms = int((time.time() - start_time) * 1000)
                prompt_tokens = self._estimate_tokens(prompt)
                completion_tokens = self._estimate_tokens(response)

                # Логирование успешного запроса в БД
                await self._log_llm_request(
                    user_id=user_id,
                    provider=model['api_provider'],
                    model=model['name'],
                    endpoint=endpoint,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    success=True,
                    duration_ms=duration_ms,
                    estimated_limits=80,
                    process_type=process_type,
                    process_details=process_details
                )

                add_activity_log("INFO", f"Успешный ответ ({len(response)} символов)", user_id)
                return response, True
            else:
                # Пустой ответ
                add_activity_log("WARNING", f"Пустой ответ от модели", user_id)
                return "Пустой ответ от модели", False

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_type = self._extract_error_type(e)
            estimated_limits = self._estimate_limits_remaining(e)

            await self._log_llm_request(
                user_id=user_id,
                provider=model['api_provider'],
                model=model['name'],
                endpoint=endpoint,
                prompt_tokens=self._estimate_tokens(prompt),
                success=False,
                error_type=error_type,
                error_message=f"API error: {str(e)}",
                duration_ms=duration_ms,
                estimated_limits=estimated_limits,
                process_type=process_type,
                process_details=process_details
            )

            return f"Ошибка API: {str(e)}", False

    async def _call_universal_api(self, model: Dict[str, Any], prompt: str, user_id: str) -> str:
        """
        API: Универсальный вызов ко всем LLM провайдерам через единый интерфейс
        Вход: model (конфиг модели), prompt (промпт), user_id (идентификатор)
        Выход: str (ответ модели)
        Логика: Определяет стратегию провайдера, строит запрос, парсит ответ
        """
        provider = model['api_provider']
        strategy = self._get_provider_strategy(provider)

        if not strategy:
            raise ValueError(f"Неизвестный провайдер: {provider}")

        # Построение запроса
        url, headers, data = self._build_api_request(strategy, model, prompt)

        # Выполнение HTTP запроса
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data, timeout=self.request_timeout) as response:
                response_text = await response.text()

                if response.status == 200:
                    # Успешный ответ - парсим
                    return self._parse_api_response(provider, response_text)
                else:
                    # Ошибка - классифицируем и выбрасываем исключение
                    raise self._handle_api_error(provider, response.status, response_text)

    def _get_provider_strategy(self, provider: str) -> Dict[str, Any]:
        """
        API: Получение конфигурации для конкретного провайдера
        Вход: provider (идентификатор провайдера)
        Выход: Dict (стратегия провайдера) или None если неизвестен
        Логика: Возвращает настройки endpoints, headers, форматы для каждого провайдера
        """
        strategies = {
            'openrouter': {
                'url': 'https://openrouter.ai/api/v1/chat/completions',
                'headers': {
                    'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://stark-ai.com',
                    'X-Title': 'Stark AI Assistant'
                },
                'body_template': {
                    'model': '{model_name}',
                    'messages': [{'role': 'user', 'content': '{prompt}'}],
                    'max_tokens': 1000,
                    'temperature': 0.7
                },
                'response_parser': 'openai_format'
            },
            'huggingface': {
                'url': 'https://api-inference.huggingface.co/models/{model_name}',
                'headers': {
                    'Authorization': f'Bearer {HUGGINGFACE_API_KEY}',
                    'Content-Type': 'application/json'
                },
                'body_template': {
                    'inputs': '{prompt}',
                    'parameters': {
                        'max_new_tokens': 1000,
                        'temperature': 0.7,
                        'return_full_text': False
                    }
                },
                'response_parser': 'huggingface_format'
            },
            'openai': {
                'url': 'https://api.openai.com/v1/chat/completions',
                'headers': {
                    'Authorization': f'Bearer {OPENAI_API_KEY}',
                    'Content-Type': 'application/json'
                },
                'body_template': {
                    'model': '{model_name}',
                    'messages': [{'role': 'user', 'content': '{prompt}'}],
                    'max_tokens': 1000,
                    'temperature': 0.7
                },
                'response_parser': 'openai_format'
            },
            'anthropic': {
                'url': 'https://api.anthropic.com/v1/messages',
                'headers': {
                    'x-api-key': ANTHROPIC_API_KEY,
                    'Content-Type': 'application/json',
                    'anthropic-version': '2023-06-01'
                },
                'body_template': {
                    'model': '{model_name}',
                    'max_tokens': 1000,
                    'temperature': 0.7,
                    'messages': [{'role': 'user', 'content': '{prompt}'}]
                },
                'response_parser': 'anthropic_format'
            },
            'google': {
                'url': 'https://generativelanguage.googleapis.com/v1/models/{model_name}:generateContent',
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body_template': {
                    'contents': [{
                        'parts': [{'text': '{prompt}'}]
                    }],
                    'generationConfig': {
                        'maxOutputTokens': 1000,
                        'temperature': 0.7
                    }
                },
                'response_parser': 'google_format',
                'params': {'key': GOOGLE_API_KEY}
            }
        }

        return strategies.get(provider)

    def _build_api_request(self, strategy: Dict[str, Any], model: Dict[str, Any], prompt: str) -> Tuple[
        str, Dict, Dict]:
        """
        API: Построение HTTP запроса для выбранного провайдера
        Вход: strategy (стратегия провайдера), model (конфиг модели), prompt (промпт)
        Выход: tuple (url, headers, data) - готовый HTTP запрос
        Логика: Заменяет плейсхолдеры в шаблонах, добавляет авторизацию
        """
        # Подготовка URL
        url = strategy['url'].format(model_name=model['name'])

        # Подготовка headers
        headers = strategy['headers'].copy()

        # Подготовка body данных
        import json
        body_template = json.dumps(strategy['body_template'])
        body_template = body_template.replace('{model_name}', model.get('model_name', model['name']))
        body_template = body_template.replace('{prompt}', prompt)
        data = json.loads(body_template)

        # Добавление параметров для Google API
        if strategy.get('params'):
            url += '?' + '&'.join([f'{k}={v}' for k, v in strategy['params'].items()])

        return url, headers, data

    def _parse_api_response(self, provider: str, response_text: str) -> str:
        """
        API: Парсинг ответа от LLM провайдера в единый формат
        Вход: provider (идентификатор провайдера), response_text (сырой ответ)
        Выход: str (текст ответа модели)
        Логика: Обработка различных форматов ответов провайдеров
        """
        try:
            response_data = json.loads(response_text)

            if provider in ['openrouter', 'openai']:
                # OpenAI-совместимый формат
                return response_data['choices'][0]['message']['content']

            elif provider == 'anthropic':
                # Anthropic формат
                return response_data['content'][0]['text']

            elif provider == 'huggingface':
                # HuggingFace формат
                if isinstance(response_data, list) and len(response_data) > 0:
                    if 'generated_text' in response_data[0]:
                        return response_data[0]['generated_text']
                    else:
                        return str(response_data[0])
                return str(response_data)

            elif provider == 'google':
                # Google AI формат
                return response_data['candidates'][0]['content']['parts'][0]['text']

            else:
                raise ValueError(f"Неизвестный формат ответа для провайдера: {provider}")

        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise ValueError(f"Ошибка парсинга ответа {provider}: {e}")

    def _handle_api_error(self, provider: str, status_code: int, response_text: str) -> Exception:
        """
        API: Обработка и классификация ошибок API провайдеров
        Вход: provider (провайдер), status_code (HTTP статус), response_text (текст ошибки)
        Выход: Exception (классифицированное исключение)
        Логика: Анализ статуса и текста ошибки для определения типа ограничения
        """
        error_message = f"{provider} API error {status_code}: {response_text}"

        if status_code == 429:
            return Exception(f"Rate limit exceeded for {provider}")
        elif status_code == 401:
            return Exception(f"Invalid API key for {provider}")
        elif status_code == 402:
            return Exception(f"Quota exceeded for {provider}")
        elif status_code == 503:
            return Exception(f"Service unavailable for {provider}")
        else:
            return Exception(error_message)

    async def _handle_api_limits(self, error_response: str, user_id: str) -> Optional[str]:
        """
        API: Обработка ограничений API и генерация пользовательских сообщений
        Вход: error_response (текст ошибки), user_id (идентификатор пользователя)
        Выход: str (сообщение пользователю) или None если не лимит
        Логика: Анализ текста ошибки для определения типа ограничения
        """
        error_lower = error_response.lower()

        if any(phrase in error_lower for phrase in ['rate limit', 'too many requests']):
            add_activity_log("WARNING", f"Rate limit обнаружен: {error_response}", user_id)
            return "⚠️ Превышено ограничение запросов. Попробуйте через 1-2 минуты."

        elif any(phrase in error_lower for phrase in ['quota', 'billing', 'daily']):
            add_activity_log("ERROR", f"Исчерпана квота API: {error_response}", user_id)
            return "⚠️ Исчерпан дневной лимит запросов. Лимит сбросится в 03:00 по МСК."

        elif any(phrase in error_lower for phrase in ['authentication', 'invalid api key']):
            add_activity_log("ERROR", f"Ошибка аутентификации API: {error_response}", user_id)
            return "⚠️ Ошибка доступа к API. Обратитесь к администратору."

        return None

    def _build_prompt(self, history: List[Dict]) -> str:
        """
        API: Построение промпта из истории диалога
        Вход: history (история сообщений)
        Выход: str (форматированный промпт)
        Логика: Конвертирует историю в формат, понятный моделям LLM
        """
        if not history:
            return "Привет! Чем могу помочь?"

        prompt = ""
        for msg in history:
            if msg["role"] == "user":
                prompt += f"Пользователь: {msg['content']}\n"
            else:
                prompt += f"Ассистент: {msg['content']}\n"

        prompt += "Ассистент: "
        return prompt

    async def _log_llm_request(self, user_id: str, provider: str, model: str, endpoint: str,
                               prompt_tokens: int = 0, completion_tokens: int = 0,
                               success: bool = True, error_type: str = None,
                               error_message: str = None, duration_ms: int = 0,
                               estimated_limits: int = None, process_type: str = "chat",
                               process_details: str = None):
        """
        API: Логирование запроса к LLM в базу данных
        Вход: user_id, provider, model, endpoint, токены, статус, ошибки, время выполнения, лимиты, тип процесса, детали процесса
        Выход: None (записывает в БД)
        Логика: Создает запись о запросе для анализа лимитов и мониторинга использования
        """
        try:
            # Если лимиты не указаны - оцениваем на основе успешности
            if estimated_limits is None:
                estimated_limits = 80 if success else 30

            request_id = create_llm_request(
                user_id=user_id,
                provider=provider,
                model=model,
                endpoint=endpoint,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                success=success,
                error_type=error_type,
                error_message=error_message,
                request_duration_ms=duration_ms,
                is_free_tier=True,
                estimated_limits_remaining=estimated_limits,
                process_type=process_type,
                process_details=process_details
            )

            add_activity_log("DEBUG", f"LLM запрос {provider}/{model} записан в БД", user_id)
            return request_id

        except Exception as e:
            add_activity_log("ERROR", f"Ошибка записи LLM запроса: {e}", user_id)

    def _estimate_tokens(self, text: str) -> int:
        """
        API: Примерная оценка количества токенов в тексте
        Вход: text (текст для оценки)
        Выход: int (примерное количество токенов)
        Логика: Простая эвристика - ~4 символа на токен для английского, ~2 для русского
        """
        if not text:
            return 0

        # Простая эвристика для оценки токенов
        russian_chars = sum(1 for c in text if 'а' <= c <= 'я' or 'А' <= c <= 'Я')
        english_chars = len(text) - russian_chars

        # ~4 символа на токен для английского, ~2 для русского
        estimated_tokens = (english_chars // 4) + (russian_chars // 2)
        return max(estimated_tokens, 1)

    def _extract_error_type(self, error: Exception) -> str:
        """
        API: Извлечение типа ошибки из исключения
        Вход: error (исключение)
        Выход: str (тип ошибки)
        Логика: Анализ текста ошибки для классификации типа ограничения
        """
        error_str = str(error).lower()

        if 'rate limit' in error_str or 'too many requests' in error_str:
            return 'rate_limit'
        elif 'quota' in error_str or 'billing' in error_str or 'daily' in error_str:
            return 'quota_exceeded'
        elif 'authentication' in error_str or 'invalid api key' in error_str:
            return 'authentication_error'
        elif 'timeout' in error_str:
            return 'timeout'
        elif 'network' in error_str or 'connection' in error_str:
            return 'network_error'
        else:
            return 'unknown_error'

    def _estimate_limits_remaining(self, error: Exception = None) -> int:
        """
        API: Оценка остатка лимитов на основе ошибки
        Вход: error (исключение или None)
        Выход: int (процент остатка лимитов: 100=полные, 0=исчерпаны)
        Логика: Анализ типа ошибки для оценки текущего состояния лимитов
        """
        if error is None:
            return 80

        error_type = self._extract_error_type(error)

        if error_type == 'rate_limit':
            return 10
        elif error_type == 'quota_exceeded':
            return 0
        elif error_type == 'authentication_error':
            return 100
        else:
            return 50

    async def _rate_limit_protection(self):
        """
        API: Защита от слишком частых запросов
        Вход: None
        Выход: None
        Логика: Добавляет задержку между запросами для избежания rate limits
        """
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()

    def get_conversation_history(self, user_id: str) -> List[Dict]:
        """
        API: Получение истории диалога пользователя
        Вход: user_id (идентификатор пользователя)
        Выход: List[Dict] (история сообщений)
        Логика: Возвращает сохраненную историю или пустой список
        """
        return self.conversations.get(user_id, [])

    def clear_conversation_history(self, user_id: str) -> bool:
        """
        API: Очистка истории диалога пользователя
        Вход: user_id (идентификатор пользователя)
        Выход: bool (успех операции)
        Логика: Удаляет историю диалога из кэша
        """
        if user_id in self.conversations:
            del self.conversations[user_id]
            add_activity_log("INFO", f"История диалога очищена для {user_id}", user_id)
            return True
        return False

    def get_active_users(self) -> List[str]:
        """
        API: Получение списка активных пользователей
        Вход: None
        Выход: List[str] (список идентификаторов)
        Логика: Возвращает ключи словаря conversations
        """
        return list(self.conversations.keys())

    def get_usage_statistics(self) -> Dict[str, Any]:
        """
        API: Получение статистики использования агента
        Вход: None
        Выход: Dict (метрики использования)
        Логика: Сбор основных метрик для мониторинга
        """
        return {
            "active_users": len(self.conversations),
            "total_conversations": sum(len(conv) for conv in self.conversations.values()),
            "models_available": len(MODEL_RANKING),
            "max_history_length": self.max_history
        }


# Глобальный экземпляр агента для использования в других модулях
ai_agent = AIAgent()


async def test_agent():
    """
    API: Тестирование функциональности AI Agent
    Вход: None
    Выход: bool (результат тестирования)
    Логика: Проверка основных функций агента на тестовых сообщениях
    """
    agent = AIAgent()
    test_messages = [
        "Привет!",
        "Как дела?",
        "Расскажи о себе"
    ]

    try:
        for msg in test_messages:
            response = await agent.process_message("test_user", msg, "test")
            print(f"Вопрос: {msg}")
            print(f"Ответ: {response}")
            print("-" * 50)

        add_activity_log("INFO", "Тестирование агента завершено успешно", "system")
        return True
    except Exception as e:
        add_activity_log("ERROR", f"Ошибка тестирования агента: {e}", "system")
        return False


if __name__ == "__main__":
    """
    Точка входа для прямого запуска агента
    """
    asyncio.run(test_agent())
