# data_processor.py

import pandas as pd
import re
import logging
from sqlalchemy.engine import Engine

from config import FILE_PATH, DELIMITER, DECIMAL_CHAR, HEADER_ROW_INDEX, DATE_COLUMNS
from db_operations import postgres_upsert_do_nothing, insert_new_types

logger = logging.getLogger(__name__)

def extract_write_off_type(details):
    """Извлекает тип списания между первым словом и кодом 'RUS'."""
    if pd.isna(details):
        return "Неизвестно"
    
    # Регулярное выражение для захвата между первым словом и RUS
    match = re.search(r'^\S+\s+(.*?)\s+RUS', str(details), re.IGNORECASE)
    
    if match:
        return match.group(1).strip()
    else:
        # Резервный вариант, если RUS не найден
        parts = str(details).split()
        if len(parts) > 1:
            return " ".join(parts[1:]).strip()
        return "Неизвестно"

def load_and_preprocess_data():
    """Чтение CSV, очистка и базовая трансформация данных."""
    logger.info("--- 1. Чтение и парсинг CSV с помощью Pandas ---")
    
    try:
        df = pd.read_csv(
            FILE_PATH, sep=DELIMITER, decimal=DECIMAL_CHAR,
            header=HEADER_ROW_INDEX, parse_dates=DATE_COLUMNS, encoding='utf-8',
        )
        logger.info(f"Файл '{FILE_PATH}' успешно загружен. Размер: {df.shape}")
    except Exception as e:
        logger.error(f"❌ Ошибка при чтении файла: {e}")
        raise

    logger.info("\n--- 2. Нормализация данных и категоризация ---")
    
    # А. Переименование столбцов
    rename_mapping = {
        "Дата и время транзакции": "transaction_datetime", "Дата обработки транзакции": "processing_datetime",
        "Детали": "details", "Сумма": "amount", "Сумма в валюте карты": "amount_card_currency",
        "Комиссия": "commission",
    }
    df.rename(columns=rename_mapping, inplace=True)
    
    # Б. Обработка числовых данных и установка внешних ключей
    numeric_cols = ['amount', 'amount_card_currency', 'commission']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.00)

    # Установка константных внешних ключей
    df['source_id'] = 1
    df.dropna(subset=['transaction_datetime', 'amount'], inplace=True)
    
    # В. Извлечение типа списания
    df['write_off_type_name'] = df['details'].apply(extract_write_off_type)
    
    return df

def process_and_load_transactions(df: pd.DataFrame, engine: Engine):
    """Выполняет загрузку типов списания и финальную загрузку транзакций."""
    
    # --- 3. Загрузка уникальных типов в write_off_types ---
    logger.info("\n--- 3. Загрузка/обновление таблицы 'write_off_types' (Проверка уникальности) ---")
    
    unique_types = df['write_off_type_name'].unique()
    df_types_to_insert = pd.DataFrame(unique_types, columns=['name'])
    df_types_to_insert['description'] = None
    df_types_to_insert['is_active'] = True

    # Получение существующих имен для фильтрации
    try:
        existing_types_df = pd.read_sql_table('write_off_types', con=engine, columns=['name'])
        existing_names = set(existing_types_df['name'])
        df_new_types = df_types_to_insert[~df_types_to_insert['name'].isin(existing_names)]

        if df_new_types.empty:
            logger.info("✅ Новых типов списания для добавления не найдено.")
        else:
            insert_new_types(df_new_types, engine) # Используем функцию из db_operations
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке или загрузке типов списания: {e}")
        return # Останавливаем, если не удалось обновить типы

    # --- 4. Получение ID и финальная загрузка в 'transactions' ---
    logger.info("\n--- 4. Получение ID и финальная загрузка в 'transactions' ---")

    try:
        # А. Получение всех ID и имен из БД для сопоставления
        df_type_map = pd.read_sql_table('write_off_types', con=engine, columns=['id', 'name'])
        type_to_id_map = df_type_map.set_index('name')['id'].to_dict()

        # Б. Замена строковых имен на ID
        df['write_off_type_id'] = df['write_off_type_name'].map(type_to_id_map)
        
        # В. Финальная подготовка DataFrame
        df.drop(columns=['write_off_type_name'], inplace=True)
        
        # Выбираем столбцы, соответствующие схеме 'transactions'
        df_final = df[[
            'transaction_datetime', 'processing_datetime', 'details', 'amount',
            'amount_card_currency', 'commission', 'source_id', 'write_off_type_id'
        ]]
        
        # Г. Загрузка в PostgreSQL С ИСПОЛЬЗОВАНИЕМ UPSERT
        df_final.to_sql(
            name='transactions',
            con=engine,
            if_exists='append',
            index=False,
            method=postgres_upsert_do_nothing, # <-- Используем функцию из db_operations
            chunksize=10000
        )
        logger.info("✅ Все транзакции успешно загружены, дубликаты пропущены.")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при загрузке транзакций: {e}")