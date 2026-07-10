"""maluS v1 authentication & user management (argon2 + cookie sessions)."""

from malus.auth.deps import get_current_user, require_admin
from malus.auth.service import authenticate, bootstrap_admin, create_user, set_password

__all__ = [
    "authenticate",
    "bootstrap_admin",
    "create_user",
    "get_current_user",
    "require_admin",
    "set_password",
]
