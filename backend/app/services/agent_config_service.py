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
        """Get agent-level settings (retry configs) with fallback to env vars.
        
        Args:
            agent_name: Agent name (e.g., 'vizql')
            
        Returns:
            Dictionary with max_build_retries and max_execution_retries
        """
        settings_config = self.db.query(AgentConfig).filter(
            and_(
                AgentConfig.agent_name == agent_name,
                AgentConfig.version == 'settings'
            )
        ).first()
        
        if settings_config:
            return {
                'max_build_retries': settings_config.max_build_retries,
                'max_execution_retries': settings_config.max_execution_retries
            }
        
        # Fallback to env vars (for backward compatibility)
        logger.warning(
            f"No agent settings found for {agent_name}, falling back to env vars. "
            "Consider configuring via admin panel."
        )
        return {
            'max_build_retries': getattr(settings, 'VIZQL_MAX_BUILD_RETRIES', 3),
            'max_execution_retries': getattr(settings, 'VIZQL_MAX_EXECUTION_RETRIES', 3)
        }
    
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
    
    def update_version_config(
        self,
        agent_name: str,
        version: str,
        is_enabled: Optional[bool] = None,
        is_default: Optional[bool] = None,
        description: Optional[str] = None
    ) -> AgentConfig:
        """Update version configuration.
        
        Args:
            agent_name: Agent name
            version: Version string
            is_enabled: Optional enabled flag
            is_default: Optional default flag (if True, unset other defaults for this agent)
            description: Optional description
            
        Returns:
            Updated AgentConfig instance
        """
        config = self.db.query(AgentConfig).filter(
            and_(
                AgentConfig.agent_name == agent_name,
                AgentConfig.version == version
            )
        ).first()
        
        if not config:
            raise ValueError(f"Agent config not found: {agent_name} {version}")
        
        if is_enabled is not None:
            config.is_enabled = is_enabled
        
        if is_default is not None:
            if is_default:
                # Unset other defaults for this agent
                self.db.query(AgentConfig).filter(
                    and_(
                        AgentConfig.agent_name == agent_name,
                        AgentConfig.is_default == True
                    )
                ).update({'is_default': False})
            config.is_default = is_default
        
        if description is not None:
            config.description = description
        
        self.db.commit()
        self.db.refresh(config)
        return config
    
    def update_agent_settings(
        self,
        agent_name: str,
        max_build_retries: Optional[int] = None,
        max_execution_retries: Optional[int] = None
    ) -> AgentConfig:
        """Update agent-level settings (retry configs).
        
        Args:
            agent_name: Agent name
            max_build_retries: Optional max build retries
            max_execution_retries: Optional max execution retries
            
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
            settings_config = AgentConfig(
                agent_name=agent_name,
                version='settings',
                is_enabled=True,
                is_default=False,
                max_build_retries=max_build_retries or 3,
                max_execution_retries=max_execution_retries or 3,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            self.db.add(settings_config)
        else:
            if max_build_retries is not None:
                settings_config.max_build_retries = max_build_retries
            if max_execution_retries is not None:
                settings_config.max_execution_retries = max_execution_retries
        
        self.db.commit()
        self.db.refresh(settings_config)
        return settings_config
