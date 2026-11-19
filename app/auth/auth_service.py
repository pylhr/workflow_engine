"""Authentication and RBAC helpers.

Simple username/password auth using passlib for hashing. There's no JWT
here since everything runs in a single desktop process — the
`current_user` is just held in memory by the UI layer (see
ui/main_window.py) for the duration of the app session.
"""

from passlib.context import CryptContext

from app.database import get_session
from app.models.user import User

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _pwd_context.verify(plain_password, password_hash)


class AuthError(Exception):
    pass


def authenticate(username: str, password: str) -> dict:
    """Validate credentials and return a plain dict snapshot of the user.

    Returns a dict (not the ORM object) so it remains usable after the
    session that loaded it is closed.
    """
    with get_session() as session:
        user: User | None = session.query(User).filter_by(username=username).first()
        if user is None or not user.is_active:
            raise AuthError("Invalid username or password.")
        if not verify_password(password, user.password_hash):
            raise AuthError("Invalid username or password.")

        return {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role.name if user.role else None,
        }


def create_user(username: str, password: str, role_name: str, full_name: str = "") -> int:
    """Create a new user with the given role. Returns the new user id.

    Raises ValueError if the username already exists or the role is unknown.
    """
    from app.models.user import Role

    with get_session() as session:
        if session.query(User).filter_by(username=username).first() is not None:
            raise ValueError(f"Username '{username}' already exists.")

        role = session.query(Role).filter_by(name=role_name).first()
        if role is None:
            raise ValueError(f"Unknown role '{role_name}'.")

        user = User(
            username=username,
            full_name=full_name,
            password_hash=hash_password(password),
            role=role,
        )
        session.add(user)
        session.flush()
        return user.id


def require_role(user: dict, *allowed_roles: str) -> None:
    """Raise PermissionError if user's role isn't in allowed_roles."""
    if user.get("role") not in allowed_roles:
        raise PermissionError(
            f"Action requires one of roles {allowed_roles}, "
            f"but user has role '{user.get('role')}'."
        )
