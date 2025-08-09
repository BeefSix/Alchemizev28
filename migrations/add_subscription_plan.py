"""Add subscription_plan column to users table

Revision ID: add_subscription_plan
Revises: 
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_subscription_plan'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    """Add subscription_plan column to users table"""
    # Add the subscription_plan column with default value 'free'
    op.add_column('users', sa.Column('subscription_plan', sa.String(), nullable=True))
    
    # Update existing users to have 'free' plan
    op.execute("UPDATE users SET subscription_plan = 'free' WHERE subscription_plan IS NULL")
    
    # Make the column non-nullable after setting default values
    op.alter_column('users', 'subscription_plan', nullable=False)

def downgrade():
    """Remove subscription_plan column from users table"""
    op.drop_column('users', 'subscription_plan')