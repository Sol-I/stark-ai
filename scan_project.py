import pyperclip
import re
from pathlib import Path
import argparse


class ProjectScanner:
    def __init__(self, root_dir='.'):
        self.root_dir = Path(root_dir).absolute()
        self.ignore_patterns = [
            '__pycache__', '.git', '.idea', '.vscode', 'venv', 'env',
            'node_modules', '.pytest_cache', '.mypy_cache', 'dist', 'build',
            '*.pyc', '*.pyo', '*.so', '*.dll', '*.exe'
        ]

    def should_ignore(self, path):
        """Проверяет, нужно ли игнорировать файл/папку"""
        path_str = str(path)

        # Игнорируем скрытые файлы/папки (начинающиеся с .)
        if any(part.startswith('.') and part not in ['.', '..'] for part in path.parts):
            # Но не игнорируем .env файлы и некоторые конфиги
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

    def clean_python_code(self, content):
        """Очищает Python код для контекста LLM"""
        lines = content.split('\n')
        cleaned_lines = []

        for line in lines:
            stripped = line.rstrip()

            # Удаляем пустые строки в конце файла
            if not stripped and not cleaned_lines:
                continue

            # Удаляем однострочные комментарии (кроме shebang)
            if stripped.startswith('#') and not stripped.startswith('#!'):
                # Сохраняем только важные комментарии (TODO, FIXME, etc.)
                if any(marker in stripped.upper() for marker in ['TODO', 'FIXME', 'HACK', 'NOTE', 'IMPORTANT']):
                    cleaned_lines.append(stripped)
                continue

            # Удаляем импорты (они обычно не важны для понимания логики)
            if re.match(r'^\s*(from|import)\s+\S', stripped):
                continue

            cleaned_lines.append(stripped)

        # Удаляем множественные пустые строки
        result_lines = []
        prev_empty = False
        for line in cleaned_lines:
            current_empty = not line.strip()
            if current_empty and prev_empty:
                continue
            result_lines.append(line)
            prev_empty = current_empty

        # Убираем пустые строки в конце
        while result_lines and not result_lines[-1].strip():
            result_lines.pop()

        return '\n'.join(result_lines)

    def clean_other_content(self, content, file_extension):
        """Очищает содержимое других типов файлов"""
        lines = content.split('\n')
        cleaned_lines = []

        for line in lines:
            stripped = line.rstrip()

            # Для JSON, YAML, TOML - сохраняем как есть, но убираем пустые строки
            if file_extension in ['.json', '.yaml', '.yml', '.toml']:
                if stripped:
                    cleaned_lines.append(stripped)
            # Для Markdown - немного очищаем
            elif file_extension == '.md':
                cleaned_lines.append(stripped)
            # Для остальных - убираем только множественные пустые строки
            else:
                cleaned_lines.append(stripped)

        # Убираем множественные пустые строки
        result_lines = []
        prev_empty = False
        for line in cleaned_lines:
            current_empty = not line.strip()
            if current_empty and prev_empty:
                continue
            result_lines.append(line)
            prev_empty = current_empty

        return '\n'.join(result_lines)

    def get_file_content(self, file_path):
        """Читает и очищает содержимое файла"""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')

            if file_path.suffix == '.py':
                return self.clean_python_code(content)
            else:
                return self.clean_other_content(content, file_path.suffix)

        except Exception as e:
            return f"[Ошибка чтения файла: {e}]"

    def scan_structure_markdown(self):
        """Режим 0: Структура в формате Markdown для пользователя"""
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
        return "\n".join(output)

    def scan_structure_context(self):
        """Режим 1: Структура для контекста LLM"""
        output = ["PROJECT STRUCTURE:"]

        def scan_directory(directory, level=0):
            try:
                items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))

                for item in items:
                    if self.should_ignore(item):
                        continue

                    indent = "  " * level
                    if item.is_dir():
                        output.append(f"{indent}{item.name}/")
                        scan_directory(item, level + 1)
                    else:
                        output.append(f"{indent}{item.name}")

            except PermissionError:
                output.append(f"{'  ' * level}[Permission denied]")

        scan_directory(self.root_dir)
        return "\n".join(output)

    def scan_full_context(self):
        """Режим 2: Полная структура с содержимым файлов для контекста LLM"""
        output = ["PROJECT ANALYSIS:"]

        # Сначала структура
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

        # Затем содержимое важных файлов
        output.append("FILE CONTENTS:")

        # Приоритетные файлы сначала
        priority_files = []
        other_files = []

        for file_path in file_paths:
            if file_path.suffix in ['.py', '.md', '.txt', '.json', '.yaml', '.yml', '.toml']:
                priority_files.append(file_path)
            else:
                other_files.append(file_path)

        # Обрабатываем приоритетные файлы
        for file_path in priority_files:
            output.append(f"\n--- FILE: {file_path.relative_to(self.root_dir)} ---")
            content = self.get_file_content(file_path)
            if content.strip():
                output.append(content)
            else:
                output.append("[File is empty or contains only comments/imports]")

        # Обрабатываем остальные файлы (только если они небольшие)
        for file_path in other_files:
            try:
                file_size = file_path.stat().st_size
                if file_size < 5000:  # Только маленькие файлы
                    output.append(f"\n--- FILE: {file_path.relative_to(self.root_dir)} ---")
                    content = self.get_file_content(file_path)
                    if content.strip():
                        output.append(content[:1000])  # Ограничиваем размер
            except:
                pass

        return "\n".join(output)

    def scan_project(self, type_output=None):
        """Основная процедура сканирования"""
        if type_output is None or type_output == 0:
            return self.scan_structure_markdown()
        elif type_output == 1:
            return self.scan_structure_context()
        elif type_output == 2:
            return self.scan_full_context()
        else:
            raise ValueError("type_output должен быть 0, 1 или 2")


