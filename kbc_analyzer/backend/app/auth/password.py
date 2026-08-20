"""Password hashing (S6-01) — passlib's bcrypt scheme.

Bcrypt over argon2id: both are acceptable per the ticket, bcrypt picked
because it's the more battle-tested default (this app has no unusual
threat model — e.g. no GPU-farm-scale offline-cracking concern beyond what
any bcrypt-hashed password database already withstands) and needs no extra
native dependency beyond what `passlib[bcrypt]` already pulls in, unlike
argon2id's separate `argon2-cffi` package.

Known bcrypt limitation: bcrypt only uses the first 72 bytes of the input
password — passlib's bcrypt backend silently truncates rather than
raising. Closed by validate_password_strength's MAX_PASSWORD_LENGTH below
(S6-04): every path that writes a new password validates first, so an
implausibly long input is rejected outright rather than silently hashed
down to its first 72 bytes.
"""
from passlib.context import CryptContext

__all__ = ["hash_password", "verify_password", "validate_password_strength", "PasswordTooWeakError"]

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# S6-04: length over complexity-rule theater — matches NIST 800-63B's
# modern guidance (mandatory uppercase/digit/symbol rules push people
# toward predictable substitutions like "Password1!" without meaningfully
# raising the search space an attacker faces; length is what actually
# does that). 8 is NIST's own stated minimum. 128 isn't a security
# requirement — it's the length-outright-rejected floor that closes the
# gap this module's own docstring used to flag: bcrypt silently truncates
# at 72 bytes, so without an upper bound a 10,000-character "password"
# would hash to the same thing as its first 72 bytes without the caller
# ever being told.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


class PasswordTooWeakError(ValueError):
    """password fails validate_password_strength — carries a message
    safe to return directly to the client (a 400, not a 500)."""


def validate_password_strength(password: str) -> None:
    """Raises PasswordTooWeakError if password doesn't meet the minimum
    bar. Called by both /api/auth/register and /api/auth/set-password —
    every path that ever writes a new password_hash."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordTooWeakError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordTooWeakError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters.")


def hash_password(password: str) -> str:
    """Hash a plaintext password for storage in users.password_hash."""
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """True if password matches the hash produced by hash_password()."""
    return _pwd_context.verify(password, password_hash)
