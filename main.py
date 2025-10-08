#!/usr/bin/env python3
"""
Stark AI Agent - Main Entry Point
"""

import asyncio
import threading
import time
import logging
from server import run_server
from agent_core import AIAgent, add_activity_log

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/root/stark/main.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def start_server():
    """Запуск FastAPI сервера в отдельном потоке"""
    try:
        add_activity_log("INFO", "Запуск FastAPI сервера...")
        logger.info("Starting FastAPI server...")
        run_server()
    except Exception as e:
        error_msg = f"Ошибка сервера: {e}"
        add_activity_log("ERROR", error_msg)
        logger.error(error_msg)


async def main():
    """Основная функция запуска агента"""
    add_activity_log("INFO", "Запуск Stark AI Agent")
    logger.info("🚀 Stark AI Agent запускается...")

    print("=" * 50)

    # Показываем рейтинг моделей
    from config import MODEL_RANKING
    logger.info("📊 Рейтинг моделей:")
    for i, model in enumerate(MODEL_RANKING[:5], 1):
        status = "✅" if i == 1 else "🟡"
        model_info = f"{status} {i}. {model['provider']} - {model['params']}B параметров"
        print(model_info)
        logger.info(model_info)

    print("=" * 50)

    # Инициализируем агента
    agent = AIAgent()

    # Запускаем сервер в отдельном потоке
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    add_activity_log("INFO", "Ожидание запуска сервера...")
    logger.info("Ожидаем запуск сервера...")
    await asyncio.sleep(5)

    # Запускаем фоновую проверку моделей (заглушку)
    bg_task = asyncio.create_task(agent.background_model_checker())

    # Выводим информацию о запуске
    startup_info = [
        "✅ Сервер запущен!",
        "🌐 Веб-интерфейс: http://localhost:8000",
        "🌐 Внешний доступ: http://94.228.123.86:8000",
        "🤖 Telegram бот: активен",
        "🔄 Фоновая проверка моделей: ОТКЛЮЧЕНА",
        "🎯 Логика: последовательный перебор моделей",
        "⏹️  Для остановки: Ctrl+C"
    ]

    for info in startup_info:
        print(info)
        logger.info(info)

    add_activity_log("INFO", "Stark AI Agent успешно запущен")
    print("=" * 50)

    try:
        # Бесконечный цикл для работы службы
        while True:
            await asyncio.sleep(60)

    except KeyboardInterrupt:
        add_activity_log("INFO", "Остановка агента по запросу пользователя")
        logger.info("🛑 Остановка агента...")
        bg_task.cancel()

    except Exception as e:
        error_msg = f"Критическая ошибка в main: {e}"
        add_activity_log("ERROR", error_msg)
        logger.error(error_msg)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        add_activity_log("INFO", "Приложение завершено")
        print("\n👋 До свидания!")
    except Exception as e:
        error_msg = f"Критическая ошибка: {e}"
        add_activity_log("ERROR", error_msg)
        logger.error(error_msg)
        print(f"❌ Критическая ошибка: {e}")