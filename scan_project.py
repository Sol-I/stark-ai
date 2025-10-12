# scan_project.py
"""
Project Scanner - система анализа и модификации кода проекта
API: Сканирование структуры, извлечение документации, управление изменениями кода
Основные возможности: деревья файлов, API документация, полный контекст, безопасные модификации
"""

import re
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict
import sys
import io
import json
import shutil
from datetime import datetime

# Настройка кодировки
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Импорт системы логирования
try:
    from database import add_activity_log
except ImportError:
    def add_activity_log(level: str, message: str, user_id: str = None):
        print(f"📝 [{level}] {message} (user: {user_id})")


class ProjectScanner:
    """
    API: Сканер структуры проекта
    Вход: root_dir (корневая директория)
    Выход: None (создает экземпляр сканера)
    Логика: Настройка игнорируемых паттернов, рекурсивное сканирование файлов
    """

    def __init__(self, root_dir='.'):
        self.root_dir = Path(root_dir).absolute()
        self.ignore_patterns = [
            '__pycache__', '.git', '.idea', '.vscode', 'venv', 'env',
            'node_modules', '.pytest_cache', '.mypy_cache', 'dist', 'build',
            '*.pyc', '*.pyo', '*.so', '*.dll', '*.exe'
        ]
        add_activity_log("INFO", f"Инициализирован сканер для {self.root_dir}")

    def should_ignore(self, path):
        """
        API: Проверка игнорирования файла/папки
        Вход: path (путь к файлу/папке)
        Выход: bool (игнорировать или нет)
        Логика: Сравнение с паттернами игнорирования, проверка скрытых файлов
        """
        path_str = str(path)

        # Игнорируем скрытые файлы/папки
        if any(part.startswith('.') and part not in ['.', '..'] for part in path.parts):
            if path.name in ['.env', '.env.example', '.gitignore']:
                return False
            return True

        for pattern in self.ignore_patterns:
            if pattern.startswith('*'):
                if path_str.endswith(pattern[1:]):
                    return True
            elif pattern in path_str:
                return True
        return False

    def scan_structure_tree(self):
        """
        API: Сканирование структуры в формате Markdown
        Вход: None
        Выход: str (дерево файлов в Markdown)
        Логика: Рекурсивный обход директорий, форматирование в древовидную структуру
        """
        add_activity_log("INFO", "Генерация дерева структуры проекта")
        output = ["# Структура проекта\n"]

        def scan_directory(directory, level=0):
            try:
                items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                for item in items:
                    if self.should_ignore(item):
                        continue
                    indent = "  " * level
                    if item.is_dir():
                        output.append(f"{indent}- **📁 {item.name}/**")
                        scan_directory(item, level + 1)
                    else:
                        output.append(f"{indent}- 📄 {item.name}")
            except PermissionError:
                output.append(f"{'  ' * level}- *[Доступ запрещен]*")

        scan_directory(self.root_dir)
        result = "\n".join(output)
        add_activity_log("INFO", f"Сгенерировано дерево структуры ({len(result)} символов)")
        return result

    def scan_api_documentation(self):
        """
        API: Сканирование API документации проекта
        Вход: None
        Выход: str (структурированная документация API)
        Логика: Рекурсивный поиск Python файлов, извлечение классов и функций с докстрингами
        """
        add_activity_log("INFO", "Сканирование API документации")

        output = ["PROJECT API DOCUMENTATION:"]
        output.append("=" * 50)

        root_path = Path(self.root_dir)
        python_files = list(root_path.rglob('*.py'))

        for file_path in python_files:
            if self.should_ignore(file_path):
                continue

            api_docs = self.extract_api_documentation(file_path)
            if api_docs:
                output.append(f"\n--- {file_path.relative_to(root_path)} ---")
                output.append(api_docs)

        result = "\n".join(output)
        add_activity_log("INFO", f"Сгенерирована API документация ({len(result)} символов)")
        return result

    def extract_api_documentation(self, file_path):
        """
        API: Извлечение API документации из файла
        Вход: file_path (путь к файлу)
        Выход: str (отформатированная документация)
        Логика: Поиск классов и функций с докстрингами через регулярные выражения
        """
        try:
            content = file_path.read_text(encoding='utf-8')

            # Улучшенные регулярные выражения - ищем только докстринги сразу после class/def
            classes = re.findall(r'class\s+(\w+)[^"]*?"""(.*?)"""', content, re.DOTALL)
            functions = re.findall(r'def\s+(\w+)\s*\([^"]*?"""(.*?)"""', content, re.DOTALL)

            docs = []
            if classes:
                docs.append(f"CLASSES:")
                for class_name, docstring in classes:
                    # Очищаем докстринг от лишних пробелов
                    clean_doc = ' '.join(docstring.strip().split())
                    docs.append(f"  {class_name}: {clean_doc[:100]}...")

            if functions:
                docs.append(f"FUNCTIONS:")
                for func_name, docstring in functions:
                    clean_doc = ' '.join(docstring.strip().split())
                    docs.append(f"  {func_name}: {clean_doc[:100]}...")

            return "\n".join(docs) if docs else f"[No API docs in {file_path.name}]"

        except Exception as e:
            return f"[Error reading {file_path.name}: {e}]"

    def scan_full_code(self):
        """
        API: Сканирование полного кода проекта
        Вход: None
        Выход: str (структура + содержимое файлов)
        Логика: Рекурсивный обход с извлечением содержимого важных файлов
        """
        add_activity_log("INFO", "Сканирование полного кода проекта")

        output = ["PROJECT FULL CODE ANALYSIS:"]

        # Структура
        structure = []
        file_paths = []

        def collect_structure(directory, level=0):
            try:
                items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                for item in items:
                    if self.should_ignore(item):
                        continue
                    indent = "  " * level
                    if item.is_dir():
                        structure.append(f"{indent}{item.name}/")
                        collect_structure(item, level + 1)
                    else:
                        structure.append(f"{indent}{item.name}")
                        file_paths.append(item)
            except PermissionError:
                structure.append(f"{'  ' * level}[Permission denied]")

        collect_structure(self.root_dir)
        output.append("STRUCTURE:")
        output.extend(structure)
        output.append("\n" + "=" * 50 + "\n")

        # Содержимое файлов
        output.append("FILE CONTENTS:")
        for file_path in file_paths:
            if file_path.suffix in ['.py', '.md', '.txt', '.json', '.yaml', '.yml', '.toml']:
                output.append(f"\n--- FILE: {file_path.relative_to(self.root_dir)} ---")
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    if content.strip():
                        output.append(content)
                    else:
                        output.append("[File is empty]")
                except Exception as e:
                    output.append(f"[Error reading file: {e}]")

        result = "\n".join(output)
        add_activity_log("INFO", f"Сгенерирован полный код ({len(result)} символов)")
        return result


