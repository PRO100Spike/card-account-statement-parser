# db_operations.py

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
import pandas as pd

from config import DATABASE_URL, UNIQUE_UPSERT_COLS # Импорт из нового config.py

# Настройка логирования
import logging

logger = logging.getLogger(__name__)

def insert_account_metadata(metadata: dict, engine: Engine):
    """
    Вставляет или обновляет метаданные выписки по счету (UPSERT).
    Использует ON CONFLICT DO UPDATE.
    """
    logger.info("Начало загрузки/обновления метаданных счета в account_statements.")

    # 1. Приведение ключей словаря к именам столбцов в БД
    # Это важно, так как функция parse_account_metadata возвращает ключи в snake_case
    data_to_upsert = {
        'contract_number': metadata.get('номер_контракта'),
        'account_number': metadata.get('номер_счета'),
        'start_date': metadata.get('дата_начала_выписки'),
        'end_date': metadata.get('дата_окончания_выписки'),
        'incoming_balance': metadata.get('входящий_остаток'),
        'total_credit': metadata.get('суммарный_приход'),
        'total_debit': metadata.get('суммарный_расход'),
        'outgoing_balance': metadata.get('исходящий_остаток'),
    }

    # 2. Определение конфликтующих элементов (Уникальный ключ)
    conflict_cols = [
        AccountStatement.account_number, 
        AccountStatement.start_date, 
        AccountStatement.end_date
    ]

    # 3. Определение полей, которые нужно ОБНОВИТЬ при конфликте
    update_cols = {
        'incoming_balance': insert_stmt.excluded.incoming_balance,
        'total_credit': insert_stmt.excluded.total_credit,
        'total_debit': insert_stmt.excluded.total_debit,
        'outgoing_balance': insert_stmt.excluded.outgoing_balance,
        # Обновляем также дату создания, чтобы видеть, когда была последняя загрузка
        'created_at': insert_stmt.excluded.created_at, 
    }
    
    # Создание выражения INSERT
    insert_stmt = insert(AccountStatement).values([data_to_upsert])

    # Создание выражения UPSERT (ON CONFLICT DO UPDATE)
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=conflict_cols,
        set_=update_cols
    )

    try:
        with Session(engine) as session:
            session.execute(upsert_stmt)
            session.commit()
        logger.info("✅ Метаданные счета успешно загружены/обновлены в account_statements.")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при UPSERT метаданных: {e}")
        # Желательно здесь поднять исключение, так как без метаданных транзакции могут быть бесполезны
        raise

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