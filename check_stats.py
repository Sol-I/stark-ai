#!/usr/bin/env python3
"""
Stark AI Agent - Statistics Monitor
Утилита для проверки статистики использования и метрик LLM
"""

import argparse
import json
from datetime import datetime
from agent_core import AIAgent, get_llm_metrics_sample


def print_usage_statistics():
    """Выводит статистику использования"""
    agent = AIAgent()
    stats = agent.get_usage_statistics()

    print("📊 СТАТИСТИКА ИСПОЛЬЗОВАНИЯ LLM")
    print("=" * 50)

    print(f"Общие запросы: {stats['total_requests']}")
    print(f"Входные токены: {stats['total_input_tokens']}")
    print(f"Выходные токены: {stats['total_output_tokens']}")
    print(f"Всего токенов: {stats['total_tokens']}")
    print(
        f"Средние токены/запрос: {stats['avg_input_tokens_per_request']:.1f} вх / {stats['avg_output_tokens_per_request']:.1f} вых")

    # Оценка стоимости (примерно)
    input_cost = stats['total_input_tokens'] * 0.000001  # ~$0.001/1K tokens
    output_cost = stats['total_output_tokens'] * 0.000002  # ~$0.002/1K tokens
    total_cost = input_cost + output_cost
    print(f"Примерная стоимость: ${total_cost:.4f}")


def print_recent_metrics(limit=10):
    """Выводит последние метрики запросов"""
    metrics = get_llm_metrics_sample(limit)

    print(f"\n🕒 ПОСЛЕДНИЕ {limit} ЗАПРОСОВ")
    print("=" * 50)

    if not metrics:
        print("Нет данных о запросах")
        return

    for i, metric in enumerate(metrics, 1):
        print(f"\n#{i} | {metric.get('timestamp', 'N/A')}")
        print(f"  Модель: {metric.get('model', 'N/A')}")
        print(f"  Провайдер: {metric.get('api_provider', 'N/A')}")
        print(f"  Статус: {metric.get('status', 'N/A')}")
        print(f"  Время: {metric.get('response_time_ms', 'N/A')}ms")
        print(f"  Токены: {metric.get('input_tokens', 0)} вх / {metric.get('output_tokens', 0)} вых")
        if metric.get('error_type'):
            print(f"  Ошибка: {metric.get('error_type')}")


def analyze_rate_limits(limit=20):
    """Анализирует проблемы с лимитами"""
    metrics = get_llm_metrics_sample(limit)

    error_count = sum(1 for m in metrics if m.get('status') == 'error')
    rate_limit_count = sum(
        1 for m in metrics if m.get('error_type') in ['rate_limit', 'daily_rate_limit', 'minute_rate_limit'])

    print(f"\n🚨 АНАЛИЗ ОШИБОК (последние {limit} запросов)")
    print("=" * 50)
    print(f"Всего запросов: {len(metrics)}")
    print(f"Ошибок: {error_count}")
    print(f"Лимиты: {rate_limit_count}")

    if rate_limit_count > 0:
        print("\n⚠️  Обнаружены проблемы с лимитами!")
        print("Рекомендации:")
        print("1. Проверить фонтовую проверку моделей")
        print("2. Увеличить паузы между запросами")
        print("3. Добавить кэширование повторных запросов")


def main():
    parser = argparse.ArgumentParser(description='Мониторинг статистики Stark AI Agent')
    parser.add_argument('--stats', action='store_true', help='Показать общую статистику')
    parser.add_argument('--metrics', type=int, default=10, help='Показать последние N метрик')
    parser.add_argument('--analyze', action='store_true', help='Анализ проблем с лимитами')
    parser.add_argument('--all', action='store_true', help='Показать всю информацию')

    args = parser.parse_args()

    if not any([args.stats, args.metrics, args.analyze, args.all]):
        args.all = True

    if args.all or args.stats:
        print_usage_statistics()

    if args.all or args.metrics:
        print_recent_metrics(args.metrics)

    if args.all or args.analyze:
        analyze_rate_limits(args.metrics * 2)


if __name__ == "__main__":
    main()