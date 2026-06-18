from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "plugin_restricted_metadata_values",
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.drop_column("plugin_restricted_metadata_values", "value_text")
    op.drop_column("plugin_restricted_metadata_values", "value_number")
    op.drop_column("plugin_restricted_metadata_values", "value_boolean")

    op.alter_column(
        "plugin_restricted_metadata_fields",
        "default_value",
        type_=postgresql.JSONB(astext_type=sa.Text()),
        postgresql_using="default_value::jsonb",
        existing_nullable=True,
    )


def downgrade():
    op.add_column("plugin_restricted_metadata_values", sa.Column("value_text", sa.Text(), nullable=True))
    op.add_column("plugin_restricted_metadata_values", sa.Column("value_number", sa.Float(), nullable=True))
    op.add_column("plugin_restricted_metadata_values", sa.Column("value_boolean", sa.Boolean(), nullable=True))
    op.drop_column("plugin_restricted_metadata_values", "value_json")
