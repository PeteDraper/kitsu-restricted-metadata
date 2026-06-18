import csv
import io
from uuid import UUID

from flask import request, Response
from flask_restful import Resource
from flask_jwt_extended import jwt_required
from zou.app import db
from zou.app.services import persons_service
from zou.app.services import shots_service, assets_service, projects_service

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


def entity_to_dict(entity):
    return {
        "id": str(entity.get("id")),
        "name": entity.get("name"),
        "code": entity.get("code"),
        "project_id": str(entity.get("project_id")) if entity.get("project_id") else None,
        "episode_id": str(entity.get("episode_id")) if entity.get("episode_id") else None,
        "sequence_id": str(entity.get("sequence_id")) if entity.get("sequence_id") else None,
        "entity_type_id": str(entity.get("entity_type_id")) if entity.get("entity_type_id") else None,
    }


class HealthResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()
        return {"status": "ok", "plugin": "restricted-metadata"}


class ProjectContextResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = request.args.get("project_id") or request.args.get("production_id")
        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        project = projects_service.get_project(project_id)

        return {
            "project": {
                "id": str(project["id"]),
                "name": project.get("name"),
                "code": project.get("code"),
            }
        }


class EpisodesResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = request.args.get("project_id") or request.args.get("production_id")
        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        episodes = shots_service.get_episodes_for_project(project_id)
        return {"episodes": [entity_to_dict(episode) for episode in episodes]}


class SequencesResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = request.args.get("project_id") or request.args.get("production_id")
        episode_id = request.args.get("episode_id")

        if episode_id:
            sequences = shots_service.get_sequences_for_episode(episode_id)
        else:
            if not project_id:
                return {"error": "project_id or production_id is required"}, 400
            sequences = shots_service.get_sequences_for_project(project_id)

        return {"sequences": [entity_to_dict(sequence) for sequence in sequences]}


class ShotsResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = request.args.get("project_id") or request.args.get("production_id")
        episode_id = request.args.get("episode_id")

        if episode_id:
            shots = shots_service.get_shots_for_episode(episode_id)
        else:
            if not project_id:
                return {"error": "project_id or production_id is required"}, 400
            shots = shots_service.get_shots_for_project(project_id)

        sequence_id = request.args.get("sequence_id")
        if sequence_id:
            shots = [
                shot for shot in shots
                if str(shot.get("sequence_id")) == str(sequence_id)
            ]

        return {"shots": [entity_to_dict(shot) for shot in shots]}


class AssetsResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = request.args.get("project_id") or request.args.get("production_id")
        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        assets = assets_service.get_assets({"project_id": project_id}, is_admin=True)

        asset_type_id = request.args.get("asset_type_id")
        if asset_type_id:
            assets = [
                asset for asset in assets
                if str(asset.get("entity_type_id")) == str(asset_type_id)
            ]

        return {"assets": [entity_to_dict(asset) for asset in assets]}


class AssetTypesResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = request.args.get("project_id") or request.args.get("production_id")
        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        asset_types = assets_service.get_asset_types_for_project(project_id)

        return {
            "asset_types": [
                {
                    "id": str(asset_type.get("id")),
                    "name": asset_type.get("name"),
                }
                for asset_type in asset_types
            ]
        }


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

        existing = RestrictedMetadataValue.query.filter_by(
            field_id=UUID(field_id),
            entity_type=entity_type,
            entity_id=UUID(entity_id),
        ).first()

        if existing:
            existing.value_json = data.get("value")
            db.session.commit()
            return {"value": value_to_dict(existing)}

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


class ExportJsonResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        fields = {
            str(field.id): field_to_dict(field)
            for field in RestrictedMetadataField.query.all()
        }

        values = [
            value_to_dict(value)
            for value in RestrictedMetadataValue.query.all()
        ]

        return {
            "fields": fields,
            "values": values,
        }


class ExportCsvResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "field_id",
            "field_name",
            "entity_type",
            "entity_id",
            "value",
        ])

        fields = {
            field.id: field
            for field in RestrictedMetadataField.query.all()
        }

        for value in RestrictedMetadataValue.query.all():
            field = fields.get(value.field_id)
            writer.writerow([
                str(value.field_id),
                field.name if field else "",
                value.entity_type,
                str(value.entity_id),
                value.value_json,
            ])

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=restricted_metadata.csv"
            },
        )
