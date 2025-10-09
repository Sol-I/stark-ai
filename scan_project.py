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

if __name__ == "__main__":
    print(scan_project_structure('.', 0))
    # project_structure = scan_project_structure('.', 1)
    # full_context = scan_project_structure('.', 2)
    api_context = scan_api_documentation()
    pyperclip.copy(api_context)

