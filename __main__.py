# __main__.py (Обновленный координатор)

import sys
import logging

# Импортируем функции из новых модулей
from db_operations import get_db_engine
from data_processor import load_and_preprocess_data, process_and_load_transactions

# Настройка логирования (для вывода сообщений в консоль)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """
    Точка входа в приложение.
    """
    logger.info("--- Запуск Card Account Statement Parser ---")
    
    try:
        # 1. Загрузка и предобработка данных (Pandas)
        df = load_and_preprocess_data()
        
        if df is None or df.empty:
            logger.warning("Нет данных для обработки. Завершение работы.")
            return

        # 2. Создание подключения к БД
        engine = get_db_engine()
        
        # 3. Загрузка в БД (типы и транзакции)
        process_and_load_transactions(df, engine)
        
    except Exception as e:
        logger.critical(f"\nКритическая ошибка приложения: {e}")
        sys.exit(1)

    logger.info("--- Процесс завершен ---")

if __name__ == "__main__":
    main()