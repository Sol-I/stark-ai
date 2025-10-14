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

        print(f"Активные пользователи: {stats.get('active_users', 0)}")
        print(f"Всего диалогов: {stats.get('total_conversations', 0)}")
        print(f"Доступно моделей: {stats.get('models_available', 0)}")
        print(f"Глубина истории: {stats.get('max_history_length', 0)}")

        # Дополнительная статистика из БД
        try:
            from database import SessionLocal, LLMRequest
            db = SessionLocal()
            try:
                total_requests = db.query(LLMRequest).count()
                successful_requests = db.query(LLMRequest).filter(LLMRequest.success == True).count()
                failed_requests = db.query(LLMRequest).filter(LLMRequest.success == False).count()

                total_input_tokens = db.query(LLMRequest.prompt_tokens).filter(
                    LLMRequest.prompt_tokens.isnot(None)).scalar() or 0
                total_output_tokens = db.query(LLMRequest.completion_tokens).filter(
                    LLMRequest.completion_tokens.isnot(None)).scalar() or 0

                print(f"\n📈 СТАТИСТИКА ИЗ БАЗЫ ДАННЫХ:")
                print(f"Всего запросов: {total_requests}")
                print(f"Успешных запросов: {successful_requests}")
                print(f"Ошибочных запросов: {failed_requests}")
                print(f"Входные токены: {total_input_tokens:,}")
                print(f"Выходные токены: {total_output_tokens:,}")
                print(f"Всего токенов: {total_input_tokens + total_output_tokens:,}")

                if total_requests > 0:
                    success_rate = (successful_requests / total_requests) * 100
                    print(f"Успешность: {success_rate:.1f}%")

                    # Оценка стоимости (примерные цены)
                    input_cost = total_input_tokens * 0.000001
                    output_cost = total_output_tokens * 0.000002
                    total_cost = input_cost + output_cost
                    print(f"Примерная стоимость: ${total_cost:.4f}")

            finally:
                db.close()

        except Exception as e:
            print(f"⚠️  Не удалось получить статистику из БД: {e}")

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
    Логика: Получение последних LLM запросов из БД и форматированный вывод
    """
    try:
        from database import get_recent_llm_requests, SessionLocal

        db = SessionLocal()
        try:
            requests = get_recent_llm_requests(limit)

            add_activity_log("INFO", f"Запрос {limit} последних LLM запросов", "stats_monitor")

            print(f"\n🕒 ПОСЛЕДНИЕ {len(requests)} LLM ЗАПРОСОВ")
            print("=" * 80)

            if not requests:
                print("📭 В базе нет записей о LLM запросах")
                return

            for i, req in enumerate(requests, 1):
                status = "✅ УСПЕХ" if req.success else "❌ ОШИБКА"
                tokens_info = f"Токены: {req.prompt_tokens}+{req.completion_tokens}" if req.prompt_tokens else "Токены: не указано"
                error_info = f" | Ошибка: {req.error_type}" if not req.success and req.error_type else ""

                print(f"{i:2d}. {status} | {req.provider:12} | {req.model:30} | {tokens_info}{error_info}")
                print(f"     Время: {req.request_duration_ms}мс | Пользователь: {req.user_id} | {req.timestamp}")

                if req.error_message and not req.success:
                    print(f"     Сообщение: {req.error_message[:100]}...")

        finally:
            db.close()

    except ImportError as e:
        print(f"❌ Ошибка импорта модуля БД: {e}")
        add_activity_log("ERROR", f"Ошибка импорта БД в print_recent_metrics: {e}", "stats_monitor")
    except Exception as e:
        print(f"❌ Ошибка получения метрик: {e}")
        add_activity_log("ERROR", f"Ошибка получения метрик: {e}", "stats_monitor")


def analyze_rate_limits(limit=20):
    """
    API: Анализ проблем с лимитами запросов
    Вход: limit (количество записей для анализа)
    Выход: None (вывод в консоль)
    Логика: Статистический анализ ошибок, выявление паттернов лимитов, рекомендации
    """
    try:
        from database import get_recent_llm_requests, SessionLocal

        db = SessionLocal()
        try:
            requests = get_recent_llm_requests(limit)

            add_activity_log("INFO", f"Анализ лимитов для {limit} запросов", "stats_monitor")

            if not requests:
                print("📭 Нет данных для анализа")
                return

            error_count = sum(1 for req in requests if not req.success)
            rate_limit_count = sum(
                1 for req in requests if req.error_type and 'rate_limit' in req.error_type.lower())

            print(f"\n🚨 АНАЛИЗ ОШИБОК LLM (последние {len(requests)} запросов)")
            print("=" * 50)
            print(f"Всего запросов: {len(requests)}")
            print(f"Ошибок: {error_count}")
            print(f"Лимиты: {rate_limit_count}")

            if rate_limit_count > 0:
                print("\n⚠️  Обнаружены проблемы с лимитами API!")
                print("Рекомендации:")
                print("1. Проверить настройки rate limiting в конфигурации")
                print("2. Увеличить паузы между запросами в agent_core.py")
                print("3. Добавить ротацию API ключей при лимитах")
                print("4. Включить кэширование повторных запросов")
            elif error_count > 0:
                print("\n⚠️  Есть ошибки, но не связанные с лимитами")
            else:
                print("\n✅ Проблем с лимитами не обнаружено")

            # Анализ по провайдерам
            provider_errors = {}
            for req in requests:
                if not req.success:
                    provider = req.provider
                    provider_errors[provider] = provider_errors.get(provider, 0) + 1

            if provider_errors:
                print(f"\n📊 Ошибки по провайдерам:")
                for provider, count in provider_errors.items():
                    print(f"  {provider}: {count} ошибок")

        finally:
            db.close()

    except ImportError:
        print("❌ Модуль базы данных недоступен для анализа")
        add_activity_log("ERROR", "Модуль БД недоступен для анализа", "stats_monitor")
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
            else:
                print(f"\n📋 Логов нет")

            # Активные задачи
            recent_tasks = get_recent_tasks(5)
            if recent_tasks:
                print(f"\n📝 Последние 5 задач:")
                for task in recent_tasks:
                    status_icon = "✅" if task.status == "completed" else "🔄" if task.status == "in_progress" else "⏳"
                    print(f"  {status_icon} [{task.status}] {task.file}")
            else:
                print(f"\n📝 Задач нет")

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