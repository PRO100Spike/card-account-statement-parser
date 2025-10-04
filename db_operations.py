# db_operations.py

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
import pandas as pd
import logging

from config import DATABASE_URL, UNIQUE_UPSERT_COLS # Импорт из нового config.py

# Настройка логирования
logger = logging.getLogger(__name__)

def get_db_engine() -> Engine:
    """Создает и возвращает объект Engine SQLAlchemy."""
    logger.info("Создание подключения к базе данных...")
    return create_engine(DATABASE_URL)

def postgres_upsert_do_nothing(table, conn, keys, data_iter):
    """
    Кастомный метод для to_sql, выполняющий INSERT...ON CONFLICT DO NOTHING.
    Проверка уникальности производится по заданному ключу.
    """
    logger.debug(f"Запуск UPSERT для таблицы {table.table.name}...")
    
    # Подготовка данных в виде словарей
    data = [dict(zip(keys, row)) for row in data_iter]
    
    # Создание выражения INSERT и ON CONFLICT DO NOTHING
    insert_stmt = insert(table.table).values(data)
    
    # Используем столбцы из конфигурации
    on_conflict_stmt = insert_stmt.on_conflict_do_nothing(
        index_elements=UNIQUE_UPSERT_COLS
    )
    
    conn.execute(on_conflict_stmt)
    logger.debug("UPSERT завершен.")

def insert_new_types(df_new_types: pd.DataFrame, engine: Engine):
    """Вставляет новые типы списания в таблицу 'write_off_types'."""
    try:
        # NOTE: Здесь не нужен UPSERT, так как мы фильтруем DataFrame на стороне Pandas
        df_new_types.to_sql(name='write_off_types', con=engine, if_exists='append', index=False)
        logger.info(f"✅ Успешно добавлено {len(df_new_types)} новых типов списания.")
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке новых типов списания: {e}")
        raise