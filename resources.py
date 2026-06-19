import csv
import io
from uuid import UUID

from flask import request, Response
from flask_restful import Resource
from flask_jwt_extended import jwt_required
from zou.app import db
from zou.app.utils import permissions
from zou.app.services import shots_service, assets_service, projects_service

from .models import RestrictedMetadataField, RestrictedMetadataValue


VALID_ENTITY_TYPES = {"episode", "sequence", "shot", "asset"}
VALID_FIELD_TYPES = {
    "text",
    "number",
    "checkbox",
    "single_select",
    "tags",
    "checklist",
}


def require_admin():
    permissions.check_admin_permissions()


def get_attr(item, key, default=None):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def to_uuid_or_none(value):
    if not value:
        return None
    return UUID(str(value))


def get_project_id():
    project_id = request.args.get("project_id") or request.args.get("production_id")
    if not project_id:
        data = request.get_json(silent=True) or {}
        project_id = data.get("project_id") or data.get("production_id")
    return project_id


def get_entity_parent_id(entity):
    return get_attr(entity, "sequence_id") or get_attr(entity, "parent_id")


def possible_thumbnail(entity):
    value = get_attr(entity, "preview_file_id")
    if value:
        return str(value)
    return None


def field_to_dict(field):
    return {
        "id": str(field.id),
        "project_id": str(field.project_id) if field.project_id else None,
        "entity_type": field.entity_type,
        "name": field.name,
        "field_type": field.field_type,
        "options_json": field.options_json or [],
        "default_value": field.default_value,
        "is_required": field.is_required,
        "is_active": field.is_active,
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


def entity_to_dict(entity, group_id=None, group_name=None, parent_id=None, parent_name=None):
    return {
        "id": str(get_attr(entity, "id")),
        "name": get_attr(entity, "name") or "",
        "project_id": str(get_attr(entity, "project_id")) if get_attr(entity, "project_id") else None,
        "episode_id": str(get_attr(entity, "episode_id")) if get_attr(entity, "episode_id") else None,
        "sequence_id": str(get_entity_parent_id(entity)) if get_entity_parent_id(entity) else None,
        "entity_type_id": str(get_attr(entity, "entity_type_id")) if get_attr(entity, "entity_type_id") else None,
        "group_id": group_id,
        "group_name": group_name,
        "parent_id": parent_id,
        "parent_name": parent_name,
        "thumbnail_id": possible_thumbnail(entity),
    }


def get_columns(project_id, entity_type):
    return RestrictedMetadataField.query.filter_by(
        project_id=to_uuid_or_none(project_id),
        entity_type=entity_type,
        is_active=True,
    ).order_by(
        RestrictedMetadataField.sort_order,
        RestrictedMetadataField.name,
    ).all()


def get_values_for_rows(entity_type, row_ids):
    if not row_ids:
        return {}

    values = RestrictedMetadataValue.query.filter(
        RestrictedMetadataValue.entity_type == entity_type,
        RestrictedMetadataValue.entity_id.in_([UUID(str(row_id)) for row_id in row_ids]),
    ).all()

    result = {}
    for value in values:
        entity_id = str(value.entity_id)
        field_id = str(value.field_id)

        if entity_id not in result:
            result[entity_id] = {}

        result[entity_id][field_id] = value.value_json

    return result


def make_table_response(project_id, entity_type, rows):
    columns = get_columns(project_id, entity_type)
    values_by_entity = get_values_for_rows(entity_type, [row["id"] for row in rows])

    return {
        "entity_type": entity_type,
        "columns": [field_to_dict(column) for column in columns],
        "rows": [
            {
                **row,
                "values": values_by_entity.get(row["id"], {}),
            }
            for row in rows
        ],
    }


def get_episode_map(project_id):
    episodes = shots_service.get_episodes_for_project(project_id)
    return {
        str(get_attr(episode, "id")): get_attr(episode, "name") or ""
        for episode in episodes
    }


def get_sequence_map(project_id):
    sequences = shots_service.get_sequences_for_project(project_id)
    return {
        str(get_attr(sequence, "id")): get_attr(sequence, "name") or ""
        for sequence in sequences
    }


def get_asset_type_map(project_id):
    asset_types = assets_service.get_asset_types_for_project(project_id)
    return {
        str(get_attr(asset_type, "id")): get_attr(asset_type, "name") or ""
        for asset_type in asset_types
    }


def build_episode_rows(project_id):
    return [
        entity_to_dict(episode)
        for episode in shots_service.get_episodes_for_project(project_id)
    ]


def build_sequence_rows(project_id, episode_id=None):
    episode_map = get_episode_map(project_id)

    if episode_id:
        sequences = shots_service.get_sequences_for_episode(episode_id)
    else:
        sequences = shots_service.get_sequences_for_project(project_id)

    rows = []
    for sequence in sequences:
        seq_episode_id = str(get_entity_parent_id(sequence)) if get_entity_parent_id(sequence) else None
        group_name = episode_map.get(seq_episode_id, "No Episode") if seq_episode_id else "No Episode"

        rows.append(
            entity_to_dict(
                sequence,
                group_id=seq_episode_id,
                group_name=group_name,
                parent_id=seq_episode_id,
                parent_name=group_name,
            )
        )

    rows.sort(key=lambda row: ((row["group_name"] or ""), row["name"] or ""))
    return rows


def build_shot_rows(project_id, episode_id=None, sequence_id=None):
    sequence_map = get_sequence_map(project_id)

    if episode_id:
        shots = shots_service.get_shots_for_episode(episode_id)
    else:
        shots = shots_service.get_shots_for_project(project_id)

    if sequence_id:
        shots = [
            shot for shot in shots
            if str(get_entity_parent_id(shot)) == str(sequence_id)
        ]

    rows = []
    for shot in shots:
        shot_sequence_id = str(get_entity_parent_id(shot)) if get_entity_parent_id(shot) else None
        group_name = sequence_map.get(shot_sequence_id, "No Sequence") if shot_sequence_id else "No Sequence"

        rows.append(
            entity_to_dict(
                shot,
                group_id=shot_sequence_id,
                group_name=group_name,
                parent_id=shot_sequence_id,
                parent_name=group_name,
            )
        )

    rows.sort(key=lambda row: ((row["group_name"] or ""), row["name"] or ""))
    return rows


def build_asset_rows(project_id, asset_type_id=None):
    asset_type_map = get_asset_type_map(project_id)
    assets = assets_service.get_assets({"project_id": project_id}, is_admin=True)

    if asset_type_id:
        assets = [
            asset for asset in assets
            if str(get_attr(asset, "entity_type_id")) == str(asset_type_id)
        ]

    rows = []
    for asset in assets:
        asset_group_id = str(get_attr(asset, "entity_type_id")) if get_attr(asset, "entity_type_id") else None
        group_name = asset_type_map.get(asset_group_id, "No Asset Type") if asset_group_id else "No Asset Type"

        rows.append(
            entity_to_dict(
                asset,
                group_id=asset_group_id,
                group_name=group_name,
            )
        )

    rows.sort(key=lambda row: ((row["group_name"] or ""), row["name"] or ""))
    return rows


def serialise_csv_value(value):
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if value is True:
        return "TRUE"
    if value is False:
        return "FALSE"
    if value is None:
        return ""
    return str(value)


class HealthResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()
        return {"status": "ok", "plugin": "restricted-metadata"}


class ProjectContextResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = get_project_id()
        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        project = projects_service.get_project(project_id)
        episodes = shots_service.get_episodes_for_project(project_id)

        return {
            "project": {
                "id": str(project["id"]),
                "name": project.get("name"),
                "has_episodes": len(episodes) > 0,
            }
        }


class ColumnsResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = get_project_id()
        entity_type = request.args.get("entity_type")

        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        query = RestrictedMetadataField.query.filter_by(
            project_id=UUID(str(project_id)),
            is_active=True,
        )

        if entity_type:
            query = query.filter_by(entity_type=entity_type)

        columns = query.order_by(
            RestrictedMetadataField.entity_type,
            RestrictedMetadataField.sort_order,
            RestrictedMetadataField.name,
        ).all()

        return {"columns": [field_to_dict(column) for column in columns]}

    @jwt_required()
    def post(self):
        require_admin()
        data = request.get_json() or {}

        project_id = data.get("project_id") or data.get("production_id")
        entity_type = data.get("entity_type")
        name = data.get("name")
        field_type = data.get("field_type")

        if not project_id:
            return {"error": "project_id or production_id is required"}, 400
        if entity_type not in VALID_ENTITY_TYPES:
            return {"error": "invalid entity_type"}, 400
        if not name:
            return {"error": "name is required"}, 400
        if field_type not in VALID_FIELD_TYPES:
            return {"error": "invalid field_type"}, 400

        column = RestrictedMetadataField.create(
            project_id=UUID(str(project_id)),
            entity_type=entity_type,
            name=name,
            field_type=field_type,
            options_json=data.get("options_json") or [],
            default_value=data.get("default_value"),
            is_required=bool(data.get("is_required", False)),
            is_active=True,
            sort_order=int(data.get("sort_order", 0)),
        )

        return {"column": field_to_dict(column)}, 201


class ColumnResource(Resource):
    @jwt_required()
    def patch(self, column_id):
        require_admin()
        column = RestrictedMetadataField.get(column_id)
        data = request.get_json() or {}

        for key in [
            "name",
            "field_type",
            "options_json",
            "default_value",
            "is_required",
            "is_active",
            "sort_order",
        ]:
            if key in data:
                setattr(column, key, data[key])

        db.session.commit()
        return {"column": field_to_dict(column)}

    @jwt_required()
    def delete(self, column_id):
        require_admin()
        column = RestrictedMetadataField.get(column_id)
        column.is_active = False
        db.session.commit()
        return {"deleted": True}


class EpisodeGroupsResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = get_project_id()
        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        episodes = shots_service.get_episodes_for_project(project_id)
        sequences = shots_service.get_sequences_for_project(project_id)

        counts = {}
        for sequence in sequences:
            episode_id = str(get_entity_parent_id(sequence)) if get_entity_parent_id(sequence) else None
            counts[episode_id] = counts.get(episode_id, 0) + 1

        groups = []
        for episode in episodes:
            episode_id = str(get_attr(episode, "id"))
            count = counts.get(episode_id, 0)

            if count > 0:
                groups.append({
                    "id": episode_id,
                    "name": get_attr(episode, "name") or "",
                    "count": count,
                })

        return {"groups": groups}


class SequenceGroupsResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = get_project_id()
        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        sequences = shots_service.get_sequences_for_project(project_id)
        shots = shots_service.get_shots_for_project(project_id)

        counts = {}
        for shot in shots:
            sequence_id = str(get_entity_parent_id(shot)) if get_entity_parent_id(shot) else None
            counts[sequence_id] = counts.get(sequence_id, 0) + 1

        groups = []
        for sequence in sequences:
            sequence_id = str(get_attr(sequence, "id"))
            count = counts.get(sequence_id, 0)

            if count > 0:
                groups.append({
                    "id": sequence_id,
                    "name": get_attr(sequence, "name") or "",
                    "count": count,
                })

        return {"groups": groups}


class AssetTypeGroupsResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = get_project_id()
        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        asset_types = assets_service.get_asset_types_for_project(project_id)
        assets = assets_service.get_assets({"project_id": project_id}, is_admin=True)

        counts = {}
        for asset in assets:
            asset_type_id = str(get_attr(asset, "entity_type_id")) if get_attr(asset, "entity_type_id") else None
            counts[asset_type_id] = counts.get(asset_type_id, 0) + 1

        groups = []
        for asset_type in asset_types:
            asset_type_id = str(get_attr(asset_type, "id"))
            count = counts.get(asset_type_id, 0)

            if count > 0:
                groups.append({
                    "id": asset_type_id,
                    "name": get_attr(asset_type, "name") or "",
                    "count": count,
                })

        return {"groups": groups}


class EpisodeRowsResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = get_project_id()
        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        return make_table_response(project_id, "episode", build_episode_rows(project_id))


class SequenceRowsResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = get_project_id()
        episode_id = request.args.get("episode_id")

        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        return make_table_response(project_id, "sequence", build_sequence_rows(project_id, episode_id))


class ShotRowsResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = get_project_id()
        episode_id = request.args.get("episode_id")
        sequence_id = request.args.get("sequence_id")

        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        return make_table_response(project_id, "shot", build_shot_rows(project_id, episode_id, sequence_id))


class AssetRowsResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = get_project_id()
        asset_type_id = request.args.get("asset_type_id")

        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        return make_table_response(project_id, "asset", build_asset_rows(project_id, asset_type_id))


class CellResource(Resource):
    @jwt_required()
    def post(self):
        require_admin()
        data = request.get_json() or {}

        field_id = UUID(str(data["field_id"]))
        entity_type = data["entity_type"]
        entity_id = UUID(str(data["entity_id"]))
        value_json = data.get("value")

        if entity_type not in VALID_ENTITY_TYPES:
            return {"error": "invalid entity_type"}, 400

        existing = RestrictedMetadataValue.query.filter_by(
            field_id=field_id,
            entity_type=entity_type,
            entity_id=entity_id,
        ).first()

        if existing:
            existing.value_json = value_json
            db.session.commit()
            return {"value": value_to_dict(existing)}

        value = RestrictedMetadataValue.create(
            field_id=field_id,
            entity_type=entity_type,
            entity_id=entity_id,
            value_json=value_json,
        )

        return {"value": value_to_dict(value)}, 201


class BulkSetResource(Resource):
    @jwt_required()
    def post(self):
        require_admin()
        data = request.get_json() or {}

        field_id = UUID(str(data["field_id"]))
        entity_type = data["entity_type"]
        entity_ids = data.get("entity_ids", [])
        new_value = data.get("value")

        if entity_type not in VALID_ENTITY_TYPES:
            return {"error": "invalid entity_type"}, 400

        updated = 0

        for entity_id_raw in entity_ids:
            entity_id = UUID(str(entity_id_raw))

            value = RestrictedMetadataValue.query.filter_by(
                field_id=field_id,
                entity_type=entity_type,
                entity_id=entity_id,
            ).first()

            if value:
                value.value_json = new_value
            else:
                RestrictedMetadataValue.create(
                    field_id=field_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    value_json=new_value,
                )

            updated += 1

        db.session.commit()
        return {"updated": updated}


class AssetTypesResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = get_project_id()
        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        asset_types = assets_service.get_asset_types_for_project(project_id)

        return {
            "asset_types": [
                {
                    "id": str(get_attr(asset_type, "id")),
                    "name": get_attr(asset_type, "name"),
                }
                for asset_type in asset_types
            ]
        }


class ExportJsonResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = get_project_id()

        query = RestrictedMetadataField.query.filter_by(is_active=True)
        if project_id:
            query = query.filter_by(project_id=UUID(str(project_id)))

        columns = query.order_by(
            RestrictedMetadataField.entity_type,
            RestrictedMetadataField.sort_order,
            RestrictedMetadataField.name,
        ).all()

        column_ids = [column.id for column in columns]

        values = RestrictedMetadataValue.query.filter(
            RestrictedMetadataValue.field_id.in_(column_ids)
        ).all() if column_ids else []

        return {
            "columns": [field_to_dict(column) for column in columns],
            "values": [value_to_dict(value) for value in values],
        }


class ExportCsvResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = get_project_id()
        entity_type = request.args.get("entity_type")

        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        if entity_type not in VALID_ENTITY_TYPES:
            return {"error": "valid entity_type is required"}, 400

        columns = get_columns(project_id, entity_type)

        if entity_type == "episode":
            rows = build_episode_rows(project_id)
        elif entity_type == "sequence":
            rows = build_sequence_rows(project_id)
        elif entity_type == "shot":
            rows = build_shot_rows(project_id)
        elif entity_type == "asset":
            rows = build_asset_rows(project_id)
        else:
            rows = []

        values_by_entity = get_values_for_rows(entity_type, [row["id"] for row in rows])

        output = io.StringIO()
        writer = csv.writer(output)

        header = ["Group", "Name"]
        header += [column.name for column in columns]
        writer.writerow(header)

        for row in rows:
            values = values_by_entity.get(row["id"], {})
            csv_row = [
                row.get("group_name") or "",
                row.get("name") or "",
            ]

            for column in columns:
                csv_row.append(serialise_csv_value(values.get(str(column.id))))

            writer.writerow(csv_row)

        filename = f"restricted_metadata_{entity_type}.csv"

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            },
        )
