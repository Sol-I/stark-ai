# init_database.py - пересоздаем таблицы
from database import init_db

if __name__ == "__main__":
    init_db()
    print("🎉 База данных обновлена! Добавлена таблица modification_tasks")