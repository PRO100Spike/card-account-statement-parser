# models/write_off_type.py

from sqlalchemy import Column, Integer, String, Text, Boolean, TIMESTAMP, Index
from base import Base

class WriteOffType(Base):
    """Таблица типов списаний."""
    __tablename__ = 'write_off_types'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False) 
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, default=Column.DefaultClause('CURRENT_TIMESTAMP')) 
    
    __table_args__ = (
        # Индекс для уникальности, соответствующий логике проекта
        Index('idx_write_off_types_name', 'name', unique=True),
    )

    def __repr__(self):
        return f"<WriteOffType(name='{self.name}')>"