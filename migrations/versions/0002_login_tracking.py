"""Add user login tracking fields and login_events table."""
from alembic import op
import sqlalchemy as sa

revision = '0002_login_tracking'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('login_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        'login_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('logged_in_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_login_events_user_id', 'login_events', ['user_id'])
    op.create_index('ix_login_events_logged_in_at', 'login_events', ['logged_in_at'])


def downgrade():
    op.drop_index('ix_login_events_logged_in_at', table_name='login_events')
    op.drop_index('ix_login_events_user_id', table_name='login_events')
    op.drop_table('login_events')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'login_count')