def get_specific_code(file_procedure_pairs, root_dir='.'):
    """
    API: Получение конкретного кода процедур или файлов
    Вход: file_procedure_pairs (список файлов и процедур), root_dir (корневая директория)
    Выход: str (код процедур/файлов) + копирует в буфер обмена
    Логика: Поиск файлов и процедур, извлечение кода, форматирование вывода
    """
    scanner = ProjectScanner(root_dir)
    output = []

    add_activity_log("INFO", f"Поиск кода для {len(file_procedure_pairs)} процедур")

    for file_spec in file_procedure_pairs:
        if isinstance(file_spec, tuple):
            filename, procedure_name = file_spec
        else:
            filename = file_spec
            procedure_name = None

        # Поиск файла
        file_path = None
        for potential_path in Path(root_dir).rglob('*'):
            if potential_path.name == filename and not scanner.should_ignore(potential_path):
                file_path = potential_path
                break

        if not file_path or not file_path.exists():
            output.append(f"# Файл не найден: {filename}")
            continue

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')

            if procedure_name:
                # Поиск конкретной процедуры
                procedure_code = extract_procedure_code(content, procedure_name, filename)
                if procedure_code:
                    output.append(f"# Файл: {filename}\n# Процедура: {procedure_name}\n{procedure_code}")
                else:
                    output.append(f"# Процедура '{procedure_name}' не найдена в файле {filename}")
            else:
                # Весь файл
                output.append(f"# Файл: {filename}\n{content}")

        except Exception as e:
            output.append(f"# Ошибка чтения {filename}: {e}")

    result = "\n\n".join(output)

    # Копируем в буфер обмена
    if result.strip():
        try:
            import pyperclip
            pyperclip.copy(result)
            add_activity_log("INFO", f"Код скопирован в буфер обмена ({len(result)} символов)")
            print(f"✅ Код скопирован в буфер обмена ({len(result)} символов)")
        except ImportError:
            add_activity_log("WARNING", "Pyperclip не установлен, буфер обмена недоступен")
            print("❌ Pyperclip не установлен, буфер обмена недоступен")

    return result


