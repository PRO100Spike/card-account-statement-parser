# Файл: data_analysis/models.py (добавляем класс WriteOffType)

from sqlalchemy import Column, Integer, String, Text, Boolean, Numeric, TIMESTAMP, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects import postgresql 

Base = declarative_base()

# 2. Определение Модели Источников (Sources) - оставлено для совместимости с FK
class Source(Base):
    __tablename__ = 'sources'
    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    # ...

# НОВАЯ МОДЕЛЬ ДЛЯ ТИПОВ СПИСАНИЯ
class WriteOffType(Base):
    __tablename__ = 'write_off_types'
    
    # id SERIAL PRIMARY KEY (автоматически реализуется как Integer, primary_key=True)
    id = Column(Integer, primary_key=True) 
    
    # name VARCHAR(100) NOT NULL
    name = Column(String(100), nullable=False, unique=True) # Добавим unique=True
    
    # description TEXT
    description = Column(Text)
    
    # is_active BOOLEAN DEFAULT TRUE
    is_active = Column(Boolean, default=True) 

    def __repr__(self):
        return f"<WriteOffType(name='{self.name}')>"

# 3. Определение Модели Транзакции (Transactions) - без изменений
class Transaction(Base):
    # ... (Весь ваш предыдущий код Transaction) ...
    __tablename__ = 'transactions'
    # ...
    # __table_args__ = (
    #     PrimaryKeyConstraint(
    #         'transaction_datetime', 
    #         'amount', 
    #         'source_id', 
    #         name='transactions_pk'
    #     ),
    # )
    # ...