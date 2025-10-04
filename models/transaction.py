# models/transaction.py

from sqlalchemy import Column, Integer, Text, Numeric, TIMESTAMP, ForeignKey, PrimaryKeyConstraint, Index
from base import Base

class Transaction(Base):
    """Основная таблица транзакций."""
    __tablename__ = 'transactions'
    
    # Поля с данными
    transaction_datetime = Column(TIMESTAMP, nullable=False)
    processing_datetime = Column(TIMESTAMP, nullable=False)
    details = Column(Text)
    amount = Column(Numeric(15, 2), nullable=False)
    amount_card_currency = Column(Numeric(15, 2))
    commission = Column(Numeric(15, 2), default=0.00)

    # Внешние ключи
    source_id = Column(Integer, ForeignKey('sources.id'), nullable=False)
    write_off_type_id = Column(Integer, ForeignKey('write_off_types.id'), nullable=False)

    __table_args__ = (
        # Primary Key, используемый для UPSERT (ON CONFLICT)
        PrimaryKeyConstraint(
            'transaction_datetime', 
            'amount', 
            'source_id', 
            'write_off_type_id', 
            name='transactions_pk'
        ),
        # Индексы для ускорения выборок
        Index('idx_transactions_date', transaction_datetime),
        Index('idx_transactions_source', source_id),
        Index('idx_transactions_writeoff', write_off_type_id)
    )

    def __repr__(self):
        return f"<Transaction(dt={self.transaction_datetime}, amount={self.amount})>"