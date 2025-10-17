#!/usr/bin/env python3
"""
Скрипт для просмотра последних LLM запросов из БД
"""

from database import get_recent_llm_requests


def show_recent_llm_requests(limit=20):
    requests = get_recent_llm_requests(limit)

    print(f"📊 ПОСЛЕДНИЕ {len(requests)} LLM ЗАПРОСОВ")
    print("=" * 80)

    for i, req in enumerate(requests, 1):
        status = "✅ УСПЕХ" if req.success else "❌ ОШИБКА"
        tokens = f"Токены: {req.prompt_tokens}+{req.completion_tokens}" if req.prompt_tokens else "Токены: не указано"
        error_info = f" | Ошибка: {req.error_type}" if not req.success and req.error_type else ""

        print(f"{i:2d}. {status} | {req.provider:12} | {req.model:30} | {tokens}{error_info}")
        print(f"     Время: {req.request_duration_ms}мс | Пользователь: {req.user_id} | {req.timestamp}")

        if req.error_message and not req.success:
            print(f"     Сообщение: {req.error_message[:100]}...")
        print()


if __name__ == "__main__":
    show_recent_llm_requests(2000)