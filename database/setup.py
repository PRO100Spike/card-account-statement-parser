# database/setup.py

import os
from sqlalchemy import create_engine
from alembic.config import Config
from alembic import command

# ИМПОРТ ВАШЕЙ БАЗОВОЙ МОДЕЛИ (из base.py)
# from ..base import Base 

def get_database_url():
    """Получает URL базы данных из переменной окружения или использует значение по умолчанию."""
    # Убедитесь, что эта строка соответствует тому, как вы храните URL БД
    return os.environ.get("DATABASE_URL", "sqlite:///./local_db.sqlite")

def initialize_db(database_url: str):
    """
    Инициализирует подключение к базе данных и запускает миграции Alembic.
    """
    print(f"Инициализация базы данных по URL: {database_url}")
    
    # 1. Создание подключения (Engine)
    engine = create_engine(database_url)
    
    # 2. Запуск миграций Alembic
    # Убедитесь, что alembic.ini находится в корневой директории
    alembic_cfg = Config("alembic.ini")
    
    # Это выполняет миграцию до последней версии
    print("Запуск миграций Alembic...")
    command.upgrade(alembic_cfg, "head")
    print("Миграции Alembic завершены.")
    
    return engine

# Дополнительно: можно добавить здесь функцию для создания Session
# def get_session(engine):
#     # ...