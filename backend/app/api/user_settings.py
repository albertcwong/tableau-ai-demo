"""User settings API - PAT management and account settings."""
import logging
from typing import Any, List, Tuple, Type

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User, TableauServerConfig, UserTableauPAT, UserTableauPassword
from app.services.pat_encryption import encrypt_pat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["user-settings"])

_CREDENTIAL_CONFIG = {
    "pat": {
        "model": UserTableauPAT,
        "config_attr": "allow_pat_auth",
        "not_found_msg": "PAT not found for this server",
        "config_not_found_msg": "Tableau server config not found or PAT auth not enabled",
    },
    "password": {
        "model": UserTableauPassword,
        "config_attr": "allow_standard_auth",
        "not_found_msg": "Credentials not found for this server",
        "config_not_found_msg": "Tableau server config not found or standard auth not enabled",
    },
}


def _list_credentials(
    db: Session,
    user_id: int,
    model_cls: Type[Any],
) -> List[Tuple[Any, TableauServerConfig]]:
    return (
        db.query(model_cls, TableauServerConfig)
        .join(TableauServerConfig, model_cls.tableau_server_config_id == TableauServerConfig.id)
        .filter(model_cls.user_id == user_id, TableauServerConfig.is_active == True)
        .all()
    )


def _create_or_update_credential(
    db: Session,
    user_id: int,
    model_cls: Type[Any],
    config_attr: str,
    config_id: int,
    name_attr: str,
    name_value: str,
    secret_attr: str,
    secret_value: str,
) -> Tuple[Any, TableauServerConfig]:
    config = db.query(TableauServerConfig).filter(
        TableauServerConfig.id == config_id,
        TableauServerConfig.is_active == True,
        getattr(TableauServerConfig, config_attr) == True,
    ).first()
    if not config:
        return None, None
    encrypted = encrypt_pat(secret_value)
    existing = db.query(model_cls).filter(
        model_cls.user_id == user_id,
        model_cls.tableau_server_config_id == config_id,
    ).first()
    if existing:
        setattr(existing, name_attr, name_value)
        setattr(existing, secret_attr, encrypted)
        db.commit()
        db.refresh(existing)
        return existing, config
    record = model_cls(
        user_id=user_id,
        tableau_server_config_id=config_id,
        **{name_attr: name_value, secret_attr: encrypted},
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record, config


def _delete_credential(
    db: Session,
    user_id: int,
    model_cls: Type[Any],
    config_id: int,
) -> bool:
    record = db.query(model_cls).filter(
        model_cls.user_id == user_id,
        model_cls.tableau_server_config_id == config_id,
    ).first()
    if not record:
        return False
    db.delete(record)
    db.commit()
    return True


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
    rows = _list_credentials(db, current_user.id, UserTableauPAT)
    return [
        TableauPATResponse(
            id=r.id,
            tableau_server_config_id=r.tableau_server_config_id,
            pat_name=r.pat_name,
            server_name=c.name,
            server_url=c.server_url,
            created_at=r.created_at.isoformat(),
        )
        for r, c in rows
    ]


@router.post("/tableau-pats", response_model=TableauPATResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_tableau_pat(
    data: TableauPATCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update PAT for a Tableau server."""
    cfg = _CREDENTIAL_CONFIG["pat"]
    pat, config = _create_or_update_credential(
        db, current_user.id, cfg["model"], cfg["config_attr"],
        data.tableau_server_config_id, "pat_name", data.pat_name,
        "pat_secret", data.pat_secret,
    )
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=cfg["config_not_found_msg"])
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
    if not _delete_credential(db, current_user.id, UserTableauPAT, config_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PAT not found for this server")


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
    rows = _list_credentials(db, current_user.id, UserTableauPassword)
    return [
        TableauPasswordResponse(
            id=r.id,
            tableau_server_config_id=r.tableau_server_config_id,
            tableau_username=r.tableau_username,
            server_name=c.name,
            server_url=c.server_url,
            created_at=r.created_at.isoformat(),
        )
        for r, c in rows
    ]


@router.post("/tableau-passwords", response_model=TableauPasswordResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_tableau_password(
    data: TableauPasswordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update standard credentials for a Tableau server."""
    cfg = _CREDENTIAL_CONFIG["password"]
    pw, config = _create_or_update_credential(
        db, current_user.id, cfg["model"], cfg["config_attr"],
        data.tableau_server_config_id, "tableau_username", data.tableau_username,
        "password_encrypted", data.password,
    )
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=cfg["config_not_found_msg"])
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
    if not _delete_credential(db, current_user.id, UserTableauPassword, config_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credentials not found for this server")
