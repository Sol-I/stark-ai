# check_stats.py
"""
Stark AI Agent - Statistics Monitor
API: Утилита мониторинга статистики использования и метрик LLM моделей
Основные возможности: анализ использования токенов, мониторинг ошибок, оценка стоимости запросов
"""

import argparse
import json
from datetime import datetime

# Импорт системы логирования
try:
    from database import add_activity_log
except ImportError:
    def add_activity_log(level: str, message: str, user_id: str = None):
        print(f"📝 [{level}] {message} (user: {user_id})")


def print_usage_statistics():
    """
    API: Вывод общей статистики использования LLM
    Вход: None
    Выход: None (вывод в консоль)
    Логика: Получение статистики от AI Agent, расчет метрик и стоимости
    """
    try:
        from agent_core import AIAgent
        agent = AIAgent()
        stats = agent.get_usage_statistics()

        add_activity_log("INFO", "Запрос статистики использования", "stats_monitor")

        print("📊 СТАТИСТИКА ИСПОЛЬЗОВАНИЯ LLM")
        print("=" * 50)

        print(f"Общие запросы: {stats.get('total_requests', 0)}")
        print(f"Успешные запросы: {stats.get('successful_requests', 0)}")
        print(f"Ошибочные запросы: {stats.get('failed_requests', 0)}")
        print(f"Входные токены: {stats.get('total_input_tokens', 0):,}")
        print(f"Выходные токены: {stats.get('total_output_tokens', 0):,}")
        print(f"Всего токенов: {stats.get('total_tokens', 0):,}")

        if stats.get('total_requests', 0) > 0:
            avg_input = stats.get('total_input_tokens', 0) / stats.get('total_requests', 1)
            avg_output = stats.get('total_output_tokens', 0) / stats.get('total_requests', 1)
            print(f"Средние токены/запрос: {avg_input:.1f} вх / {avg_output:.1f} вых")

        # Оценка стоимости (примерные цены)
        input_cost = stats.get('total_input_tokens', 0) * 0.000001  # ~$0.001/1K tokens
        output_cost = stats.get('total_output_tokens', 0) * 0.000002  # ~$0.002/1K tokens
        total_cost = input_cost + output_cost
        print(f"Примерная стоимость: ${total_cost:.4f}")

        success_rate = (stats.get('successful_requests', 0) / stats.get('total_requests', 1)) * 100
        print(f"Успешность: {success_rate:.1f}%")

    except ImportError:
        print("❌ AI Agent недоступен")
        add_activity_log("ERROR", "AI Agent недоступен для статистики", "stats_monitor")
    except Exception as e:
        error_msg = f"Ошибка получения статистики: {e}"
        print(f"❌ {error_msg}")
        add_activity_log("ERROR", error_msg, "stats_monitor")


def print_recent_metrics(limit=10):
    """
    API: Вывод последних метрик запросов к LLM
    Вход: limit (количество записей для показа)
    Выход: None (вывод в консоль)
    Логика: Получение сэмпла метрик, форматирование и вывод детальной информации
    """
    try:
        from agent_core import get_llm_metrics_sample
        metrics = get_llm_metrics_sample(limit)

        add_activity_log("INFO", f"Запрос {limit} последних метрик", "stats_monitor")

        print(f"\n🕒 ПОСЛЕДНИЕ {limit} ЗАПРОСОВ LLM")
        print("=" * 50)

        if not metrics:
            print("📭 Нет данных о запросах")
            return

        for i, metric in enumerate(metrics, 1):
            print(f"\n#{i} | {metric.get('timestamp', 'N/A')}")
            print(f"  Модель: {metric.get('model', 'N/A')}")
            print(f"  Провайдер: {metric.get('api_provider', 'N/A')}")
            print(f"  Статус: {metric.get('status', 'N/A')}")
            print(f"  Время ответа: {metric.get('response_time_ms', 'N/A')}ms")
            print(f"  Токены: {metric.get('input_tokens', 0)} вх / {metric.get('output_tokens', 0)} вых")

            if metric.get('error_type'):
                print(f"  ❌ Ошибка: {metric.get('error_type')}")
                if metric.get('error_message'):
                    print(f"     Сообщение: {metric.get('error_message')}")

    except ImportError:
        print("❌ Модуль метрик недоступен")
        add_activity_log("ERROR", "Модуль метрик недоступен", "stats_monitor")
    except Exception as e:
        error_msg = f"Ошибка получения метрик: {e}"
        print(f"❌ {error_msg}")
        add_activity_log("ERROR", error_msg, "stats_monitor")


