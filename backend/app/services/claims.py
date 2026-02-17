"""IdP-agnostic claim extraction from JWT/claims dicts."""


def extract_claim_value(claims: dict, field_path: str) -> str | None:
    """
    Extract a value from claims using dot-notation or namespaced path.
    Works with any IdP (Auth0, Entra, Okta, etc.).

    Supports:
    - Simple: "email" -> claims["email"]
    - Nested: "app_metadata.tableau_username" -> claims["app_metadata"]["tableau_username"]
    - Namespaced: "https://api.example/tableau_username" -> claims["https://api.example/tableau_username"]
    """
    if not field_path or not claims:
        return None
    if "/" in field_path:
        v = claims.get(field_path)
        return str(v) if v is not None else None
    parts = field_path.split(".")
    value = claims
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
        if value is None:
            return None
    return str(value) if value is not None else None
