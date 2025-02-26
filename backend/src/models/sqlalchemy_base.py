"""SQLAlchemy base model class."""

from typing import Any, Dict, Optional
from datetime import datetime
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy import Column, DateTime, String, Integer, Boolean, JSON
from sqlalchemy.orm import registry
from ..types import JSONValue

mapper_registry = registry()
Base = declarative_base()

class SQLAlchemyBaseModel:
    """Base model for SQLAlchemy models."""
    
    # Make tablename automatically convert CamelCase to snake_case
    @declared_attr
    def __tablename__(cls) -> str:  # type: ignore
        """Generate table name from class name."""
        return ''.join(['_' + c.lower() if c.isupper() else c
                       for c in cls.__name__]).lstrip('_')
    
    # Common columns for all models
    id: str = Column(String, primary_key=True)
    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )
    updated_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    metadata_: Optional[Dict[str, JSONValue]] = Column(
        'metadata',
        JSON,
        nullable=True,
        default=dict
    )
    is_active: bool = Column(Boolean, nullable=False, default=True)
    version: int = Column(Integer, nullable=False, default=1)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary.
        
        Returns:
            Dictionary representation of model
        """
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns  # type: ignore
        }
        
    def update(self, data: Dict[str, Any]) -> None:
        """Update model attributes.
        
        Args:
            data: Dictionary of attributes to update
        """
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.version += 1
        
    @property
    def metadata(self) -> Dict[str, JSONValue]:
        """Get metadata dictionary.
        
        Returns:
            Metadata dictionary
        """
        return self.metadata_ or {}
        
    def update_metadata(self, data: Dict[str, JSONValue]) -> None:
        """Update metadata dictionary.
        
        Args:
            data: Dictionary of metadata to update
        """
        current = self.metadata
        current.update(data)
        self.metadata_ = current
        
    def __repr__(self) -> str:
        """Get string representation of model.
        
        Returns:
            String representation
        """
        return f"<{self.__class__.__name__}(id={self.id})>"

class SQLAlchemyBase(SQLAlchemyBaseModel, Base):
    """Base class for SQLAlchemy models with metadata."""
    __abstract__ = True

class SQLAlchemyTimestampedModel(SQLAlchemyBaseModel):
    """Base model with only timestamp fields."""
    __abstract__ = True
    
    # Remove other fields from base model
    id = None  # type: ignore
    metadata_ = None  # type: ignore
    is_active = None  # type: ignore
    version = None  # type: ignore
