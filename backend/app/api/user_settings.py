"""User settings API - PAT management and account settings."""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User, TableauServerConfig, UserTableauPAT, UserTableauPassword
from app.services.pat_encryption import encrypt_pat, decrypt_pat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["user-settings"])


class TableauPATResponse(BaseModel):
    """Tableau PAT response model (no secret)."""
    id: int
    tableau_server_config_id: int
    pat_name: str
    server_name: str
    server_url: str
    created_at: str


class TableauPATCreate(BaseModel):
    """Tableau PAT create/update model."""
    tableau_server_config_id: int = Field(..., description="Tableau server config ID")
    pat_name: str = Field(..., min_length=1, max_length=255)
    pat_secret: str = Field(..., min_length=1)


class UserSettingsResponse(BaseModel):
    """User settings overview."""
    username: str
    role: str
    has_tableau_pats: bool


@router.get("/settings", response_model=UserSettingsResponse)
async def get_user_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user's settings overview."""
    pat_count = db.query(UserTableauPAT).filter(UserTableauPAT.user_id == current_user.id).count()
    return UserSettingsResponse(
        username=current_user.username,
        role=current_user.role.value,
        has_tableau_pats=pat_count > 0,
    )


@router.get("/tableau-pats", response_model=List[TableauPATResponse])
async def list_tableau_pats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List current user's configured Tableau PATs."""
    pats = (
        db.query(UserTableauPAT, TableauServerConfig)
        .join(TableauServerConfig, UserTableauPAT.tableau_server_config_id == TableauServerConfig.id)
        .filter(
            UserTableauPAT.user_id == current_user.id,
            TableauServerConfig.is_active == True,
        )
        .all()
    )
    return [
        TableauPATResponse(
            id=pat.id,
            tableau_server_config_id=pat.tableau_server_config_id,
            pat_name=pat.pat_name,
            server_name=config.name,
            server_url=config.server_url,
            created_at=pat.created_at.isoformat(),
        )
        for pat, config in pats
    ]


@router.post("/tableau-pats", response_model=TableauPATResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_tableau_pat(
    data: TableauPATCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update PAT for a Tableau server."""
    config = db.query(TableauServerConfig).filter(
        TableauServerConfig.id == data.tableau_server_config_id,
        TableauServerConfig.is_active == True,
        TableauServerConfig.allow_pat_auth == True,
    ).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tableau server config not found or PAT auth not enabled",
        )
    encrypted = encrypt_pat(data.pat_secret)
    existing = db.query(UserTableauPAT).filter(
        UserTableauPAT.user_id == current_user.id,
        UserTableauPAT.tableau_server_config_id == data.tableau_server_config_id,
    ).first()
    if existing:
        existing.pat_name = data.pat_name
        existing.pat_secret = encrypted
        db.commit()
        db.refresh(existing)
        pat = existing
    else:
        pat = UserTableauPAT(
            user_id=current_user.id,
            tableau_server_config_id=data.tableau_server_config_id,
            pat_name=data.pat_name,
            pat_secret=encrypted,
        )
        db.add(pat)
        db.commit()
        db.refresh(pat)
    return TableauPATResponse(
        id=pat.id,
        tableau_server_config_id=pat.tableau_server_config_id,
        pat_name=pat.pat_name,
        server_name=config.name,
        server_url=config.server_url,
        created_at=pat.created_at.isoformat(),
    )


@router.delete("/tableau-pats/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tableau_pat(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete PAT for a Tableau server."""
    pat = db.query(UserTableauPAT).filter(
        UserTableauPAT.user_id == current_user.id,
        UserTableauPAT.tableau_server_config_id == config_id,
    ).first()
    if not pat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PAT not found for this server",
        )
    db.delete(pat)
    db.commit()


class TableauPasswordResponse(BaseModel):
    """Tableau password credential response (no password)."""
    id: int
    tableau_server_config_id: int
    tableau_username: str
    server_name: str
    server_url: str
    created_at: str


class TableauPasswordCreate(BaseModel):
    """Tableau standard credential create/update model."""
    tableau_server_config_id: int = Field(..., description="Tableau server config ID")
    tableau_username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1)


@router.get("/tableau-passwords", response_model=List[TableauPasswordResponse])
async def list_tableau_passwords(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List current user's configured Tableau standard credentials."""
    passwords = (
        db.query(UserTableauPassword, TableauServerConfig)
        .join(TableauServerConfig, UserTableauPassword.tableau_server_config_id == TableauServerConfig.id)
        .filter(
            UserTableauPassword.user_id == current_user.id,
            TableauServerConfig.is_active == True,
        )
        .all()
    )
    return [
        TableauPasswordResponse(
            id=pw.id,
            tableau_server_config_id=pw.tableau_server_config_id,
            tableau_username=pw.tableau_username,
            server_name=config.name,
            server_url=config.server_url,
            created_at=pw.created_at.isoformat(),
        )
        for pw, config in passwords
    ]


@router.post("/tableau-passwords", response_model=TableauPasswordResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_tableau_password(
    data: TableauPasswordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update standard credentials for a Tableau server."""
    config = db.query(TableauServerConfig).filter(
        TableauServerConfig.id == data.tableau_server_config_id,
        TableauServerConfig.is_active == True,
        TableauServerConfig.allow_standard_auth == True,
    ).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tableau server config not found or standard auth not enabled",
        )
    encrypted = encrypt_pat(data.password)
    existing = db.query(UserTableauPassword).filter(
        UserTableauPassword.user_id == current_user.id,
        UserTableauPassword.tableau_server_config_id == data.tableau_server_config_id,
    ).first()
    if existing:
        existing.tableau_username = data.tableau_username
        existing.password_encrypted = encrypted
        db.commit()
        db.refresh(existing)
        pw = existing
    else:
        pw = UserTableauPassword(
            user_id=current_user.id,
            tableau_server_config_id=data.tableau_server_config_id,
            tableau_username=data.tableau_username,
            password_encrypted=encrypted,
        )
        db.add(pw)
        db.commit()
        db.refresh(pw)
    return TableauPasswordResponse(
        id=pw.id,
        tableau_server_config_id=pw.tableau_server_config_id,
        tableau_username=pw.tableau_username,
        server_name=config.name,
        server_url=config.server_url,
        created_at=pw.created_at.isoformat(),
    )


@router.delete("/tableau-passwords/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tableau_password(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete standard credentials for a Tableau server."""
    pw = db.query(UserTableauPassword).filter(
        UserTableauPassword.user_id == current_user.id,
        UserTableauPassword.tableau_server_config_id == config_id,
    ).first()
    if not pw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credentials not found for this server",
        )
    db.delete(pw)
    db.commit()
