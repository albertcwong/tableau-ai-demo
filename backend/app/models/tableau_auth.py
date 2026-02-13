"""Tableau authentication type enumeration."""
from enum import Enum


class TableauAuthType(str, Enum):
    """Tableau authentication type enumeration."""
    CONNECTED_APP = "connected_app"  # Direct Trust JWT
    PAT = "pat"  # Personal Access Token
    STANDARD = "standard"  # Future: username/password
    CONNECTED_APP_OAUTH = "connected_app_oauth"  # OAuth 2.0 Trust (EAS-issued JWT)
