# config.py

import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env
load_dotenv()

# --- КОНФИГУРАЦИЯ БАЗЫ ДАННЫХ ---
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"

# --- КОНФИГУРАЦИЯ ФАЙЛА И ПАРСИНГА ---
FILE_PATH = './data/CardAccountStatement.csv'
DELIMITER = ';'
DECIMAL_CHAR = ','
HEADER_ROW_INDEX = 8
DATE_COLUMNS = ["Дата и время транзакции", "Дата обработки транзакции"]

# СТОЛБЦЫ ДЛЯ УНИКАЛЬНОГО КЛЮЧА UPSERT
UNIQUE_UPSERT_COLS = [
    'transaction_datetime',
    'amount',
    'source_id',
    'write_off_type_id'
]