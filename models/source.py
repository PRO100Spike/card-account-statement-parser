# models/source.py

from sqlalchemy import Column, Integer, String
from base import Base # Импортируем Base из родительского каталога (base.py)

class Source(Base):
    """Таблица источников данных."""
    __tablename__ = 'sources'
    
    id = Column(Integer, primary_key=True)
    code = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    
    def __repr__(self):
        return f"<Source(id={self.id}, code='{self.code}')>"