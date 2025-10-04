import os
import re
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert # Используется для ON CONFLICT DO NOTHING
from dotenv import load_dotenv

# --- КОНФИГУРАЦИЯ ---
load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"

FILE_PATH = 'CardAccountStatement.csv'
DELIMITER = ';' 
DECIMAL_CHAR = ',' 
HEADER_ROW_INDEX = 8 
DATE_COLUMNS = ["Дата и время транзакции", "Дата обработки транзакции"]


# --- ФУНКЦИИ ---

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

# --- ОБНОВЛЕННАЯ ФУНКЦИЯ UPSERT ---
def postgres_upsert_do_nothing(table, conn, keys, data_iter):
    """
    Кастомный метод для to_sql, выполняющий INSERT...ON CONFLICT DO NOTHING.
    Проверка уникальности производится по новому, расширенному ключу.
    """
    # Подготовка данных в виде словарей
    data = [dict(zip(keys, row)) for row in data_iter]
    
    # СТОЛБЦЫ, СОСТАВЛЯЮЩИЕ НОВЫЙ УНИКАЛЬНЫЙ ИНДЕКС:
    unique_cols = [
        'transaction_datetime', 
        'amount', 
        'source_id',       
        'write_off_type_id' 
    ] 
    
    # Создание выражения INSERT и ON CONFLICT DO NOTHING
    insert_stmt = insert(table.table).values(data)
    
    on_conflict_stmt = insert_stmt.on_conflict_do_nothing(
        index_elements=unique_cols
    )
    
    conn.execute(on_conflict_stmt)
# ------------------------------------

# --- ГЛАВНАЯ ЛОГИКА ---
def process_and_load_transactions():
    print("--- 1. Чтение и парсинг CSV с помощью Pandas ---")
    
    try:
        df = pd.read_csv(
            FILE_PATH, sep=DELIMITER, decimal=DECIMAL_CHAR,
            header=HEADER_ROW_INDEX, parse_dates=DATE_COLUMNS, encoding='utf-8', 
        )
        print(f"Файл '{FILE_PATH}' успешно загружен. Размер: {df.shape}")
        
    except Exception as e:
        print(f"❌ Ошибка при чтении файла: {e}")
        return

    # 2. Нормализация данных и категоризация
    print("\n--- 2. Нормализация данных и категоризация ---")
    
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

    df['source_id'] = 1 
    df.dropna(subset=['transaction_datetime', 'amount'], inplace=True)
    
    # В. Извлечение типа списания
    df['write_off_type_name'] = df['details'].apply(extract_write_off_type)
    
    # --- 3. Загрузка уникальных типов в write_off_types (Проверка уникальности) ---
    engine = create_engine(DATABASE_URL)
    
    unique_types = df['write_off_type_name'].unique()
    df_types_to_insert = pd.DataFrame(unique_types, columns=['name'])
    df_types_to_insert['description'] = None
    df_types_to_insert['is_active'] = True
    
    print("\n--- 3. Загрузка/обновление таблицы 'write_off_types' (Проверка уникальности) ---")

    try:
        existing_types_df = pd.read_sql_table('write_off_types', con=engine, columns=['name'])
        existing_names = set(existing_types_df['name'])
        
        # Фильтруем, оставляя только те, которых нет в БД
        df_new_types = df_types_to_insert[~df_types_to_insert['name'].isin(existing_names)]

        if df_new_types.empty:
            print("✅ Новых типов списания для добавления не найдено.")
        else:
            df_new_types.to_sql(name='write_off_types', con=engine, if_exists='append', index=False)
            print(f"✅ Успешно добавлено {len(df_new_types)} новых типов списания.")

    except Exception as e:
        print(f"❌ Ошибка при проверке или загрузке типов списания: {e}")


    # --- 4. Получение ID и финальная загрузка в 'transactions' ---
    print("\n--- 4. Получение ID и финальная загрузка в 'transactions' ---")

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
            method=postgres_upsert_do_nothing, # <-- Используется функция с новым ключом
            chunksize=10000 
        )
        print("✅ Все транзакции успешно загружены, дубликаты пропущены.")

    except Exception as e:
        print(f"❌ Критическая ошибка при загрузке транзакций: {e}")

if __name__ == "__main__":
    process_and_load_transactions()