# check_db.py
from core.services.database.database import SessionLocal, engine
from sqlalchemy import inspect

inspector = inspect(engine)
print('ТАБЛИЦЫ В БАЗЕ ДАННЫХ:')
for table_name in inspector.get_table_names():
    print(f'Таблица: {table_name}')
    for column in inspector.get_columns(table_name):
        print(f'   Колонка: {column["name"]} ({column["type"]})')
    print()