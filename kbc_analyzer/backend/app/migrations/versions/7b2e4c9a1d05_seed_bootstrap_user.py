"""seed bootstrap user

Sprint 6 (S6-02) — seeds exactly one real user row: Borys's real login
email, provided directly by him for this migration (not invented). Every
existing row in every table gets backfilled to this user in the next
migration (backfill_user_id_from_bootstrap_user).

password_hash is a real bcrypt hash (app/auth/password.hash_password) of a
random value generated once and never stored or displayed anywhere,
including here — satisfies the users_has_auth_method CHECK constraint
without setting a usable password. This account cannot be logged into via
password OR Google (google_id is also NULL) until a later ticket gives it
one: S6-04 ("your call, state which and why" per the ticket) chose the
"register a real password" path over a one-time reset-token flow, since
S6-01 built no reset-token machinery and adding one now would be scope
creep into S6-04's own ticket. Until S6-04 ships, this is expected and
correct — Sprint 6 builds schema (S6-02) before login flows (S6-03/S6-04)
by design.

Revision ID: 7b2e4c9a1d05
Revises: 1f7634448483
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b2e4c9a1d05'
down_revision: Union[str, Sequence[str], None] = '1f7634448483'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BOOTSTRAP_USER_EMAIL = "boris.sydorchuk@gmail.com"
# bcrypt hash of a random value generated once at migration-authoring time
# and immediately discarded — nobody, including this migration's author,
# knows the plaintext it corresponds to. Satisfies users_has_auth_method
# without being a usable credential.
_LOCKED_PASSWORD_HASH = "$2b$12$6qRhoHla2R0n2zGuL64mCuIkCOuSeVdmd03AfCoHU5U6iyF56egu6"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        sa.text(
            "INSERT INTO users (email, password_hash) VALUES (:email, :password_hash)"
        ).bindparams(email=BOOTSTRAP_USER_EMAIL, password_hash=_LOCKED_PASSWORD_HASH)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        sa.text("DELETE FROM users WHERE email = :email").bindparams(email=BOOTSTRAP_USER_EMAIL)
    )
