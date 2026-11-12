"""Seed test accounts for each user role.

Revision ID: b9c84e2a76d1
Revises: fe038862beb8
Create Date: 2026-11-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9c84e2a76d1"
down_revision: Union[str, Sequence[str], None] = "fe038862beb8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TEST_ACCOUNTS = (
    {
        "first_name": "Teszt",
        "last_name": "Ügyfél",
        "email": "teszt.ugyfel@example.com",
        "password_hash": "scrypt:32768:8:1$ZdTRfd2kLHwOs1qc$ceb4ffd182a78bbbbc97bb82dead3ef059cca38fb4c4a2bba26143c95fee71a9dd82b24d840813fc1b93af6c909e587a439aa951e996a95279123439500a6cd4",
        "role": "customer",
    },
    {
        "first_name": "Teszt",
        "last_name": "Futár",
        "email": "teszt.futar@example.com",
        "password_hash": "scrypt:32768:8:1$ZdTRfd2kLHwOs1qc$ceb4ffd182a78bbbbc97bb82dead3ef059cca38fb4c4a2bba26143c95fee71a9dd82b24d840813fc1b93af6c909e587a439aa951e996a95279123439500a6cd4",
        "role": "courier",
    },
    {
        "first_name": "Teszt",
        "last_name": "Logisztikus",
        "email": "teszt.logisztikus@example.com",
        "password_hash": "scrypt:32768:8:1$ZdTRfd2kLHwOs1qc$ceb4ffd182a78bbbbc97bb82dead3ef059cca38fb4c4a2bba26143c95fee71a9dd82b24d840813fc1b93af6c909e587a439aa951e996a95279123439500a6cd4",
        "role": "logistician",
    },
    {
        "first_name": "Teszt",
        "last_name": "Admin",
        "email": "teszt.admin@example.com",
        "password_hash": "scrypt:32768:8:1$ZdTRfd2kLHwOs1qc$ceb4ffd182a78bbbbc97bb82dead3ef059cca38fb4c4a2bba26143c95fee71a9dd82b24d840813fc1b93af6c909e587a439aa951e996a95279123439500a6cd4",
        "role": "admin",
    },
)


def _users_table() -> sa.Table:
    return sa.table(
        "users",
        sa.column("first_name", sa.String(50)),
        sa.column("last_name", sa.String(50)),
        sa.column("email", sa.String(100)),
        sa.column("password_hash", sa.String(255)),
        sa.column("role", sa.String(20)),
        sa.column("is_active", sa.Boolean()),
    )


def upgrade() -> None:
    users = _users_table()
    bind = op.get_bind()

    for account in _TEST_ACCOUNTS:
        already_exists = bind.scalar(
            sa.select(sa.literal(1))
            .select_from(users)
            .where(
                sa.func.lower(users.c.email) == account["email"],
                users.c.is_active.is_(True),
            )
            .limit(1)
        )
        if already_exists is None:
            bind.execute(users.insert().values(**account, is_active=True))


def downgrade() -> None:
    users = _users_table()
    bind = op.get_bind()

    for account in _TEST_ACCOUNTS:
        bind.execute(
            users.delete().where(
                sa.func.lower(users.c.email) == account["email"],
                users.c.password_hash == account["password_hash"],
                users.c.role == account["role"],
            )
        )