def main():
    """Запуск из PyCharm или командной строки"""
    parser = argparse.ArgumentParser(description='Сканирование структуры проекта')
    parser.add_argument('--root', '-r', default='.', help='Корневая директория проекта')
    parser.add_argument('--type', '-t', type=int, choices=[0, 1, 2], default=0,
                        help='Тип вывода: 0-Markdown, 1-Структура для LLM, 2-Полный контекст для LLM')
    parser.add_argument('--output', '-o', help='Файл для сохранения результата')

    args = parser.parse_args()

    scanner = ProjectScanner(args.root)
    result = scanner.scan_project(args.type)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"Результат сохранен в: {args.output}")
    else:
        print(result)


# Функции для удобного импорта
def scan_project_structure(root_dir='.', type_output=0):
    """
    Сканирует структуру проекта

    Args:
        root_dir (str): Корневая директория
        type_output (int): Тип вывода (0, 1, 2)

    Returns:
        str: Отформатированная структура проекта
    """
    scanner = ProjectScanner(root_dir)
    return scanner.scan_project(type_output)


def save_project_context(root_dir='.', output_file='project_context.txt', type_output=2):
    """
    Сохраняет контекст проекта в файл

    Args:
        root_dir (str): Корневая директория
        output_file (str): Файл для сохранения
        type_output (int): Тип вывода (0, 1, 2)
    """
    scanner = ProjectScanner(root_dir)
    result = scanner.scan_project(type_output)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(result)

    print(f"Контекст проекта сохранен в: {output_file}")
    print(f"Размер: {len(result)} символов")


def extract_api_documentation(file_path):
    """
    API: Извлечение API документации из файлов проекта
    Вход: file_path (путь к файлу)
    Выход: str (отформатированная документация)
    Логика: Анализирует Python файлы, извлекает классы и функции с докстрингами
    """
    try:
        content = file_path.read_text(encoding='utf-8')

        # Ищем классы и функции с докстрингами
        classes = re.findall(r'class (\w+).*?"""(.*?)"""', content, re.DOTALL)
        functions = re.findall(r'def (\w+)\(.*?"""(.*?)"""', content, re.DOTALL)

        docs = []
        if classes:
            docs.append(f"CLASSES in {file_path.name}:")
            for class_name, docstring in classes:
                docs.append(f"  {class_name}: {docstring.strip()[:100]}...")

        if functions:
            docs.append(f"FUNCTIONS in {file_path.name}:")
            for func_name, docstring in functions:
                docs.append(f"  {func_name}: {docstring.strip()[:100]}...")

        return "\n".join(docs) if docs else f"[No API docs in {file_path.name}]"

    except Exception as e:
        return f"[Error reading {file_path.name}: {e}]"


def scan_api_documentation(root_dir='.'):
    """
    API: Сканирование API документации проекта
    Вход: root_dir (корневая директория)
    Выход: str (структурированная документация всех API)
    Логика: Рекурсивно обходит файлы, извлекает документацию для контекста LLM
    """
    scanner = ProjectScanner(root_dir)

    output = ["PROJECT API DOCUMENTATION:"]
    output.append("=" * 50)

    root_path = Path(root_dir)
    python_files = list(root_path.rglob('*.py'))

    for file_path in python_files:
        if scanner.should_ignore(file_path):
            continue

        api_docs = extract_api_documentation(file_path)
        if api_docs:
            output.append(f"\n--- {file_path.relative_to(root_path)} ---")
            output.append(api_docs)

    return "\n".join(output)


