from zou.app import db
from zou.app.models.base import BaseMixin


class RestrictedMetadataField(db.Model, BaseMixin):
    __tablename__ = "plugin_restricted_metadata_fields"
    __table_args__ = {"extend_existing": True}

    name = db.Column(db.String(120), nullable=False)
    entity_type = db.Column(db.String(30), nullable=False)
    field_type = db.Column(db.String(30), nullable=False)
    options_json = db.Column(db.JSON, nullable=True)
    default_value = db.Column(db.JSON, nullable=True)
    is_required = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class RestrictedMetadataValue(db.Model, BaseMixin):
    __tablename__ = "plugin_restricted_metadata_values"
    __table_args__ = {"extend_existing": True}

    field_id = db.Column(db.UUID(as_uuid=True), nullable=False)
    entity_type = db.Column(db.String(30), nullable=False)
    entity_id = db.Column(db.UUID(as_uuid=True), nullable=False)
    value_json = db.Column(db.JSON, nullable=True)
