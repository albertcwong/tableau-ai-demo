"""Agent configuration models."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.core.database import Base


class AgentConfig(Base):
    """Agent configuration model for managing agent versions and settings."""
    __tablename__ = "agent_configs"

    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(String(50), nullable=False, index=True, comment="Agent name (e.g., 'vizql', 'summary')")
    version = Column(String(20), nullable=False, comment="Version (e.g., 'v1', 'v2', 'v3', or 'settings' for agent-level config)")
    is_enabled = Column(Boolean, default=True, nullable=False, index=True)
    is_default = Column(Boolean, default=False, nullable=False, index=True, comment="Only one default per agent_name")
    description = Column(String(500), nullable=True, comment="Optional description of this version")
    max_build_retries = Column(Integer, nullable=True, comment="VizQL-specific: max query build/refinement attempts")
    max_execution_retries = Column(Integer, nullable=True, comment="VizQL-specific: max execution retry attempts")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Unique constraint: one config per agent_name + version combination
    __table_args__ = (
        UniqueConstraint('agent_name', 'version', name='uq_agent_config_name_version'),
        Index('idx_agent_config_name_default', 'agent_name', 'is_default'),
    )

    def __repr__(self):
        return f"<AgentConfig(id={self.id}, agent_name={self.agent_name}, version={self.version}, enabled={self.is_enabled}, default={self.is_default})>"