def extract_procedure_code(content, procedure_name, filename):
    """
    API: Извлечение кода конкретной процедуры
    Вход: content (содержимое файла), procedure_name (имя процедуры), filename (имя файла)
    Выход: str (код процедуры)
    Логика: Поиск процедуры по имени, извлечение кода с учетом отступов
    """
    lines = content.split('\n')
    in_procedure = False
    procedure_lines = []
    indent_level = 0
    procedure_start = None

    patterns = [
        f"def {procedure_name}(",
        f"async def {procedure_name}(",
        f"class {procedure_name}",
        f"class {procedure_name}(",
    ]

    for i, line in enumerate(lines):
        if not in_procedure and any(line.strip().startswith(pattern) for pattern in patterns):
            in_procedure = True
            procedure_start = i
            indent_level = len(line) - len(line.lstrip())
            procedure_lines.append(line)
            continue

        if in_procedure:
            current_indent = len(line) - len(line.lstrip()) if line.strip() else indent_level + 1
            if current_indent <= indent_level and line.strip() and i > procedure_start:
                break
            procedure_lines.append(line)

    return '\n'.join(procedure_lines) if procedure_lines else ""


def safe_code_modification(tasks: List[Dict]) -> Dict:
    """
    API: Безопасная модификация кода
    Вход: tasks (список задач модификации)
    Выход: Dict (результат выполнения)
    Логика: Создание бэкапов, применение изменений, проверка синтаксиса, откат при ошибках
    """
    add_activity_log("INFO", f"Начало модификации кода: {len(tasks)} задач")

    backup_files = []
    results = []

    try:
        # Создание бэкапов
        for task in tasks:
            file_path = Path(task['file'])
            if file_path.exists():
                backup_path = Path(f"backup_{datetime.now().strftime('%H%M%S')}_{file_path.name}")
                shutil.copy2(file_path, backup_path)
                backup_files.append(backup_path)
                results.append(f"Создан бэкап: {backup_path}")

        # Применение изменений
        for i, task in enumerate(tasks):
            file_path = Path(task['file'])
            asis = task.get('asis', '')
            tobe = task.get('tobe', '')
            mode = task.get('mode', 'replace')
            desc = task.get('desc', f'Изменение {i + 1}')

            if not file_path or not tobe:
                results.append(f"ОШИБКА: Задача {i + 1}: отсутствуют file или tobe")
                continue

            if mode == 'create' and not file_path.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(tobe, encoding='utf-8')
                results.append(f"УСПЕХ: Создан файл: {file_path}")

            elif file_path.exists():
                content = file_path.read_text(encoding='utf-8')

                if mode == 'append':
                    new_content = content + '\n' + tobe
                elif mode == 'replace' and asis:
                    if asis in content:
                        new_content = content.replace(asis, tobe)
                    else:
                        results.append(f"ОШИБКА: Паттерн asis не найден в {file_path}")
                        continue
                else:
                    new_content = tobe

                file_path.write_text(new_content, encoding='utf-8')
                results.append(f"УСПЕХ: Изменен файл: {file_path}")

            else:
                results.append(f"ОШИБКА: Файл не существует: {file_path}")
                continue

        # Проверка синтаксиса
        for task in tasks:
            if task['file'].endswith('.py'):
                file_path = Path(task['file'])
                if file_path.exists():
                    try:
                        compile(file_path.read_text(encoding='utf-8'), file_path.name, 'exec')
                    except SyntaxError as e:
                        results.append(f"ОШИБКА: Синтаксическая ошибка в {file_path}: {e}")
                        raise

        add_activity_log("INFO", "Модификация кода завершена успешно")
        return {
            "status": "success",
            "message": "Все изменения применены успешно",
            "changes": results,
            "backups": [str(b) for b in backup_files]
        }

    except Exception as e:
        # Восстановление бэкапов
        for backup in backup_files:
            if backup.exists():
                original = Path(backup.name.replace(f"backup_{backup.name.split('_')[1]}_", ""))
                shutil.copy2(backup, original)
                results.append(f"ВОССТАНОВЛЕН: {original} из {backup}")

        add_activity_log("ERROR", f"Ошибка модификации кода: {e}")
        return {
            "status": "error",
            "message": f"Ошибка применения изменений. Бэкапы восстановлены.",
            "errors": results + [f"ОШИБКА: {e}"],
            "backups": [str(b) for b in backup_files]
        }


