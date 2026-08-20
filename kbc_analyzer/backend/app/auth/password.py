"""Password hashing (S6-01) — passlib's bcrypt scheme.

Bcrypt over argon2id: both are acceptable per the ticket, bcrypt picked
because it's the more battle-tested default (this app has no unusual
threat model — e.g. no GPU-farm-scale offline-cracking concern beyond what
any bcrypt-hashed password database already withstands) and needs no extra
native dependency beyond what `passlib[bcrypt]` already pulls in, unlike
argon2id's separate `argon2-cffi` package.

Known bcrypt limitation, not worked around here: bcrypt only uses the
first 72 bytes of the input password — passlib's bcrypt backend silently
truncates rather than raising. This is a non-issue for any password a
human actually types, and S6-04 (which owns password-strength validation)
is the right place to decide whether to reject implausibly long input
outright rather than silently truncate it.
"""
from passlib.context import CryptContext

__all__ = ["hash_password", "verify_password"]

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password for storage in users.password_hash."""
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """True if password matches the hash produced by hash_password()."""
    return _pwd_context.verify(password, password_hash)
