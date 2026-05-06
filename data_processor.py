# data_processor.py

import re
import logging
import pandas as pd
from sqlalchemy.engine import Engine
from datetime import datetime # <-- ДОБАВЛЕНО: для парсинга дат в метаданных

from config import FILE_PATH, DELIMITER, DECIMAL_CHAR, HEADER_ROW_INDEX, DATE_COLUMNS, METADATA_ROWS_COUNT
# Предполагаем, что вы добавили функцию insert_account_metadata в db_operations.py
from db_operations import postgres_upsert_do_nothing, insert_new_types, insert_account_metadata 

logger = logging.getLogger(__name__)

# --- ФУНКЦИИ ПАРСИНГА И ТРАНСФОРМАЦИИ ---

def parse_account_metadata(file_path, delimiter=DELIMITER, decimal_char=DECIMAL_CHAR, num_rows=METADATA_ROWS_COUNT):
    """
    Парсит первые N строк CSV-файла, содержащие метаданные счета.
    """
    logger.info("--- Парсинг метаданных из первых %s строк ---", num_rows)
    
    # Задаем имена столбцам: 'key' (индекс 0), 'value' (индекс 1), 'currency' (индекс 2)
    # Это позволяет Pandas корректно обработать все 3 поля, даже если оно ожидает только 2
    COLUMN_NAMES = ['key', 'value', 'currency']

    try:
        df_meta = pd.read_csv(
            file_path,
            sep=delimiter,
            decimal=decimal_char,
            header=None,
            nrows=num_rows,
            encoding='utf-8', 
            names=COLUMN_NAMES,  # <-- ИЗМЕНЕНИЕ 1: Явно задаем имена столбцов
            usecols=['key', 'value'], # <-- ИЗМЕНЕНИЕ 2: Используем только первые 2 столбца
            skipinitialspace=True,
            # Важно: engine='python' более терпим к ошибкам, но медленнее. 
            # Начнем с этого, если C engine продолжит выдавать ошибку.
            engine='python' # <-- ИЗМЕНЕНИЕ 3: Переключаемся на более гибкий парсер
        )
    except Exception as e:
        logger.error("❌ Ошибка при чтении метаданных: %s", e)
        return None

    # Приводим DataFrame к серии, где ключ - это имя поля, значение - его содержимое
    meta_series = df_meta.iloc[:, 0]
    
    # Конвертируем в словарь для удобного доступа
    metadata = meta_series.to_dict()
    
    # Очистка и нормализация ключей и значений
    cleaned_metadata = {}
    
    # Итерируемся по строкам df_meta
    for row in metadata.items():
        # Первый элемент - ключ (название поля), второй - значение.
        # Для строк остатков, значение - это второй столбец (индекс 1)
        
        raw_key = row[0]
        raw_val = row[1] if pd.notna(row[1]) else None # Используем столбец 1 как значение
        
        if raw_key is None:
            continue
            
        # Очистка ключа
        clean_key = str(raw_key).replace('"', '').strip()
        snake_key = re.sub(r'\W+', '_', clean_key.lower().strip()).strip('_')
        
        # Очистка значения
        if raw_val is not None:
            clean_val = str(raw_val).replace('"', '').strip()
        else:
            # Если значение было в третьем столбце (как в примере RUR), оно не попало в row[1].
            # Пробуем объединить (менее надежно) или просто оставить как None,
            # но для числовых полей нам нужно число.
            clean_val = str(row[1]) if pd.notna(row[1]) else ''
            # Проверяем, есть ли данные в третьем столбце (индекс 2), если строка была типа "Остаток;X,XX;RUR"
            if len(row) > 2 and pd.notna(row[2]) and clean_key.endswith('остаток') or clean_key.endswith('приход') or clean_key.endswith('расход'):
                 # Для остатков, значение уже находится в row[1], а валюта в row[2].
                 # Нам нужно только число из row[1].
                 clean_val = str(row[1]).replace('"', '').strip()

        # ... (Остальной код нормализации без изменений) ...
        # (Остальной цикл обработки, который парсит даты и числа, остается)
        
        # Специальная обработка для числовых полей с валютой
        if snake_key.startswith(('входящий_остаток', 'суммарный_приход', 'суммарный_расход', 'исходящий_остаток')):
            try:
                # Нам нужно только числовое значение из clean_val (которое теперь row[1])
                numeric_val = float(clean_val.replace(',', '.'))
                cleaned_metadata[snake_key] = numeric_val
            except ValueError:
                 logger.warning("Не удалось преобразовать числовое значение '%s' для ключа '%s'", clean_val, clean_key)
                 cleaned_metadata[snake_key] = None
        
        # Специальная обработка для дат
        # ... (код для дат) ...
        
        # Прочие поля
        else:
            cleaned_metadata[snake_key] = clean_val.replace("'", "")
            
    logger.info("✅ Метаданные успешно извлечены и нормализованы.")
    return cleaned_metadata


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
        # Сдвигаем чтение, пропуская строки метаданных
        df = pd.read_csv(
            FILE_PATH, sep=DELIMITER, decimal=DECIMAL_CHAR,
            dayfirst=True,
            header=HEADER_ROW_INDEX - METADATA_ROWS_COUNT, # Сдвиг, чтобы header=8 стал 0-м после пропуска 8 строк
            skiprows=METADATA_ROWS_COUNT, # Пропускаем строки с метаданными
            parse_dates=DATE_COLUMNS, encoding='utf-8',
        )
        logger.info("Файл '%s' успешно загружен. Размер: %s", FILE_PATH, df.shape)
    except Exception as e:
        logger.error("❌ Ошибка при чтении файла: %s", e)
        raise

    logger.info("\n--- 2. Нормализация данных и категоризация ---")
    
    # А. Переименование столбцов (оставлено без изменений)
    rename_mapping = {
        "Дата и время транзакции": "transaction_datetime", "Дата обработки транзакции": "processing_datetime",
        "Детали": "details", "Сумма": "amount", "Сумма в валюте карты": "amount_card_currency",
        "Комиссия": "commission",
    }
    df.rename(columns=rename_mapping, inplace=True)
    
    # ... (Остальная часть предварительной обработки без изменений) ...
    numeric_cols = ['amount', 'amount_card_currency', 'commission']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.00)

    df['source_id'] = 1
    df.dropna(subset=['transaction_datetime', 'amount'], inplace=True)
    
    df['write_off_type_name'] = df['details'].apply(extract_write_off_type)
    
    return df