def generate_project_context():
    """
    API: Генерация технического контекста проекта
    Вход: None
    Выход: str (отформатированный контекст в Markdown)
    Логика: Сбор структуры проекта, API документации и системных данных с раздельной обработкой ошибок
    """
    add_activity_log("INFO", "Генерация технического контекста проекта")

    import json
    from datetime import datetime

    context = {
        "generated_at": datetime.now().isoformat(),
        "project": {},
        "database": {},
        "system_status": {}
    }

    # 1. Информация о проекте
    try:
        scanner = ProjectScanner('.')
        structure = scanner.scan_structure_tree()
        api_docs = scanner.scan_api_documentation()

        context["project"] = {
            "structure": structure,
            "api_documentation": api_docs,
            "file_count": len(list(Path('.').rglob('*.py'))),
            "main_files": [f.name for f in Path('.').glob('*.py') if f.is_file()]
        }
    except Exception as e:
        context["project"]["error"] = str(e)
        add_activity_log("ERROR", f"Ошибка сканирования проекта: {e}")

    # 2. Системные данные - раздельная обработка ошибок
    try:
        from database import get_recent_logs, get_recent_tasks, SessionLocal, LogEntry, ModificationTask
    except ImportError as e:
        context["database"]["error"] = f"Модуль БД недоступен: {e}"
        add_activity_log("ERROR", f"Ошибка импорта БД: {e}")
    except Exception as e:
        context["database"]["error"] = f"Ошибка загрузки БД: {e}"
        add_activity_log("ERROR", f"Ошибка загрузки БД: {e}")
    else:
        # Если импорт успешен - работаем с БД
        db = None
        try:
            db = SessionLocal()

            log_count = db.query(LogEntry).count()
            recent_logs = get_recent_logs(5)

            task_count = db.query(ModificationTask).count()
            recent_tasks = get_recent_tasks(5)

            context["database"] = {
                "log_entries_total": log_count,
                "modification_tasks_total": task_count,
                "recent_logs": [
                    {
                        "level": log.level,
                        "message": log.message[:100] + "..." if len(log.message) > 100 else log.message,
                        "user_id": log.user_id,
                        "timestamp": log.timestamp.isoformat()
                    }
                    for log in recent_logs
                ],
                "recent_tasks": [
                    {
                        "file": task.file,
                        "status": task.status,
                        "level": task.level,
                        "desc": task.desc[:100] + "..." if len(
                            task.desc) > 100 else task.desc
                    }
                    for task in recent_tasks
                ]
            }
            add_activity_log("INFO", f"Данные БД получены: {log_count} логов, {task_count} задач")

        except Exception as e:
            context["database"]["error"] = f"Ошибка подключения к БД: {e}"
            add_activity_log("ERROR", f"Ошибка подключения к БД: {e}")
        finally:
            if db:
                db.close()

    # 3. Статус системы
    try:
        from config import TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY

        context["system_status"] = {
            "telegram_bot_configured": bool(TELEGRAM_BOT_TOKEN),
            "openai_configured": bool(OPENAI_API_KEY),
            "anthropic_configured": bool(ANTHROPIC_API_KEY),
            "google_configured": bool(GOOGLE_API_KEY),
        }
        add_activity_log("INFO", "Статус системы получен")

    except Exception as e:
        context["system_status"]["error"] = str(e)
        add_activity_log("ERROR", f"Ошибка получения статуса системы: {e}")

    # Форматируем в Markdown
    markdown_output = f"""# Stark AI Project - Technical Context

## 📊 Project Overview
- **Generated**: {context['generated_at']}
- **Python Files**: {context['project'].get('file_count', 'N/A')}
- **Main Modules**: {', '.join(context['project'].get('main_files', []))}
- **Status**: {'✅ Success' if 'error' not in context['project'] else '❌ ' + context['project']['error']}

## 🗄️ Database Status
- **Total Logs**: {context['database'].get('log_entries_total', 'N/A')}
- **Total Tasks**: {context['database'].get('modification_tasks_total', 'N/A')}
- **Status**: {'✅ Connected' if 'error' not in context['database'] else '❌ ' + context['database']['error']}

## 🔧 System Configuration
- **Telegram Bot**: {'✅ Configured' if context['system_status'].get('telegram_bot_configured') else '❌ Not configured'}
- **OpenAI API**: {'✅ Configured' if context['system_status'].get('openai_configured') else '❌ Not configured'}
- **Anthropic API**: {'✅ Configured' if context['system_status'].get('anthropic_configured') else '❌ Not configured'}
- **Google AI API**: {'✅ Configured' if context['system_status'].get('google_configured') else '❌ Not configured'}

## 📁 Project Structure
{context['project'].get('structure', 'N/A')}

## 📋 API Documentation
{context['project'].get('api_documentation', 'N/A')}

## 📊 Recent Activity

### Last 5 Logs:
{chr(10).join(f"- **{log['level']}** {log['timestamp'][11:19]} {log['message']} (user: {log['user_id'] or 'system'})" for log in context['database'].get('recent_logs', [])) if 'recent_logs' in context['database'] else '📭 No log data available'}

### Last 5 Tasks:
{chr(10).join(f"- **{task['status']}** {task['file']} - {task['desc']}" for task in context['database'].get('recent_tasks', [])) if 'recent_tasks' in context['database'] else '📭 No task data available'}

---
*Context automatically generated by Stark AI System*
"""

    add_activity_log("INFO", f"Сгенерирован техконтекст ({len(markdown_output)} символов)")
    return markdown_output


