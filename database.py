# database.py
"""
Database Module - система хранения логов и задач модификации кода
API: Управление базой данных PostgreSQL, CRUD операции для логов и задач
Основные возможности: автоматическое логирование, отслеживание задач модификации кода
"""

from sqlalchemy import create_engine, Column, String, DateTime, Text, Boolean, Integer, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
from datetime import timedelta
import uuid

Base = declarative_base()


class LogEntry(Base):
    """
    API: Модель записи лога в системе
    Вход: None (создается через конструктор)
    Выход: None (хранит данные лога)
    Логика: Автоматически генерирует ID и timestamp при создании
    """
    __tablename__ = 'logs'
    __table_args__ = (
        Index('idx_logs_timestamp', 'timestamp'),
        Index('idx_logs_level', 'level'),
        Index('idx_logs_user_id', 'user_id'),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    level = Column(String)  # INFO, ERROR, DEBUG, WARNING
    message = Column(Text)
    user_id = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Log({self.level}) {self.message[:50]}...>"


class ModificationTask(Base):
    """
    API: Модель задачи модификации кода с иерархической структурой
    Вход: None (создается через конструктор)
    Выход: None (хранит данные задачи модификации)
    Логика: Поддерживает родительские/дочерние задачи, управление разрешениями, отслеживание статусов
    """
    __tablename__ = 'modification_tasks'
    __table_args__ = (
        Index('idx_tasks_status', 'status'),
        Index('idx_tasks_created', 'created_at'),
        Index('idx_tasks_level', 'level'),
        Index('idx_tasks_parent', 'parent_id'),
    )

    # Идентификаторы
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_id = Column(String(36), nullable=True)  # ID родительской задачи

    # Данные модификации
    file = Column(String, nullable=False)  # Файл для изменения
    asis = Column(Text, nullable=True)  # Старый код (None = добавить tobe)
    tobe = Column(Text, nullable=True)  # Новый код (None = удалить asis)
    desc = Column(Text, nullable=False)  # Описание изменения

    # Управление доступом
    level = Column(String, default="dev")  # dev (разработчик) или agent (система)
    perm = Column(String, default="false")  # Разрешение разработчика: true/false

    # Статусы
    status = Column(String, default="new")  # new, hold, ready, done
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))  # Время создания
    completed_dt = Column(DateTime, nullable=True)  # Время реализации
    error_message = Column(Text, nullable=True)  # Лог ошибки

    def __repr__(self):
        return f"<ModificationTask({self.status}) {self.file}>"


class LLMRequest(Base):
    """
    API: Модель запроса к LLM провайдеру
    Вход: None (создается через конструктор)
    Выход: None (хранит данные запроса к LLM)
    Логика: Трекинг использования лимитов, мониторинг ошибок и распределения запросов
    """
    __tablename__ = 'llm_requests'
    __table_args__ = (
        Index('idx_llm_timestamp', 'timestamp'),
        Index('idx_llm_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_llm_provider_success', 'provider', 'success'),
        Index('idx_llm_process_type', 'process_type'),
        Index('idx_llm_error_type', 'error_type'),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String)  # Кто сделал запрос
    provider = Column(String, nullable=False)  # openai, anthropic, google, openrouter
    model = Column(String, nullable=False)  # gpt-4, claude-3-opus, gemini-pro
    endpoint = Column(String, nullable=False)  # web, telegram, api, terminal
    prompt_tokens = Column(Integer, default=0)  # Токены промпта
    completion_tokens = Column(Integer, default=0)  # Токены ответа
    total_tokens = Column(Integer, default=0)  # Всего токенов
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))  # Время запроса
    success = Column(Boolean, default=True)  # Успешен ли запрос
    error_type = Column(String)  # rate_limit, quota_exceeded, etc
    error_message = Column(Text)  # Детальное сообщение об ошибке
    request_duration_ms = Column(Integer)  # Время выполнения
    retry_count = Column(Integer, default=0)  # Количество повторных попыток
    is_free_tier = Column(Boolean, default=True)  # Бесплатный ли тариф
    estimated_limits_remaining = Column(Integer)  # Остаток лимитов в %
    process_type = Column(String)  # Тип процесса
    process_details = Column(Text)  # Детали процесса

    def __repr__(self):
        return f"<LLMRequest({self.provider}/{self.model}) {self.user_id} - {self.process_type}>"


# Подключение к БД
DATABASE_URL = "postgresql://developer:dev123@localhost:5432/stark_ai"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """
    API: Инициализация базы данных
    Вход: None
    Выход: None (создает таблицы в БД)
    Логика: Создает все таблицы определенные в Base.metadata
    """
    Base.metadata.create_all(bind=engine)
    print("✅ Таблицы созданы!")