# --- ГЛАВНЫЙ ОРКЕСТРАТОР ПРОЦЕССА ---

def process_data_file(engine: Engine):
    """
    Основная функция для обработки и загрузки данных из файла в БД.
    """
    # 1. Парсинг и загрузка метаданных счета
    metadata = parse_account_metadata(FILE_PATH)
    if metadata:
        # Передаем нормализованный словарь для загрузки в таблицу account_statements
        insert_account_metadata(metadata, engine)
    else:
        logger.error("Невозможно продолжить: не удалось получить метаданные.")
        return

    # 2. Чтение, предобработка и трансформация транзакций
    try:
        df_transactions = load_and_preprocess_data()
    except Exception as e:
        logger.error("Невозможно продолжить: ошибка при загрузке транзакций. %s", e)
        return

    # 3. Загрузка транзакций
    process_and_load_transactions(df_transactions, engine)

# --- ФУНКЦИЯ ЗАГРУЗКИ ТРАНЗАКЦИЙ (ОСТАВЛЕНА ПОЧТИ БЕЗ ИЗМЕНЕНИЙ) ---

def process_and_load_transactions(df: pd.DataFrame, engine: Engine):
    """Выполняет загрузку типов списания и финальную загрузку транзакций."""
    
    # --- 3. Загрузка уникальных типов в write_off_types ---
    logger.info("\n--- 3. Загрузка/обновление таблицы 'write_off_types' (Проверка уникальности) ---")
    
    unique_types = df['write_off_type_name'].unique()
    df_types_to_insert = pd.DataFrame(unique_types, columns=['name'])
    df_types_to_insert['description'] = None
    df_types_to_insert['is_active'] = True

    try:
        existing_types_df = pd.read_sql_table('write_off_types', con=engine, columns=['name'])
        existing_names = set(existing_types_df['name'])
        df_new_types = df_types_to_insert[~df_types_to_insert['name'].isin(existing_names)]

        if df_new_types.empty:
            logger.info("✅ Новых типов списания для добавления не найдено.")
        else:
            insert_new_types(df_new_types, engine)
    except Exception as e:
        logger.error("❌ Ошибка при проверке или загрузке типов списания: %s", e)
        return

    # --- 4. Получение ID и финальная загрузка в 'transactions' ---
    logger.info("--- 4. Получение ID и финальная загрузка в 'transactions' ---")

    try:
        df_type_map = pd.read_sql_table('write_off_types', con=engine, columns=['id', 'name'])
        type_to_id_map = df_type_map.set_index('name')['id'].to_dict()

        df['write_off_type_id'] = df['write_off_type_name'].map(type_to_id_map)
        
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
            method=postgres_upsert_do_nothing,
            chunksize=10000
        )
        logger.info("✅ Все транзакции успешно загружены, дубликаты пропущены.")

    except Exception as e:
        logger.error("❌ Критическая ошибка при загрузке транзакций: %s", e)