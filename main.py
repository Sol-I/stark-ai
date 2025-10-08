#!/usr/bin/env python3
"""
Stark AI Agent - Main Entry Point
Автоматически выбирает лучшую доступную модель AI
"""

import asyncio
import threading
import time
import logging
from server import run_server
from agent_core import AIAgent

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def start_server():
    """Запуск FastAPI сервера в отдельном потоке"""
    try:
        logger.info("Запуск FastAPI сервера...")
        run_server()
    except Exception as e:
        logger.error(f"Ошибка сервера: {e}")


async def background_model_checker(agent: AIAgent):
    """Фоновая проверка доступности моделей"""
    while True:
        try:
            await agent.background_model_checker()
        except Exception as e:
            logger.error(f"Ошибка в фоновой проверке: {e}")
            await asyncio.sleep(60)


async def main():
    """Основная функция запуска агента"""
    print("🚀 Stark AI Agent запускается...")
    print("=" * 50)

    # Показываем рейтинг моделей
    from config import MODEL_RANKING
    print("📊 Рейтинг моделей (по параметрам):")
    for i, model in enumerate(MODEL_RANKING[:5], 1):  # Показываем топ-5
        status = "✅" if i == 1 else "🟡"
        print(f"{status} {i}. {model['provider']} - {model['params']}B параметров")

    print("=" * 50)

    # Инициализируем агента
    agent = AIAgent()

    # Запускаем сервер в отдельном потоке
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    logger.info("Ожидаем запуск сервера...")
    await asyncio.sleep(5)

    # Запускаем фоновую проверку моделей
    bg_task = asyncio.create_task(background_model_checker(agent))

    # Выводим информацию о запуске
    print("✅ Сервер запущен!")
    print("🌐 Веб-интерфейс: http://localhost:8000")
    print("🌐 Внешний доступ: http://94.228.123.86:8000")
    print("🤖 Telegram бот: активен")
    print("🔄 Фоновая проверка моделей: запущена")
    print("⏹️  Для остановки: Ctrl+C")
    print("=" * 50)

    try:
        # Бесконечный цикл для работы службы
        while True:
            await asyncio.sleep(60)

    except KeyboardInterrupt:
        print("\n🛑 Остановка агента...")
        bg_task.cancel()
        logger.info("Агент остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 До свидания!")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        print(f"❌ Критическая ошибка: {e}")