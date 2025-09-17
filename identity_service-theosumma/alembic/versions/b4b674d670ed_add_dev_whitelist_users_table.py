"""add dev_whitelist_users table

Revision ID: b4b674d670ed
Revises: 40e9d13fd09b
Create Date: 2025-05-04 09:07:38.128019

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4b674d670ed'
down_revision: Union[str, None] = '40e9d13fd09b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        'dev_whitelist_users',
        sa.Column('w_user_id', sa.String(), primary_key=True, index=True),
        sa.Column('email', sa.String(), nullable=False, unique=True, index=True),
    )

def downgrade():
    op.drop_table('dev_whitelist_users')