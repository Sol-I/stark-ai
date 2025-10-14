"""
Test Script for Stark AI Agent
API: Проверка работоспособности агента и конфигурации
"""

import asyncio
import sys
import os

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent_core import AIAgent
from config import API_STRATEGIES, API_ENDPOINTS


async def test_configuration():
    """
    API: Проверка конфигурации системы
    Вход: None
    Выход: None (вывод в консоль)
    Логика: Проверка доступности стратегий провайдеров и endpoints
    """
    print("🔧 ТЕСТ КОНФИГУРАЦИИ")
    print("=" * 50)

    # Проверка стратегий
    print("📋 Стратегии провайдеров:")
    for provider, strategy in API_STRATEGIES.items():
        status = "✅" if strategy else "❌"
        print(f"  {status} {provider}: {bool(strategy)}")

    # Проверка endpoints
    print("\n🌐 API Endpoints:")
    for provider, endpoint in API_ENDPOINTS.items():
        status = "✅" if endpoint else "❌"
        print(f"  {status} {provider}: {endpoint}")

    print("✅ Конфигурация загружена корректно\n")


async def test_provider_strategies():
    """
    API: Проверка стратегий провайдеров в агенте
    Вход: None
    Выход: None (вывод в консоль)
    Логика: Проверка загрузки стратегий через метод агента
    """
    print("🔍 ТЕСТ СТРАТЕГИЙ ПРОВАЙДЕРОВ")
    print("=" * 50)

    agent = AIAgent()

    # Проверка стратегий для актуальных провайдеров
    providers = ['openrouter', 'deepseek']
    for provider in providers:
        strategy = agent._get_provider_strategy(provider)
        if strategy:
            print(f"  ✅ {provider}: стратегия загружена")
            print(f"     URL шаблон: {strategy['url']}")
        else:
            print(f"  ❌ {provider}: стратегия не найдена")

    print("✅ Стратегии провайдеров проверены\n")


async def test_agent_initialization():
    """
    API: Тест инициализации агента
    Вход: None
    Выход: None (вывод в консоль)
    Логика: Проверка ленивой загрузки моделей и инициализации агента
    """
    print("🔄 ТЕСТ ИНИЦИАЛИЗАЦИИ АГЕНТА")
    print("=" * 50)

    agent = AIAgent()

    try:
        # Принудительная инициализация для теста
        await agent.ensure_initialized()

        print(f"  ✅ Агент инициализирован")
        print(f"  📊 Загружено моделей: {len(agent.model_ranking)}")

        # Показываем топ-3 модели
        if agent.model_ranking:
            print(f"  🏆 Топ-3 модели:")
            for i, model in enumerate(agent.model_ranking[:3], 1):
                print(f"     {i}. {model['name']}")
        else:
            print(f"  ⚠️  Модели не загружены")

    except Exception as e:
        print(f"  ❌ Ошибка инициализации: {e}")

    print("✅ Тест инициализации завершен\n")


async def test_agent_processing():
    """
    API: Тест обработки сообщения агентом
    Вход: None
    Выход: None (вывод в консоль)
    Логика: Проверка полного цикла обработки сообщения через агента
    """
    print("🤖 ТЕСТ ОБРАБОТКИ СООБЩЕНИЯ")
    print("=" * 50)

    agent = AIAgent()

    try:
        print("🔄 Отправка тестового сообщения...")
        response = await agent.process_message(
            user_id="test_user",
            message="Привет! Ответь коротко - какая сегодня дата?",
            endpoint="test_suite",
            process_type="test"
        )

        print(f"📨 Ответ агента: {response}")

        # Анализ ответа
        if "❌" in response:
            print("❌ Обнаружена ошибка в ответе агента")
        elif not response or response.isspace():
            print("⚠️  Получен пустой ответ")
        else:
            print("✅ Агент ответил успешно")

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

    print("✅ Тест обработки завершен\n")


async def test_multiple_messages():
    """
    API: Тест обработки нескольких сообщений
    Вход: None
    Выход: None (вывод в консоль)
    Логика: Проверка работы с историей диалога и несколькими запросами
    """
    print("💬 ТЕСТ НЕСКОЛЬКИХ СООБЩЕНИЙ")
    print("=" * 50)

    agent = AIAgent()
    user_id = "multi_test_user"

    test_messages = [
        "Привет!",
        "Как тебя зовут?",
        "Что ты умеешь?"
    ]

    try:
        for i, message in enumerate(test_messages, 1):
            print(f"📝 Сообщение {i}: '{message}'")
            response = await agent.process_message(
                user_id=user_id,
                message=message,
                endpoint="test_suite",
                process_type="multi_test"
            )
            print(f"   📨 Ответ: {response[:100]}..." if len(response) > 100 else f"   📨 Ответ: {response}")
            print()

        # Проверяем историю
        history = agent.get_conversation_history(user_id)
        print(f"📊 История диалога: {len(history)} сообщений")

    except Exception as e:
        print(f"❌ Ошибка в тесте нескольких сообщений: {e}")

    print("✅ Тест нескольких сообщений завершен\n")


async def main():
    """
    API: Основная функция тестирования
    Вход: None
    Выход: None (вывод в консоль)
    Логика: Последовательный запуск всех тестов системы
    """
    print("🚀 ЗАПУСК ТЕСТОВ STARK AI AGENT")
    print("=" * 60)

    await test_configuration()
    await test_provider_strategies()
    await test_agent_initialization()
    await test_agent_processing()
    await test_multiple_messages()

    print("🎯 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())