def analyze_rate_limits(limit=20):
    """
    API: Анализ проблем с лимитами запросов
    Вход: limit (количество записей для анализа)
    Выход: None (вывод в консоль)
    Логика: Статистический анализ ошибок, выявление паттернов лимитов, рекомендации
    """
    try:
        from agent_core import get_llm_metrics_sample
        metrics = get_llm_metrics_sample(limit)

        add_activity_log("INFO", f"Анализ лимитов для {limit} запросов", "stats_monitor")

        error_count = sum(1 for m in metrics if m.get('status') == 'error')
        rate_limit_count = sum(
            1 for m in metrics if m.get('error_type') in ['rate_limit', 'daily_rate_limit', 'minute_rate_limit'])

        print(f"\n🚨 АНАЛИЗ ОШИБОК LLM (последние {limit} запросов)")
        print("=" * 50)
        print(f"Всего запросов: {len(metrics)}")
        print(f"Ошибок: {error_count}")
        print(f"Лимиты: {rate_limit_count}")

        if rate_limit_count > 0:
            print("\n⚠️  Обнаружены проблемы с лимитами API!")
            print("Рекомендации:")
            print("1. Проверить настройки rate limiting в конфигурации")
            print("2. Увеличить паузы между запросами в agent_core.py")
            print("3. Добавить ротацию API ключей при лимитах")
            print("4. Включить кэширование повторных запросов")
        else:
            print("\n✅ Проблем с лимитами не обнаружено")

        # Анализ по провайдерам
        provider_errors = {}
        for metric in metrics:
            if metric.get('status') == 'error':
                provider = metric.get('api_provider', 'unknown')
                provider_errors[provider] = provider_errors.get(provider, 0) + 1

        if provider_errors:
            print(f"\n📊 Ошибки по провайдерам:")
            for provider, count in provider_errors.items():
                print(f"  {provider}: {count} ошибок")

    except ImportError:
        print("❌ Модуль метрик недоступен для анализа")
        add_activity_log("ERROR", "Модуль метрик недоступен для анализа", "stats_monitor")
    except Exception as e:
        error_msg = f"Ошибка анализа лимитов: {e}"
        print(f"❌ {error_msg}")
        add_activity_log("ERROR", error_msg, "stats_monitor")


def print_database_stats():
    """
    API: Вывод статистики базы данных
    Вход: None
    Выход: None (вывод в консоль)
    Логика: Получение статистики из БД (логи, задачи), анализ активности системы
    """
    try:
        from database import get_recent_logs, get_recent_tasks, SessionLocal, LogEntry, ModificationTask

        db = SessionLocal()
        try:
            log_count = db.query(LogEntry).count()
            task_count = db.query(ModificationTask).count()

            add_activity_log("INFO", "Запрос статистики БД", "stats_monitor")

            print(f"\n🗄️ СТАТИСТИКА БАЗЫ ДАННЫХ")
            print("=" * 50)
            print(f"Всего записей в логах: {log_count}")
            print(f"Всего задач модификации: {task_count}")

            # Последние логи
            recent_logs = get_recent_logs(5)
            if recent_logs:
                print(f"\n📋 Последние 5 логов:")
                for log in recent_logs:
                    print(f"  [{log.level}] {log.timestamp.strftime('%H:%M:%S')} {log.message[:50]}...")

            # Активные задачи
            recent_tasks = get_recent_tasks(5)
            if recent_tasks:
                print(f"\n📝 Последние 5 задач:")
                for task in recent_tasks:
                    status_icon = "✅" if task.status == "completed" else "🔄" if task.status == "in_progress" else "⏳"
                    print(f"  {status_icon} [{task.status}] {task.file}")

        finally:
            db.close()

    except ImportError:
        print("❌ Модуль базы данных недоступен")
        add_activity_log("ERROR", "Модуль БД недоступен для статистики", "stats_monitor")
    except Exception as e:
        error_msg = f"Ошибка получения статистики БД: {e}"
        print(f"❌ {error_msg}")
        add_activity_log("ERROR", error_msg, "stats_monitor")


def main():
    """
    API: Основная функция утилиты мониторинга
    Вход: None (аргументы командной строки)
    Выход: None (вывод в консоль)
    Логика: Парсинг аргументов, вызов соответствующих функций мониторинга
    """
    parser = argparse.ArgumentParser(
        description='Stark AI Agent - Утилита мониторинга статистики и метрик',
        epilog='Примеры использования:\n'
               '  python check_stats.py --all\n'
               '  python check_stats.py --stats --metrics 5\n'
               '  python check_stats.py --analyze'
    )

    parser.add_argument('--stats', action='store_true', help='Показать общую статистику использования LLM')
    parser.add_argument('--metrics', type=int, default=10, metavar='N',
                        help='Показать последние N метрик запросов (по умолчанию: 10)')
    parser.add_argument('--analyze', action='store_true', help='Анализ проблем с лимитами API')
    parser.add_argument('--db', action='store_true', help='Статистика базы данных')
    parser.add_argument('--all', action='store_true', help='Показать всю доступную информацию')

    args = parser.parse_args()

    # Если не указаны аргументы - показываем справку
    if not any([args.stats, args.metrics, args.analyze, args.db, args.all]):
        parser.print_help()
        return

    add_activity_log("INFO", f"Запуск check_stats.py с аргументами: {vars(args)}", "stats_monitor")

    if args.all or args.stats:
        print_usage_statistics()

    if args.all or args.metrics:
        print_recent_metrics(args.metrics)

    if args.all or args.analyze:
        analyze_rate_limits(args.metrics * 2)

    if args.all or args.db:
        print_database_stats()

    add_activity_log("INFO", "Завершение работы check_stats.py", "stats_monitor")


if __name__ == "__main__":
    """
    Точка входа при прямом запуске утилиты мониторинга
    """
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Мониторинг завершен")
        add_activity_log("INFO", "Мониторинг завершен пользователем", "stats_monitor")
    except Exception as e:
        error_msg = f"Критическая ошибка в check_stats: {e}"
        print(f"❌ {error_msg}")
        add_activity_log("ERROR", error_msg, "stats_monitor")