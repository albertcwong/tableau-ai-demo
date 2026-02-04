"""Tableau metadata cache models."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Index, JSON, Boolean, BigInteger
from sqlalchemy.orm import relationship
from app.core.database import Base


class Datasource(Base):
    """Datasource model for caching Tableau datasource metadata."""
    __tablename__ = "datasources"

    id = Column(Integer, primary_key=True, index=True)
    tableau_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    project = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)  # For soft deletion
    size_bytes = Column(BigInteger, nullable=True)  # For performance metrics
    row_count = Column(BigInteger, nullable=True)  # For performance metrics
    extra_metadata = Column(JSON, nullable=True)  # Additional Tableau properties
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    last_synced_at = Column(DateTime, nullable=True, index=True)  # Separate from updated_at for sync tracking

    # Relationships
    views = relationship("View", back_populates="datasource", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_datasource_project", "project"),
        Index("idx_datasource_updated", "updated_at"),
        Index("idx_datasource_synced", "last_synced_at"),
        Index("idx_datasource_active", "is_active"),
    )

    def __repr__(self):
        return f"<Datasource(id={self.id}, tableau_id={self.tableau_id}, name={self.name})>"


class View(Base):
    """View model for caching Tableau view metadata."""
    __tablename__ = "views"

    id = Column(Integer, primary_key=True, index=True)
    tableau_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    workbook = Column(String(255), nullable=True)
    view_type = Column(String(50), nullable=True)  # worksheet, dashboard, etc.
    embed_url = Column(String(500), nullable=True)  # Cached embed URL
    is_published = Column(Boolean, default=True, nullable=False, index=True)
    tags = Column(JSON, nullable=True)  # For organization/categories
    datasource_id = Column(Integer, ForeignKey("datasources.id", ondelete="CASCADE"), nullable=True, index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    last_synced_at = Column(DateTime, nullable=True, index=True)  # Separate from updated_at for sync tracking

    # Relationships
    datasource = relationship("Datasource", back_populates="views")

    # Indexes
    __table_args__ = (
        Index("idx_view_datasource", "datasource_id"),
        Index("idx_view_workbook", "workbook"),
        Index("idx_view_updated", "updated_at"),
        Index("idx_view_synced", "last_synced_at"),
        Index("idx_view_published", "is_published"),
        Index("idx_view_type", "view_type"),
    )

    def __repr__(self):
        return f"<View(id={self.id}, tableau_id={self.tableau_id}, name={self.name})>"