def copy_to_clipboard(content: str, command: str):
    """
    API: Копирование содержимого в буфер обмена
    Вход: content (содержимое), command (имя команды для логирования)
    Выход: None
    Логика: Попытка копирования через pyperclip, fallback в файл при ошибке
    """
    try:
        import pyperclip
        pyperclip.copy(content)
        add_activity_log("INFO", f"{command} скопирован в буфер обмена ({len(content)} символов)")
        print(f"✅ Результат скопирован в буфер обмена ({len(content)} символов)")
    except ImportError:
        # Сохраняем в файл если pyperclip не установлен
        context_file = f"{command}_output.txt"
        with open(context_file, "w", encoding="utf-8") as f:
            f.write(content)
        add_activity_log("WARNING", f"{command} сохранен в {context_file} (pyperclip недоступен)")
        print(f"✅ Результат сохранен в {context_file}!")
        print("📋 Скопируй содержимое файла вручную (Ctrl+A, Ctrl+C)")


def main():
    """
    API: Основная функция запуска сканера проекта
    Вход: None (аргументы командной строки)
    Выход: None (вывод в консоль и буфер обмена)
    Логика: Парсинг аргументов, выполнение соответствующих команд, обработка ошибок
    """
    parser = argparse.ArgumentParser(description='Сканирование и анализ проекта Stark AI')

    # Основные команды
    parser.add_argument('--tree', action='store_true', help='Структура проекта в Markdown → буфер')
    parser.add_argument('--api', action='store_true', help='API документация → буфер')
    parser.add_argument('--fullcode', action='store_true', help='Полный код проекта → буфер')
    parser.add_argument('--context', action='store_true',
                        help='Техконтекст (структура + API + системные данные) → буфер')

    # Дополнительные команды
    parser.add_argument('--code', nargs='+', action='append', metavar=('FILE', 'PROCEDURE'),
                        help='Получить код процедур: --code filename.py procedure1 procedure2 → буфер')
    parser.add_argument('--modify', type=str, metavar='JSON',
                        help='Изменить код (JSON строка): --modify \'[{"file":"f.py","tobe":"code"}]\'')

    # Опциональные параметры
    parser.add_argument('--root', '-r', default='.', help='Корневая директория проекта')

    args = parser.parse_args()
    scanner = ProjectScanner(args.root)

    # Обработка команд
    try:
        if args.tree:
            result = scanner.scan_structure_tree()
            copy_to_clipboard(result, "Дерево структуры")
            return

        elif args.api:
            result = scanner.scan_api_documentation()
            copy_to_clipboard(result, "API документация")
            return

        elif args.fullcode:
            result = scanner.scan_full_code()
            copy_to_clipboard(result, "Полный код")
            return

        elif args.context:
            result = generate_project_context()
            copy_to_clipboard(result, "Технический контекст")
            return

        elif args.code:
            file_procedure_pairs = []
            for code_arg in args.code:
                if len(code_arg) == 1:
                    file_procedure_pairs.append((code_arg[0], None))
                elif len(code_arg) >= 2:
                    filename = code_arg[0]
                    for procedure_name in code_arg[1:]:
                        file_procedure_pairs.append((filename, procedure_name))
                else:
                    print(f"ОШИБКА: Неверный формат: {code_arg}")
                    return

            result = get_specific_code(file_procedure_pairs, args.root)
            print(result)
            return

        elif args.modify:
            print("РЕЖИМ ИЗМЕНЕНИЯ КОДА")
            print("=" * 50)

            try:
                tasks = json.loads(args.modify)
                if not isinstance(tasks, list):
                    print("ОШИБКА: Ожидается список задач")
                    return

                print(f"Обработка {len(tasks)} задач...")
                result = safe_code_modification(tasks)
                result_str = json.dumps(result, ensure_ascii=False, indent=2)
                print("\nРЕЗУЛЬТАТ ИЗМЕНЕНИЙ:")
                print(result_str)

            except Exception as e:
                error_msg = f"ОШИБКА: {e}"
                print(error_msg)
                add_activity_log("ERROR", error_msg)

            return

        # Если нет аргументов - показываем справку
        parser.print_help()

    except Exception as e:
        error_msg = f"Критическая ошибка: {e}"
        print(error_msg)
        add_activity_log("ERROR", error_msg)
        raise


if __name__ == "__main__":
    main()
