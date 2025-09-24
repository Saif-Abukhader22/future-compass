"""create whitelist_users

Revision ID: 98b371d8e30a
Revises: 
Create Date: 2025-09-21 09:58:48.655261

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '98b371d8e30a'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


"""create whitelist_users

Revision ID: 98b371d8e30a
Revises: 
Create Date: 2025-09-21 09:58:48.655261

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '98b371d8e30a'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "whitelist_users",
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.UniqueConstraint("email", name="uq_whitelist_email"),
    )
    # Optional: enforce case-insensitive uniqueness
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_whitelist_email_ci ON whitelist_users (lower(email))")
    elif bind.dialect.name == "postgresql":
        # If you want strict CI uniqueness at DB level, uncomment:
        # op.execute("CREATE EXTENSION IF NOT EXISTS citext")
        # op.execute("ALTER TABLE whitelist_users ALTER COLUMN email TYPE CITEXT")
        pass

def downgrade():
    op.drop_table("whitelist_users")
