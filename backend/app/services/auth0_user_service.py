"""Auth0 user service. Delegates to IdP service. Kept for backward compatibility."""
from app.services.claims import extract_claim_value
from app.services.idp_user_service import get_or_create_user

# Backward compat alias
extract_metadata_value = extract_claim_value


def get_or_create_user_from_auth0(db, auth0_claims: dict):
    """Deprecated: use idp_user_service.get_or_create_user(db, claims, provider='auth0')."""
    return get_or_create_user(db, auth0_claims, provider="auth0")
