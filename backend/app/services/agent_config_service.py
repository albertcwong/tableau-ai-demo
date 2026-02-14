"""Agent configuration service for managing agent versions and settings."""
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.agent_config import AgentConfig
from app.core.config import settings

logger = logging.getLogger(__name__)


class AgentConfigService:
    """Service for managing agent configurations."""
    
    def __init__(self, db: Session):
        """Initialize agent config service.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def get_default_version(self, agent_name: str) -> Optional[str]:
        """Get the default version for an agent.
        
        Args:
            agent_name: Agent name (e.g., 'vizql', 'summary')
            
        Returns:
            Version string (e.g., 'v1', 'v2', 'v3') or None if not found
        """
        config = self.db.query(AgentConfig).filter(
            and_(
                AgentConfig.agent_name == agent_name,
                AgentConfig.is_default == True,
                AgentConfig.is_enabled == True
            )
        ).first()
        
        if config:
            return config.version
        return None
    
    def get_enabled_versions(self, agent_name: str) -> List[str]:
        """Get all enabled versions for an agent.
        
        Args:
            agent_name: Agent name (e.g., 'vizql', 'summary')
            
        Returns:
            List of version strings
        """
        configs = self.db.query(AgentConfig).filter(
            and_(
                AgentConfig.agent_name == agent_name,
                AgentConfig.is_enabled == True,
                AgentConfig.version != 'settings'  # Exclude settings row
            )
        ).all()
        
        return [config.version for config in configs]
    
    def is_version_enabled(self, agent_name: str, version: str) -> bool:
        """Check if a specific agent version is enabled.
        
        Args:
            agent_name: Agent name
            version: Version string
            
        Returns:
            True if enabled, False otherwise
        """
        config = self.db.query(AgentConfig).filter(
            and_(
                AgentConfig.agent_name == agent_name,
                AgentConfig.version == version,
                AgentConfig.is_enabled == True
            )
        ).first()
        
        return config is not None
    
    def get_agent_settings(self, agent_name: str) -> Dict[str, Optional[int]]:
        """Get agent-level settings (retry configs, max_rows) with fallback to env vars.
        
        Args:
            agent_name: Agent name (e.g., 'vizql', 'summary')
            
        Returns:
            Dictionary with max_build_retries, max_execution_retries, and max_rows
        """
        settings_config = self.db.query(AgentConfig).filter(
            and_(
                AgentConfig.agent_name == agent_name,
                AgentConfig.version == 'settings'
            )
        ).first()
        
        if settings_config:
            result = {
                'max_build_retries': settings_config.max_build_retries,
                'max_execution_retries': settings_config.max_execution_retries,
                'max_rows': settings_config.max_rows
            }
            return result
        
        # Fallback to env vars (for backward compatibility)
        logger.warning(
            f"No agent settings found for {agent_name}, falling back to env vars. "
            "Consider configuring via admin panel."
        )
        result = {
            'max_build_retries': getattr(settings, 'VIZQL_MAX_BUILD_RETRIES', 3),
            'max_execution_retries': getattr(settings, 'VIZQL_MAX_EXECUTION_RETRIES', 3),
            'max_rows': None  # No env var fallback for max_rows
        }
        # For summary agent, default max_rows to 5000 if not configured
        if agent_name == 'summary':
            result['max_rows'] = 5000
        return result
    
    def get_all_agents(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all agents with their versions.
        
        Returns:
            Dictionary mapping agent_name to list of version configs
        """
        configs = self.db.query(AgentConfig).filter(
            AgentConfig.version != 'settings'  # Exclude settings rows
        ).order_by(AgentConfig.agent_name, AgentConfig.version).all()
        
        result: Dict[str, List[Dict[str, Any]]] = {}
        for config in configs:
            if config.agent_name not in result:
                result[config.agent_name] = []
            result[config.agent_name].append({
                'version': config.version,
                'is_enabled': config.is_enabled,
                'is_default': config.is_default,
                'description': config.description
            })
        
        return result
    
    def get_agent_versions(self, agent_name: str) -> List[Dict[str, Any]]:
        """Get all versions for a specific agent.
        
        Args:
            agent_name: Agent name
            
        Returns:
            List of version config dictionaries
        """
        configs = self.db.query(AgentConfig).filter(
            and_(
                AgentConfig.agent_name == agent_name,
                AgentConfig.version != 'settings'
            )
        ).order_by(AgentConfig.version).all()
        
        return [
            {
                'version': config.version,
                'is_enabled': config.is_enabled,
                'is_default': config.is_default,
                'description': config.description
            }
            for config in configs
        ]
    
    def set_active_version(self, agent_name: str, version: str) -> AgentConfig:
        """Set the active version for an agent. Only one version can be active at a time.
        
        Args:
            agent_name: Agent name (e.g., 'vizql', 'summary')
            version: Version string to activate
            
        Returns:
            Updated AgentConfig instance for the active version
        """
        config = self.db.query(AgentConfig).filter(
            and_(
                AgentConfig.agent_name == agent_name,
                AgentConfig.version == version,
                AgentConfig.version != 'settings'
            )
        ).first()
        
        if not config:
            raise ValueError(f"Agent config not found: {agent_name} {version}")
        
        # Disable all other versions for this agent
        self.db.query(AgentConfig).filter(
            and_(
                AgentConfig.agent_name == agent_name,
                AgentConfig.version != 'settings'
            )
        ).update({'is_enabled': False, 'is_default': False})
        
        # Enable and set as default for selected version
        config.is_enabled = True
        config.is_default = True
        
        safe_commit(self.db)
        self.db.refresh(config)
        return config
    
    def update_agent_settings(
        self,
        agent_name: str,
        max_build_retries: Optional[int] = None,
        max_execution_retries: Optional[int] = None,
        max_rows: Optional[int] = None
    ) -> AgentConfig:
        """Update agent-level settings (retry configs, max_rows).
        
        Args:
            agent_name: Agent name
            max_build_retries: Optional max build retries
            max_execution_retries: Optional max execution retries
            max_rows: Optional max rows (Summary agent)
            
        Returns:
            Updated AgentConfig instance (settings row)
        """
        settings_config = self.db.query(AgentConfig).filter(
            and_(
                AgentConfig.agent_name == agent_name,
                AgentConfig.version == 'settings'
            )
        ).first()
        
        if not settings_config:
            # Create settings row if it doesn't exist
            from datetime import datetime, timezone
            default_max_rows = max_rows if max_rows is not None else (5000 if agent_name == 'summary' else None)
            settings_config = AgentConfig(
                agent_name=agent_name,
                version='settings',
                is_enabled=True,
                is_default=False,
                max_build_retries=max_build_retries or 3,
                max_execution_retries=max_execution_retries or 3,
                max_rows=default_max_rows,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            self.db.add(settings_config)
        else:
            if max_build_retries is not None:
                settings_config.max_build_retries = max_build_retries
            if max_execution_retries is not None:
                settings_config.max_execution_retries = max_execution_retries
            if max_rows is not None:
                settings_config.max_rows = max_rows
        
        from app.core.database import safe_commit
        safe_commit(self.db)
        self.db.refresh(settings_config)
        return settings_config
