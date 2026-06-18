from uuid import UUID

from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required
from zou.app import db
from zou.app.services import persons_service

from .models import RestrictedMetadataField, RestrictedMetadataValue


VALID_ENTITY_TYPES = {"episode", "sequence", "shot", "asset"}
VALID_FIELD_TYPES = {"text", "number", "checkbox", "list"}


def require_admin():
    persons_service.check_admin_permissions()


def field_to_dict(field):
    return {
        "id": str(field.id),
        "name": field.name,
        "entity_type": field.entity_type,
        "field_type": field.field_type,
        "options_json": field.options_json,
        "default_value": field.default_value,
        "is_required": field.is_required,
        "sort_order": field.sort_order,
    }


def value_to_dict(value):
    return {
        "id": str(value.id),
        "field_id": str(value.field_id),
        "entity_type": value.entity_type,
        "entity_id": str(value.entity_id),
        "value": value.value_json,
    }


class HealthResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()
        return {"status": "ok", "plugin": "restricted-metadata"}


class FieldsResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        entity_type = request.args.get("entity_type")
        query = RestrictedMetadataField.query

        if entity_type:
            query = query.filter_by(entity_type=entity_type)

        fields = query.order_by(
            RestrictedMetadataField.entity_type,
            RestrictedMetadataField.sort_order,
            RestrictedMetadataField.name,
        ).all()

        return {"fields": [field_to_dict(field) for field in fields]}

    @jwt_required()
    def post(self):
        require_admin()
        data = request.get_json() or {}

        name = data.get("name")
        entity_type = data.get("entity_type")
        field_type = data.get("field_type")

        if not name:
            return {"error": "name is required"}, 400

        if entity_type not in VALID_ENTITY_TYPES:
            return {"error": "invalid entity_type"}, 400

        if field_type not in VALID_FIELD_TYPES:
            return {"error": "invalid field_type"}, 400

        field = RestrictedMetadataField.create(
            name=name,
            entity_type=entity_type,
            field_type=field_type,
            options_json=data.get("options_json"),
            default_value=data.get("default_value"),
            is_required=bool(data.get("is_required", False)),
            sort_order=int(data.get("sort_order", 0)),
        )

        return {"field": field_to_dict(field)}, 201


class FieldResource(Resource):
    @jwt_required()
    def patch(self, field_id):
        require_admin()
        field = RestrictedMetadataField.get(field_id)
        data = request.get_json() or {}

        for key in [
            "name",
            "entity_type",
            "field_type",
            "options_json",
            "default_value",
            "is_required",
            "sort_order",
        ]:
            if key in data:
                setattr(field, key, data[key])

        db.session.commit()
        return {"field": field_to_dict(field)}

    @jwt_required()
    def delete(self, field_id):
        require_admin()
        field = RestrictedMetadataField.get(field_id)

        RestrictedMetadataValue.query.filter_by(field_id=field.id).delete()
        db.session.delete(field)
        db.session.commit()

        return {"deleted": True}


class ValuesResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        entity_type = request.args.get("entity_type")
        entity_id = request.args.get("entity_id")

        query = RestrictedMetadataValue.query

        if entity_type:
            query = query.filter_by(entity_type=entity_type)

        if entity_id:
            query = query.filter_by(entity_id=UUID(entity_id))

        values = query.all()
        return {"values": [value_to_dict(value) for value in values]}

    @jwt_required()
    def post(self):
        require_admin()
        data = request.get_json() or {}

        field_id = data.get("field_id")
        entity_type = data.get("entity_type")
        entity_id = data.get("entity_id")

        if entity_type not in VALID_ENTITY_TYPES:
            return {"error": "invalid entity_type"}, 400

        value = RestrictedMetadataValue.create(
            field_id=UUID(field_id),
            entity_type=entity_type,
            entity_id=UUID(entity_id),
            value_json=data.get("value"),
        )

        return {"value": value_to_dict(value)}, 201


class BulkSetResource(Resource):
    @jwt_required()
    def post(self):
        require_admin()
        data = request.get_json() or {}

        field_id = UUID(data["field_id"])
        entity_type = data["entity_type"]
        entity_ids = data.get("entity_ids", [])
        new_value = data.get("value")

        if entity_type not in VALID_ENTITY_TYPES:
            return {"error": "invalid entity_type"}, 400

        updated = 0

        for entity_id_raw in entity_ids:
            entity_id = UUID(entity_id_raw)

            value = RestrictedMetadataValue.query.filter_by(
                field_id=field_id,
                entity_type=entity_type,
                entity_id=entity_id,
            ).first()

            if value is None:
                RestrictedMetadataValue.create(
                    field_id=field_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    value_json=new_value,
                )
            else:
                value.value_json = new_value

            updated += 1

        db.session.commit()

        return {"updated": updated}