def get_db():
    """
    API: Получение сессии базы данных
    Вход: None
    Выход: Generator[Session, None, None] (генератор сессий)
    Логика: Создает новую сессию для каждого запроса, автоматически закрывает
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def add_activity_log(level: str, message: str, user_id: str = None):
    """
    API: Добавление записи в лог активности
    Вход: level (уровень логирования), message (сообщение), user_id (ID пользователя)
    Выход: str (ID созданной записи лога) или None при ошибке
    Логика: Создает запись лога с автоматическим timestamp и ID
    """
    db = SessionLocal()
    try:
        log = LogEntry(level=level, message=message, user_id=user_id)
        db.add(log)
        db.commit()
        print(f"📝 LOG [{level}]: {message}")
        return log.id
    except Exception as e:
        print(f"❌ Ошибка записи лога: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def get_recent_logs(limit: int = 10):
    """
    API: Получение последних записей лога
    Вход: limit (количество записей, по умолчанию 10)
    Выход: List[LogEntry] (список объектов лога)
    Логика: Возвращает записи отсортированные по времени (новые сначала)
    """
    db = SessionLocal()
    try:
        logs = db.query(LogEntry).order_by(LogEntry.timestamp.desc()).limit(limit).all()
        return logs
    finally:
        db.close()


def create_modification_task(
        file: str,
        desc: str,
        asis: str = None,
        tobe: str = None,
        parent_id: str = None,
        level: str = "dev"
) -> str:
    """
    API: Создание новой задачи модификации кода
    Вход: file (путь к файлу), desc (описание), asis (старый код), tobe (новый код),
          parent_id (ID родительской задачи), level (уровень доступа)
    Выход: str (ID созданной задачи)
    Логика: Создает задачу с указанными параметрами, автоматически устанавливает статус 'new'
    """
    db = SessionLocal()
    try:
        task = ModificationTask(
            file=file,
            desc=desc,
            asis=asis,
            tobe=tobe,
            parent_id=parent_id,
            level=level
        )
        db.add(task)
        db.commit()
        add_activity_log("INFO", f"Создана задача модификации: {file} ({desc[:50]}...)", "system")
        return task.id
    except Exception as e:
        add_activity_log("ERROR", f"Ошибка создания задачи: {e}", "system")
        db.rollback()
        raise
    finally:
        db.close()


def update_task_status(task_id: str, status: str, error_message: str = None, perm: str = None):
    """
    API: Обновление статуса задачи модификации
    Вход: task_id (ID задачи), status (новый статус), error_message (сообщение об ошибке),
          perm (разрешение разработчика)
    Выход: None
    Логика: Обновляет статус задачи, устанавливает completed_dt для статуса 'done'
    """
    db = SessionLocal()
    try:
        task = db.query(ModificationTask).filter(ModificationTask.id == task_id).first()
        if task:
            task.status = status
            if status == "done":
                task.completed_dt = datetime.now(timezone.utc)
            if error_message is not None:
                task.error_message = error_message
            if perm is not None:
                task.perm = perm
            db.commit()
            add_activity_log("INFO", f"Задача {task_id} обновлена: {status}", "system")
    except Exception as e:
        add_activity_log("ERROR", f"Ошибка обновления задачи: {e}", "system")
        db.rollback()
    finally:
        db.close()


def get_recent_tasks(limit: int = 10):
    """
    API: Получение последних задач модификации
    Вход: limit (количество задач, по умолчанию 10)
    Выход: List[ModificationTask] (список объектов задач)
    Логика: Возвращает задачи отсортированные по времени создания (новые сначала)
    """
    db = SessionLocal()
    try:
        tasks = db.query(ModificationTask).order_by(ModificationTask.created_at.desc()).limit(limit).all()
        return tasks
    finally:
        db.close()


def grant_permission(task_id: str):
    """
    API: Выдача разрешения разработчика на задачу
    Вход: task_id (ID задачи)
    Выход: None
    Логика: Устанавливает perm='true' для задачи уровня 'dev'
    """
    db = SessionLocal()
    try:
        task = db.query(ModificationTask).filter(ModificationTask.id == task_id).first()
        if task and task.level == "dev":
            task.perm = "true"
            db.commit()
            add_activity_log("INFO", f"Выдано разрешение для задачи: {task_id}", "system")
    except Exception as e:
        add_activity_log("ERROR", f"Ошибка выдачи разрешения: {e}", "system")
        db.rollback()
    finally:
        db.close()


def get_child_tasks(parent_id: str):
    """
    API: Получение дочерних задач
    Вход: parent_id (ID родительской задачи)
    Выход: List[ModificationTask] (список дочерних задач)
    Логика: Возвращает все задачи с указанным parent_id
    """
    db = SessionLocal()
    try:
        tasks = db.query(ModificationTask).filter(ModificationTask.parent_id == parent_id).all()
        return tasks
    finally:
        db.close()


def get_ready_tasks():
    """
    API: Получение задач готовых к внедрению
    Вход: None
    Выход: List[ModificationTask] (список задач со статусом 'ready')
    Логика: Возвращает задачи с status='ready' и (level='agent' или perm='true')
    """
    db = SessionLocal()
    try:
        tasks = db.query(ModificationTask).filter(
            ModificationTask.status == "ready"
        ).filter(
            (ModificationTask.level == "agent") | (ModificationTask.perm == "true")
        ).all()
        return tasks
    finally:
        db.close()


def create_llm_request(
        user_id: str,
        provider: str,
        model: str,
        endpoint: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        success: bool = True,
        error_type: str = None,
        error_message: str = None,
        request_duration_ms: int = 0,
        retry_count: int = 0,
        is_free_tier: bool = True,
        estimated_limits_remaining: int = 100,
        process_type: str = None,
        process_details: str = None
) -> str:
    """
    API: Создание записи о запросе к LLM
    Вход: все параметры запроса (пользователь, провайдер, модель, токены, статус, ошибки)
    Выход: str (ID созданной записи)
    Логика: Сохранение детальной информации о каждом запросе для анализа лимитов
    """
    db = SessionLocal()
    try:
        request = LLMRequest(
            user_id=user_id,
            provider=provider,
            model=model,
            endpoint=endpoint,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            success=success,
            error_type=error_type,
            error_message=error_message,
            request_duration_ms=request_duration_ms,
            retry_count=retry_count,
            is_free_tier=is_free_tier,
            estimated_limits_remaining=estimated_limits_remaining,
            process_type=process_type,
            process_details=process_details
        )
        db.add(request)
        db.commit()
        add_activity_log("DEBUG", f"LLM запрос записан: {provider}/{model}", user_id)
        return request.id
    except Exception as e:
        add_activity_log("ERROR", f"Ошибка записи LLM запроса: {e}", user_id)
        db.rollback()
        raise
    finally:
        db.close()


def get_recent_llm_requests(limit: int = 10):
    """
    API: Получение последних запросов к LLM
    Вход: limit (количество записей)
    Выход: List[LLMRequest] (список объектов запросов)
    Логика: Возвращает последние запросы отсортированные по времени (новые сначала)
    """
    db = SessionLocal()
    try:
        requests = db.query(LLMRequest).order_by(LLMRequest.timestamp.desc()).limit(limit).all()
        return requests
    finally:
        db.close()


def get_provider_limits_status(provider: str = None):
    """
    API: Получение статуса лимитов провайдеров
    Вход: provider (опционально - конкретный провайдер)
    Выход: Dict (статистика по лимитам)
    Логика: Анализ использования лимитов за последние 24 часа
    """
    db = SessionLocal()
    try:
        from sqlalchemy import func, case

        # Анализ за последние 24 часа вместо текущего дня
        time_threshold = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)

        query = db.query(
            LLMRequest.provider,
            func.count().label('total_requests'),
            func.count(case([(LLMRequest.success == True, 1)])).label('successful_requests'),
            func.count(case([(LLMRequest.error_type == 'rate_limit', 1)])).label('rate_limit_errors'),
            func.avg(LLMRequest.estimated_limits_remaining).label('avg_limits_remaining')
        )

        if provider:
            query = query.filter(LLMRequest.provider == provider)

        query = query.filter(LLMRequest.timestamp >= time_threshold)
        query = query.group_by(LLMRequest.provider)

        results = query.all()

        limits_status = {}
        for result in results:
            limits_status[result.provider] = {
                'total_requests': result.total_requests,
                'successful_requests': result.successful_requests,
                'rate_limit_errors': result.rate_limit_errors,
                'avg_limits_remaining': round(result.avg_limits_remaining or 100),
                'health': 'HEALTHY' if (result.avg_limits_remaining or 100) > 80 else
                'WARNING' if (result.avg_limits_remaining or 100) > 50 else 'CRITICAL'
            }

        return limits_status

    except Exception as e:
        logger.error(f"Error getting provider limits: {e}")
        return {}
    finally:
        db.close()


# Настройка логирования для модуля
import logging

logger = logging.getLogger(__name__)