# __main__.py (Обновленный координатор)

import sys
import logging

# Импортируем функции из новых модулей
from db_operations import get_db_engine
from data_processor import load_and_preprocess_data, process_and_load_transactions, parse_account_metadata

from config import FILE_PATH

# Настройка логирования (для вывода сообщений в консоль)

class ColoredFormatter(logging.Formatter):
    # ANSI коды для цветов
    grey = "\x1b[38;20m"
    blue = "\x1b[34;20m"
    red = "\x1b[31;20m"
    yellow = "\x1b[33;20m"
    reset = "\x1b[0m"
    fmt = "%(levelname)s - %(message)s"

    def format(self, record):
        colors = {
            logging.INFO: self.blue,
            logging.WARNING: self.yellow,
            logging.ERROR: self.red,
        }
        log_fmt = colors.get(record.levelno, self.grey) + self.fmt + self.reset
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# Настройка КОРНЕВОГО логгера
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter())
root_logger = logging.getLogger() # Получаем корневой логгер (без имени)
root_logger.addHandler(handler)
root_logger.setLevel(logging.INFO)

# Создаем локальный логгер для main
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

        parse_account_metadata(FILE_PATH)
        
    except Exception as e:
        logger.critical("Критическая ошибка приложения: %s", e)
        sys.exit(1)

    logger.info("--- Процесс завершен ---")

if __name__ == "__main__":
    main()