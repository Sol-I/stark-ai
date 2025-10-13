# main.py
"""
Stark AI Agent - главная точка входа системы
API: Запуск и координация всех компонентов Stark AI (веб-сервер, Telegram бот, AI ядро)
Основные возможности: многопоточный запуск сервисов, управление жизненным циклом, мониторинг состояния
"""

import asyncio
import threading
import time
import logging
from datetime import datetime

# Импорт системы логирования
try:
    from database import add_activity_log
except ImportError:
    def add_activity_log(level: str, message: str, user_id: str = None):
        print(f"📝 [{level}] {message} (user: {user_id})")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def start_server():
    """
    API: Запуск FastAPI сервера в отдельном потоке
    Вход: None
    Выход: None (блокирующий вызов в потоке)
    Логика: Импорт и запуск веб-сервера с обработкой ошибок
    """
    try:
        from server import run_server
        add_activity_log("INFO", "Запуск FastAPI сервера...", "system")
        logger.info("🚀 Starting FastAPI server...")
        run_server(host="0.0.0.0", port=8000)
    except ImportError as e:
        error_msg = f"Ошибка импорта сервера: {e}"
        add_activity_log("ERROR", error_msg, "system")
        logger.error(error_msg)
    except Exception as e:
        error_msg = f"Ошибка сервера: {e}"
        add_activity_log("ERROR", error_msg, "system")
        logger.error(error_msg)


def start_telegram_bot():
    def start_telegram_bot():
        """
        API: Запуск Telegram бота в отдельном потоке
        Вход: None
        Выход: None (блокирующий вызов в потоке)
        Логика: Импорт и запуск Telegram бота с обработкой ошибок
        """
        try:
            from telegram_bot import TelegramBot
            add_activity_log("INFO", "Запуск Telegram бота...", "system")
            logger.info("🤖 Starting Telegram bot...")
            bot = TelegramBot()
            bot.run()  # Синхронный запуск polling
        except Exception as e:
            error_msg = f"Ошибка Telegram бота: {e}"
            add_activity_log("ERROR", error_msg, "system")
            logger.error(error_msg)

async def monitor_services():
    """
    API: Мониторинг состояния сервисов
    Вход: None
    Выход: None (периодическая проверка)
    Логика: Проверка активности потоков сервера и бота, логирование состояния
    """
    while True:
        try:
            active_threads = threading.enumerate()
            server_active = any('server' in str(t).lower() for t in active_threads)
            telegram_active = any('telegram' in str(t).lower() for t in active_threads)

            status_msg = f"Мониторинг: Сервер {'✅' if server_active else '❌'}, Telegram {'✅' if telegram_active else '❌'}"

            if not server_active or not telegram_active:
                add_activity_log("WARNING", status_msg, "system")
            else:
                add_activity_log("DEBUG", status_msg, "system")

            await asyncio.sleep(60)  # Проверка каждую минуту

        except Exception as e:
            error_msg = f"Ошибка мониторинга: {e}"
            add_activity_log("ERROR", error_msg, "system")
            logger.error(error_msg)
            await asyncio.sleep(30)


async def main():
    """
    API: Основная функция запуска Stark AI Agent
    Вход: None
    Выход: None (асинхронный запуск)
    Логика: Инициализация компонентов, запуск сервисов в потоках, управление жизненным циклом
    """
    add_activity_log("INFO", "Запуск Stark AI Agent", "system")
    logger.info("🎯 Stark AI Agent запускается...")

    print("=" * 60)
    print("🚀 STARK AI AGENT - MULTI-INTERFACE AI ASSISTANT")
    print("=" * 60)

    # Показываем информацию о системе
    try:
        from config import MODEL_RANKING
        logger.info("📊 Доступные модели AI:")
        for i, model in enumerate(MODEL_RANKING[:5], 1):
            status = "✅" if i == 1 else "🟡"
            model_info = f"{status} {i}. {model.get('name', 'Unknown')} - {model.get('api_provider', 'Unknown')}"
            print(f"   {model_info}")
            logger.info(model_info)
    except Exception as e:
        logger.warning(f"⚠️ Не удалось загрузить конфигурацию моделей: {e}")

    print("=" * 60)

    # Инициализируем агента
    try:
        from agent_core import AIAgent
        agent = AIAgent()
        add_activity_log("INFO", "AI Agent инициализирован", "system")
    except Exception as e:
        error_msg = f"Ошибка инициализации AI Agent: {e}"
        add_activity_log("ERROR", error_msg, "system")
        logger.error(error_msg)
        return

    # Запускаем сервер в отдельном потоке
    server_thread = threading.Thread(
        target=start_server,
        daemon=True,
        name="FastAPI-Server"
    )
    server_thread.start()

    # Запускаем Telegram бота в отдельном потоке
    telegram_thread = threading.Thread(
        target=start_telegram_bot,
        daemon=True,
        name="Telegram-Bot"
    )
    telegram_thread.start()

    add_activity_log("INFO", "Ожидание запуска сервисов...", "system")
    logger.info("⏳ Ожидаем запуск сервера и бота...")

    # Даем время сервисам на запуск
    await asyncio.sleep(3)

    # Запускаем мониторинг сервисов
    monitor_task = asyncio.create_task(monitor_services())

    # Выводим информацию о запуске
    startup_info = [
        "✅ СИСТЕМА ЗАПУЩЕНА",
        "🌐 Веб-интерфейс: http://localhost:8000",
        "🌐 Внешний доступ: http://94.228.123.86:8000",
        "🤖 Telegram бот: ЗАПУЩЕН",
        "📊 Мониторинг сервисов: АКТИВЕН",
        "🎯 AI модели: ГОТОВЫ К РАБОТЕ",
        "⏹️  Для остановки: Ctrl+C",
        "",
        "💡 Используйте:",
        "   - Браузер: http://94.228.123.86:8000",
        "   - Telegram: Найдите @StarkAIBot",
        "   - API: POST /api/chat для интеграций"
    ]

    print("\n".join(startup_info))
    logger.info("Stark AI Agent успешно запущен")

    for info in startup_info:
        if info and not info.startswith("   ") and "💡" not in info:
            logger.info(info)

    print("=" * 60)
    add_activity_log("INFO", "Stark AI Agent успешно запущен", "system")

    try:
        # Основной цикл работы
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        add_activity_log("INFO", "Остановка агента по запросу пользователя", "system")
        logger.info("🛑 Остановка Stark AI Agent...")
        monitor_task.cancel()

    except Exception as e:
        error_msg = f"Критическая ошибка в main: {e}"
        add_activity_log("ERROR", error_msg, "system")
        logger.error(error_msg)
        monitor_task.cancel()


if __name__ == "__main__":
    """
    Точка входа при прямом запуске main.py
    """
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        add_activity_log("INFO", "Приложение завершено пользователем", "system")
        print("\n👋 Stark AI Agent остановлен. До свидания!")
    except Exception as e:
        error_msg = f"Критическая ошибка при запуске: {e}"
        add_activity_log("ERROR", error_msg, "system")
        logger.error(error_msg)
        print(f"❌ Критическая ошибка: {e}")