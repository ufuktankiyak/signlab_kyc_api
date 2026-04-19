"""add face_match fields to kyc_liveness

Revision ID: d4e1f2a3b5c6
Revises: ccf2472a6066
Create Date: 2026-04-19

"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e1f2a3b5c6'
down_revision = 'ccf2472a6066'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('kyc_liveness', sa.Column('face_match_score', sa.Float(), nullable=True))
    op.add_column('kyc_liveness', sa.Column('face_matched', sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column('kyc_liveness', 'face_matched')
    op.drop_column('kyc_liveness', 'face_match_score')
