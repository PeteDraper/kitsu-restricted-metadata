from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "plugin_restricted_metadata_fields",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.add_column(
        "plugin_restricted_metadata_fields",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )

    op.create_index(
        "idx_restricted_metadata_fields_project_entity",
        "plugin_restricted_metadata_fields",
        ["project_id", "entity_type"],
    )

    op.create_index(
        "idx_restricted_metadata_values_entity",
        "plugin_restricted_metadata_values",
        ["entity_type", "entity_id"],
    )

    op.create_index(
        "idx_restricted_metadata_values_field_entity",
        "plugin_restricted_metadata_values",
        ["field_id", "entity_type", "entity_id"],
    )


def downgrade():
    op.drop_index(
        "idx_restricted_metadata_values_field_entity",
        table_name="plugin_restricted_metadata_values",
    )
    op.drop_index(
        "idx_restricted_metadata_values_entity",
        table_name="plugin_restricted_metadata_values",
    )
    op.drop_index(
        "idx_restricted_metadata_fields_project_entity",
        table_name="plugin_restricted_metadata_fields",
    )
    op.drop_column("plugin_restricted_metadata_fields", "is_active")
    op.drop_column("plugin_restricted_metadata_fields", "project_id")