def get_specific_code(file_procedure_pairs, root_dir='.'):
    """
    API: Получение полного кода конкретных процедур или файлов
    Вход: file_procedure_pairs - список кортежей [(filename, procedure_name), ...]
    Выход: str (код процедур/файлов) + копирует в буфер обмена
    Логика: Ищет указанные файлы и процедуры, возвращает их полный код
    """
    scanner = ProjectScanner(root_dir)
    output = []

    for file_spec in file_procedure_pairs:
        if isinstance(file_spec, tuple):
            filename, procedure_name = file_spec
        else:
            filename = file_spec
            procedure_name = None

        # Ищем файл
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
                # Ищем конкретную процедуру
                procedure_code = extract_procedure_code(content, procedure_name, filename)
                if procedure_code:
                    output.append(f"# Файл: {filename}\n# Процедура: {procedure_name}\n{procedure_code}")
                else:
                    output.append(f"# Процедура '{procedure_name}' не найдена в файле {filename}")
            else:
                # Возвращаем весь файл
                output.append(f"# Файл: {filename}\n{content}")

        except Exception as e:
            output.append(f"# Ошибка чтения {filename}: {e}")

    result = "\n\n".join(output)

    # Копируем в буфер обмена
    if result.strip():
        try:
            import pyperclip
            pyperclip.copy(result)
            print(f"✅ Код скопирован в буфер обмена ({len(result)} символов)")
        except ImportError:
            print("❌ Pyperclip не установлен, буфер обмена недоступен")

    return result


def extract_procedure_code(content, procedure_name, filename):
    """
    Извлекает код конкретной процедуры из содержимого файла
    """
    lines = content.split('\n')
    in_procedure = False
    procedure_lines = []
    indent_level = 0
    procedure_start = None

    # Паттерны для поиска процедуры
    patterns = [
        f"def {procedure_name}(",  # Обычная функция
        f"async def {procedure_name}(",  # Асинхронная функция
        f"class {procedure_name}",  # Класс
        f"class {procedure_name}(",  # Класс с наследованием
    ]

    for i, line in enumerate(lines):
        # Проверяем начало процедуры
        if not in_procedure and any(line.strip().startswith(pattern) for pattern in patterns):
            in_procedure = True
            procedure_start = i
            # Определяем базовый отступ
            indent_level = len(line) - len(line.lstrip())
            procedure_lines.append(line)
            continue

        if in_procedure:
            # Проверяем конец процедуры (меньший отступ или конец файла)
            current_indent = len(line) - len(line.lstrip()) if line.strip() else indent_level + 1

            if current_indent <= indent_level and line.strip() and i > procedure_start:
                # Это начало следующей процедуры или конец
                break

            procedure_lines.append(line)

    return '\n'.join(procedure_lines) if procedure_lines else ""


def create_llm_prompt(project_context):
    """
    Создает промпт для LLM с инструкциями по запросу дополнительного кода
    """
    prompt = f"""
{project_context}

=== ИНСТРУКЦИЯ ДЛЯ LLM ===

Если тебе нужен код конкретной процедуры или файла для более точного ответа, 
попроси пользователя выполнить в терминале PyCharm:

python scan_project.py --code "filename.py" "procedure_name"

Примеры:
- Получить весь файл: python scan_project.py --code "agent_core.py"
- Получить конкретную процедуру: python scan_project.py --code "agent_core.py" "process_message"
- Получить несколько процедур: python scan_project.py --code "agent_core.py" "process_message" --code "server.py" "chat_endpoint"

После выполнения команды код будет скопирован в буфер обмена и пользователь сможет 
вставить его в следующий запрос.

Продолжи работу с доступной информацией. Если конкретный код не требуется, 
не упоминай эту инструкцию.
"""
    return prompt


def main():
    """Запуск из PyCharm или командной строки"""
    parser = argparse.ArgumentParser(description='Сканирование структуры проекта')
    parser.add_argument('--root', '-r', default='.', help='Корневая директория проекта')
    parser.add_argument('--type', '-t', type=int, choices=[0, 1, 2, 3], default=0,
                        help='Тип вывода: 0-Markdown, 1-Структура для LLM, 2-Полный контекст для LLM, 3-API документация')
    parser.add_argument('--output', '-o', help='Файл для сохранения результата')

    # Простой вариант для получения кода - принимает ровно 2 аргумента
    parser.add_argument('--code', nargs=2, metavar=('FILE', 'PROCEDURE'),
                        help='Получить код процедуры: --code filename.py procedure_name')

    args = parser.parse_args()

    # Режим получения конкретного кода
    if args.code:
        filename, procedure_name = args.code
        print(f"🔍 Поиск кода: {filename} -> {procedure_name}")
        result = get_specific_code([(filename, procedure_name)], args.root)
        print(result)
        return

    # Обычные режимы сканирования
    scanner = ProjectScanner(args.root)
    result = scanner.scan_project(args.type)

    # Добавляем промпт для LLM в конец (кроме режима 0)
    if args.type != 0:
        result = create_llm_prompt(result)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"Результат сохранен в: {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    main()

