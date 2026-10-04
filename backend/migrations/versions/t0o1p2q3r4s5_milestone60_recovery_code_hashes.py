"""milestone60_recovery_code_hashes

Revision ID: t0o1p2q3r4s5
Revises: s9n0o1p2q3r4
Create Date: 2026-10-04 16:00:00.000000

Datenmigration: MFA-Recovery-Codes lagen bisher im Klartext in users.mfa_recovery_codes. Ab M60 werden
nur noch Hashes gespeichert; vorhandene Klartext-Codes werden hier gehasht (bereits gehashte bleiben
unveraendert, die Codes funktionieren fuer die Nutzer weiter). Kein Schema-Wechsel.
Downgrade: Hashes sind nicht umkehrbar, die Codes bleiben gehasht (Code-Stand vor M60 erwartet Klartext:
betroffene Nutzer muessen dann neue Codes erzeugen, siehe docs/known-limitations.md).
"""
import json
import re

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from werkzeug.security import generate_password_hash

revision = "t0o1p2q3r4s5"
down_revision = "s9n0o1p2q3r4"
branch_labels = None
depends_on = None

_PREFIXES = ("scrypt:", "pbkdf2:")


def _norm(code) -> str:
    return re.sub(r"[\s-]", "", str(code or "")).lower()


def upgrade():
    bind = op.get_bind()
    if "users" not in sa_inspect(bind).get_table_names():
        return
    users = sa.table("users", sa.column("id", sa.Integer), sa.column("mfa_recovery_codes", sa.JSON))
    rows = bind.execute(sa.select(users.c.id, users.c.mfa_recovery_codes)
                        .where(users.c.mfa_recovery_codes.isnot(None))).fetchall()
    for user_id, codes in rows:
        if isinstance(codes, (str, bytes)):
            codes = json.loads(codes)
        if not isinstance(codes, list) or not codes:
            continue
        hashed = [c if str(c).startswith(_PREFIXES) else generate_password_hash(_norm(c)) for c in codes]
        if hashed != codes:
            bind.execute(users.update().where(users.c.id == user_id).values(mfa_recovery_codes=hashed))


def downgrade():
    pass
