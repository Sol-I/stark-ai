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
import re
import json

# Конфигурация системы
from config import (
    OPENROUTER_API_KEY,
    DEEPSEEK_API_KEY,
    MAX_HISTORY_LENGTH,
    REQUEST_TIMEOUT,
    API_STRATEGIES,
    API_ENDPOINTS
)

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AIAgent:
    """
    AI Agent - основной класс обработки запросов к LLM провайдерам
    API: Управление диалогами, ротация моделей, мониторинг лимитов, логирование операций
    Основные возможности: отказоустойчивость, многомодельность, трекинг использования, аналитика
    """

    def __init__(self, log_callback=None, llm_request_callback=None):
        """
        API: Инициализация AI Agent
        Вход: log_callback (функция логирования), llm_request_callback (функция записи LLM запросов)
        Выход: None (создает экземпляр агента)
        Логика: Инициализация кэшей, истории диалогов, метрик использования
        """
        self.conversations: Dict[str, List[Dict]] = {}
        self.model_ranking: List[Dict] = []
        self.initialized = False
        self.initialization_lock = asyncio.Lock()
        self.max_history = MAX_HISTORY_LENGTH or 10
        self.request_timeout = REQUEST_TIMEOUT or 30
        self.last_request_time = 0
        self.min_request_interval = 0.1

        # Callbacks для логирования
        self.add_activity_log = log_callback or (lambda level, msg, user=None: print(f"[{level}] {msg}"))
        self.create_llm_request = llm_request_callback or (lambda **kwargs: print(f"LLM Request: {kwargs}"))

        self.add_activity_log("INFO", "AI Agent инициализирован (ленивая загрузка моделей)", "system")
        logger.info("AI Agent initialized with lazy model loading")

    async def ensure_initialized(self):
        """
        API: Гарантирует что модели загружены и ранжированы
        Вход: None
        Выход: None
        Логика: Ленивая загрузка моделей при первом вызове, защита от гонок
        """
        if not self.initialized:
            async with self.initialization_lock:
                if not self.initialized:  # Double-check
                    await self._load_free_models_ranking()
                    self.initialized = True
                    logger.info(f"Модели загружены: {len(self.model_ranking)} шт")

    async def _load_free_models_ranking(self):
        """С отладкой"""
        try:
            self.add_activity_log("INFO", "Начало загрузки моделей из OpenRouter", "system")

            models = await self._fetch_models_from_openrouter()
            logger.info(f"Получено {len(models)} моделей из API")

            # Отладка: покажем первые 3 модели
            for i, model in enumerate(models[:3]):
                logger.debug(f"Модель {i}: {model.get('id')} - pricing: {model.get('pricing')}")

            if not models:
                raise Exception("Не удалось загрузить модели из OpenRouter")

            free_models = self._filter_free_models(models)
            logger.info(f"После фильтрации: {len(free_models)} моделей")

            if not free_models:
                # Покажем почему не прошли фильтрацию
                for model in models[:5]:
                    pricing = model.get('pricing', {})
                    logger.debug(
                        f"Модель {model.get('id')}: prompt={pricing.get('prompt')}, completion={pricing.get('completion')}")
                raise Exception("Не найдено бесплатных моделей")

            self.model_ranking = self._rank_models_by_parameters(free_models)

            self.add_activity_log("INFO", f"Загружено {len(self.model_ranking)} бесплатных моделей", "system")
            logger.info(f"Топ-3 модели: {[m['name'] for m in self.model_ranking[:3]]}")

        except Exception as e:
            error_msg = f"Ошибка загрузки моделей: {e}"
            self.add_activity_log("ERROR", error_msg, "system")
            logger.error(error_msg)
            self.model_ranking = self._get_fallback_models()

    async def _fetch_models_from_openrouter(self) -> List[Dict]:
        """
        API: Получение списка моделей из OpenRouter API
        Вход: None
        Выход: List[Dict] (список моделей)
        Логика: HTTP запрос к /api/v1/models, парсинг JSON ответа
        """
        url = "https://openrouter.ai/api/v1/models"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('data', [])
                    else:
                        raise Exception(f"HTTP {response.status}: {await response.text()}")
        except Exception as e:
            logger.error(f"Ошибка получения моделей: {e}")
            return []

    def _filter_free_models(self, models: List[Dict]) -> List[Dict]:
        """Фильтрация бесплатных моделей - более гибкая"""
        free_models = []
        for model in models:
            try:
                pricing = model.get('pricing', {})

                # Более гибкая проверка бесплатности
                is_free = (
                        pricing.get('prompt') == "0" or
                        pricing.get('prompt') == 0 or
                        pricing.get('prompt') is None
                )

                # Активные модели с описанием
                is_active = model.get('active', False) or True  # Многие модели без active флага
                has_description = bool(model.get('description'))

                if is_free and has_description:
                    free_models.append(model)

            except Exception as e:
                logger.debug(f"Ошибка проверки модели {model.get('id')}: {e}")
                continue

        logger.info(f"Найдено {len(free_models)} бесплатных моделей из {len(models)}")
        return free_models

    def _rank_models_by_parameters(self, models: List[Dict]) -> List[Dict]:
        """
        API: Ранжирование моделей по мощности (параметрам)
        Вход: models (список бесплатных моделей)
        Выход: List[Dict] (отсортированные модели)
        Логика: Сортировка по убыванию параметров, затем по другим критериям
        """
        def get_model_parameters(model: Dict) -> int:
            """Извлекает количество параметров модели"""
            # Пробуем разные поля где могут быть параметры
            description = model.get('description', '').lower()
            context_length = model.get('context_length', 0)

            # Ищем числа с суффиксами параметров
            param_patterns = [
                r'(\d+)b\b',  # 7b, 13b, 70b
                r'(\d+)b\s+parameters',  # 7b parameters
                r'(\d+)\s+billion',  # 7 billion
            ]

            for pattern in param_patterns:
                match = re.search(pattern, description)
                if match:
                    return int(match.group(1)) * 1_000_000_000  # Конвертируем в числа

            # Фолбэк на context_length
            return context_length

        def get_model_score(model: Dict) -> Tuple[int, int, int]:
            """Создает кортеж для сортировки: параметры, контекст, приоритет"""
            params = get_model_parameters(model)
            context = model.get('context_length', 0)
            # Приоритет по провайдеру (deepseek > другие)
            provider_priority = 2 if 'deepseek' in model.get('id', '').lower() else 1
            return (params, context, provider_priority)

        # Сортируем по убыванию мощности
        sorted_models = sorted(models, key=get_model_score, reverse=True)

        # Конвертируем в формат для agent_core
        ranked_models = []
        for model in sorted_models:
            ranked_models.append({
                'name': model['id'],
                'api_provider': 'openrouter',  # Все из OpenRouter
                'model_name': model['id'],
                'description': model.get('description', ''),
                'context_length': model.get('context_length', 0)
            })

        return ranked_models

    def _get_fallback_models(self) -> List[Dict]:
        """Рабочие резервные модели"""
        logger.warning("Используются резервные модели")
        return [
            {
                'name': 'deepseek/deepseek-chat',
                'api_provider': 'deepseek',  # ✅ Правильный провайдер
                'model_name': 'deepseek-chat',
                'description': 'DeepSeek Chat (67B) - резервная модель',
                'context_length': 8192
            },
            {
                'name': 'google/gemma-7b-it',
                'api_provider': 'openrouter',
                'model_name': 'google/gemma-7b-it',
                'description': 'Google Gemma 7B - резервная модель',
                'context_length': 8192
            }
        ]

    async def process_message(self, user_id: str, message: str, endpoint: str = "unknown",
                              process_type: str = "chat",
                              process_details: str = None) -> str:
        """
        API: Основной метод обработки сообщений пользователя
        Вход: user_id (идентификатор сессии), message (текст сообщения), endpoint (источник запроса), process_type (тип процесса), process_details (детали)
        Выход: str (ответ ИИ или сообщение об ошибке)
        Логика: Последовательно пробует модели из model_ranking, логирует все операции в БД
        """
        try:
            # Ленивая загрузка моделей при первом вызове
            await self.ensure_initialized()

            self.add_activity_log("INFO", f"Получено сообщение через {endpoint}: '{message[:100]}...'", user_id)

            # Защита от слишком частых запросов
            await self._rate_limit_protection()

            # Инициализация сессии пользователя
            if user_id not in self.conversations:
                self.conversations[user_id] = []
                self.add_activity_log("DEBUG", f"Создана новая сессия пользователя", user_id)

            # Обновление истории диалога
            current_history = self.conversations[user_id][-self.max_history:]
            current_history.append({"role": "user", "content": message})

            # Последовательная попытка моделей по приоритету
            for model_index, model in enumerate(self.model_ranking):
                model_info = f"{model['name']} ({model['api_provider']})"
                self.add_activity_log("DEBUG", f"Попытка #{model_index + 1}: {model_info}", user_id)

                response, success, prompt_tokens, completion_tokens = await self._try_model_request(
                    model, current_history, user_id, endpoint, process_type, process_details
                )

                if success:
                    # Успешный ответ - сохраняем историю и возвращаем результат
                    current_history.append({"role": "assistant", "content": response})
                    self.conversations[user_id] = current_history[-self.max_history:]
                    self.add_activity_log("INFO", f"Успешный ответ от {model_info}", user_id)
                    return response
                else:
                    # Продолжаем ротацию при ошибках
                    self.add_activity_log("INFO", f"Модель {model_info} недоступна", user_id)
                    continue

            # Все модели недоступны
            error_msg = "❌ Все модели временно недоступны. Попробуйте позже."
            self.add_activity_log("ERROR", "Все модели в ротации недоступны", user_id)
            return error_msg

        except Exception as e:
            error_msg = f"❌ Системная ошибка обработки сообщения: {str(e)}"
            self.add_activity_log("ERROR", f"Критическая ошибка process_message: {e}", user_id)
            return error_msg

    async def _try_model_request(self, model: Dict[str, Any], history: List[Dict],
                                 user_id: str, endpoint: str,
                                 process_type: str = "chat", process_details: str = None) -> Tuple[str, bool, int, int]:
        """
        API: Попытка запроса к конкретной модели с полным логированием
        Вход: model (конфиг модели), history (история диалога), user_id (идентификатор),
              endpoint (источник), process_type (тип процесса), process_details (детали процесса)
        Выход: tuple (response, success, prompt_tokens, completion_tokens) - ответ, статус и токены
        Логика: Выполняет запрос к API с трекингом токенов, времени и ошибок
        """
        start_time = time.time()
        prompt = self._build_prompt(history)

        try:
            self.add_activity_log("DEBUG", f"Запрос к {model['name']}", user_id)

            # Универсальный вызов API
            response, prompt_tokens, completion_tokens = await self._call_universal_api(model, prompt, user_id)

            # Обработка успешного ответа
            if response and response.strip():
                duration_ms = int((time.time() - start_time) * 1000)

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

                self.add_activity_log("INFO", f"Успешный ответ ({len(response)} символов)", user_id)
                return response, True, prompt_tokens, completion_tokens
            else:
                # Пустой ответ
                self.add_activity_log("WARNING", f"Пустой ответ от модели", user_id)
                return "Пустой ответ от модели", False, 0, 0

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_type = self._extract_error_type(e)
            estimated_limits = self._estimate_limits_remaining(e)

            await self._log_llm_request(
                user_id=user_id,
                provider=model['api_provider'],
                model=model['name'],
                endpoint=endpoint,
                prompt_tokens=self._estimate_tokens_fallback(prompt),
                success=False,
                error_type=error_type,
                error_message=f"API error: {str(e)}",
                duration_ms=duration_ms,
                estimated_limits=estimated_limits,
                process_type=process_type,
                process_details=process_details
            )

            return f"Ошибка API: {str(e)}", False, 0, 0

    async def _call_universal_api(self, model: Dict[str, Any], prompt: str, user_id: str) -> Tuple[str, int, int]:
        """
        API: Универсальный вызов ко всем LLM провайдерам через единый интерфейс
        Вход: model (конфиг модели), prompt (промпт), user_id (идентификатор)
        Выход: tuple (ответ, prompt_tokens, completion_tokens)
        Логика: Определяет стратегию провайдера, строит запрос, парсит ответ с токенами
        """
        provider = model['api_provider']
        strategy = self._get_provider_strategy(provider)

        if not strategy:
            raise ValueError(f"Неизвестный провайдер: {provider}")

        # Построение запроса
        url, headers, data = self._build_api_request(strategy, model, prompt)

        try:
            # Выполнение HTTP запроса
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data, timeout=self.request_timeout) as response:
                    response_text = await response.text()

                    if response.status == 200:
                        # Успешный ответ - парсим с токенами
                        return self._parse_api_response_with_tokens(provider, response_text)
                    else:
                        # Ошибка - классифицируем и выбрасываем исключение
                        raise self._handle_api_error(provider, response.status, response_text)

        except Exception as e:
            logger.error(f"HTTP запрос к {provider} провал: {e}")
            raise

    def _get_provider_strategy(self, provider: str) -> Dict[str, Any]:
        """
        API: Получение конфигурации для конкретного провайдера
        Вход: provider (идентификатор провайдера)
        Выход: Dict (стратегия провайдера) или None если неизвестен
        """
        return API_STRATEGIES.get(provider)

    def _build_api_request(self, strategy: Dict[str, Any], model: Dict[str, Any], prompt: str) -> Tuple[str, Dict, Dict]:
        """
        API: Построение HTTP запроса для выбранного провайдера
        Вход: strategy (стратегия провайдера), model (конфиг модели), prompt (промпт)
        Выход: tuple (url, headers, data) - готовый HTTP запрос
        Логика: Заменяет плейсхолдеры в шаблонах, добавляет авторизацию
        """
        try:
            # Получаем endpoint для провайдера
            endpoint = API_ENDPOINTS.get(model['api_provider'], '')

            # Подготовка URL с подстановкой endpoint
            url = strategy['url'].format(endpoint=endpoint, model_name=model['name'])

            # Подготовка headers с подстановкой API ключа
            headers = {}
            for key, value in strategy['headers'].items():
                if '{api_key}' in value:
                    api_key = ""
                    if model['api_provider'] == 'openrouter':
                        api_key = OPENROUTER_API_KEY
                    elif model['api_provider'] == 'deepseek':
                        api_key = DEEPSEEK_API_KEY
                    headers[key] = value.format(api_key=api_key)
                else:
                    headers[key] = value

            # Подготовка тела запроса
            escaped_prompt = json.dumps(prompt)[1:-1]  # Убираем кавычки json.dumps

            body_template = json.dumps(strategy['body_template'])
            body_template = body_template.replace('{model_name}', model.get('model_name', model['name']))
            body_template = body_template.replace('{prompt}', escaped_prompt)
            data = json.loads(body_template)

            return url, headers, data

        except Exception as e:
            logger.error(f"Ошибка построения API запроса: {e}")
            raise

    def _parse_api_response_with_tokens(self, provider: str, response_text: str) -> Tuple[str, int, int]:
        """
        API: Парсинг ответа от LLM провайдера с извлечением токенов
        Вход: provider (идентификатор провайдера), response_text (сырой ответ)
        Выход: tuple (текст ответа, prompt_tokens, completion_tokens)
        Логика: Обработка различных форматов ответов провайдеров с извлечением usage данных
        """
        try:
            response_data = json.loads(response_text)
            prompt_tokens = 0
            completion_tokens = 0

            if provider in ['openrouter', 'deepseek']:
                # OpenAI-совместимый формат
                text = response_data['choices'][0]['message']['content']
                if 'usage' in response_data:
                    prompt_tokens = response_data['usage'].get('prompt_tokens', 0)
                    completion_tokens = response_data['usage'].get('completion_tokens', 0)
                return text, prompt_tokens, completion_tokens

            else:
                # Для других провайдеров - базовая обработка
                text = self._parse_api_response(provider, response_text)
                prompt_tokens = self._estimate_tokens_fallback(text)
                return text, prompt_tokens, 0

        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise ValueError(f"Ошибка парсинга ответа {provider}: {e}")

    def _parse_api_response(self, provider: str, response_text: str) -> str:
        """
        API: Парсинг ответа от LLM провайдера в единый формат (базовая версия)
        Вход: provider (идентификатор провайдера), response_text (сырой ответ)
        Выход: str (текст ответа модели)
        """
        try:
            response_data = json.loads(response_text)

            if provider in ['openrouter', 'deepseek']:
                return response_data['choices'][0]['message']['content']
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

            request_id = self.create_llm_request(
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

            logger.debug(f"LLM запрос {provider}/{model} записан в БД")
            return request_id

        except Exception as e:
            logger.error(f"Ошибка записи LLM запроса: {e}")

    def _estimate_tokens_fallback(self, text: str) -> int:
        """
        API: Фолбэк оценка токенов когда данные от API недоступны
        Вход: text (текст для оценки)
        Выход: int (примерное количество токенов)
        Логика: Упрощенная эвристика для случаев когда API не возвращает usage
        """
        if not text:
            return 0
        # Более простая и консервативная оценка
        return max(len(text) // 3, 1)

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
            self.add_activity_log("INFO", f"История диалога очищена для {user_id}", user_id)
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
            "models_available": len(self.model_ranking),
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
    await agent.ensure_initialized()  # Явная инициализация для теста

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

        return True
    except Exception as e:
        return False


if __name__ == "__main__":
    """
    Точка входа для прямого запуска агента
    """
    asyncio.run(test_agent())