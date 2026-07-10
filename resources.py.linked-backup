import ast
import csv
import io
import re
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
    "formula",
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

def get_asset_pack_id(asset):
    """
    Episode-specific assets may be linked through parent_id, source_id,
    episode_id, or legacy/custom data keys depending on Zou/Kitsu version.
    If no episode-like owner is found, treat the asset as Main Pack.
    """
    for key in ("parent_id", "source_id", "episode_id"):
        value = get_attr(asset, key)
        if value:
            return str(value)

    data = get_attr(asset, "data") or {}
    if isinstance(data, dict):
        for key in ("episode_id", "parent_id", "source_id"):
            value = data.get(key)
            if value:
                return str(value)

    return "main-pack"




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
    values_by_entity = add_formula_values(rows, columns, values_by_entity)

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


def build_asset_rows(project_id, asset_type_id=None, parent_id=None):
    asset_type_map = get_asset_type_map(project_id)
    assets = assets_service.get_assets({"project_id": project_id}, is_admin=True)

    if asset_type_id:
        assets = [
            asset for asset in assets
            if str(get_attr(asset, "entity_type_id")) == str(asset_type_id)
        ]

    if parent_id:
        assets = [
            asset for asset in assets
            if get_asset_pack_id(asset) == str(parent_id)
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
                parent_id=get_asset_pack_id(asset),
                parent_name="Main Pack" if get_asset_pack_id(asset) == "main-pack" else None,
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


def get_formula_text(column):
    options = column.options_json

    if not options:
        return ""

    if isinstance(options, dict):
        return options.get("formula") or ""

    if isinstance(options, list):
        return " ".join(str(item) for item in options)

    return str(options)


def normalise_formula_expression(expression):
    expression = re.sub(
        r"(\d+(?:\.\d+)?)\s*%",
        lambda match: f"({match.group(1)}/100)",
        expression,
    )
    expression = expression.replace("^", "**")
    return expression


def safe_eval_formula_expression(expression):
    tree = ast.parse(expression, mode="eval")

    def eval_node(node):
        if isinstance(node, ast.Expression):
            return eval_node(node.body)

        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Invalid constant")

        if isinstance(node, ast.UnaryOp):
            value = eval_node(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +value
            if isinstance(node.op, ast.USub):
                return -value
            raise ValueError("Invalid unary operator")

        if isinstance(node, ast.BinOp):
            left = eval_node(node.left)
            right = eval_node(node.right)

            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                return left ** right

            raise ValueError("Invalid binary operator")

        raise ValueError("Invalid expression")

    result = eval_node(tree)

    if not isinstance(result, (int, float)):
        raise ValueError("Invalid result")

    if result == float("inf") or result == float("-inf"):
        raise ValueError("Invalid result")

    return result


def evaluate_formula_column(row_values, columns, formula_column, visited=None):
    if visited is None:
        visited = set()

    formula_column_id = str(formula_column.id)

    if formula_column_id in visited:
        raise ValueError("Circular formula reference")

    visited.add(formula_column_id)

    formula = get_formula_text(formula_column).strip()

    if not formula:
        return ""

    columns_by_name = {column.name: column for column in columns}

    def replace_column_reference(match):
        column_name = match.group(1)
        referenced_column = columns_by_name.get(column_name)

        if referenced_column is None:
            raise ValueError("Unknown column")

        referenced_field_id = str(referenced_column.id)

        if referenced_column.field_type in {"tags", "checklist"}:
            raise ValueError("Invalid formula column type")

        if referenced_column.field_type == "formula":
            return str(
                evaluate_formula_column(
                    row_values,
                    columns,
                    referenced_column,
                    set(visited),
                )
            )

        raw_value = row_values.get(referenced_field_id)

        if referenced_column.field_type == "checkbox":
            return "1" if raw_value is True else "0"

        number_value = float(raw_value)

        return str(number_value)

    formula = re.sub(r"\[([^\]]+)\]", replace_column_reference, formula)
    formula = normalise_formula_expression(formula)

    if not re.match(r"^[0-9+\-*/().\s*]+$", formula):
        raise ValueError("Unsafe formula")

    result = safe_eval_formula_expression(formula)

    if int(result) == result:
        return int(result)

    return result


def add_formula_values(rows, columns, values_by_entity):
    formula_columns = [
        column for column in columns
        if column.field_type == "formula"
    ]

    if not formula_columns:
        return values_by_entity

    for row in rows:
        row_id = row["id"]
        row_values = dict(values_by_entity.get(row_id, {}))

        for formula_column in formula_columns:
            formula_field_id = str(formula_column.id)

            try:
                row_values[formula_field_id] = evaluate_formula_column(
                    row_values,
                    columns,
                    formula_column,
                )
            except Exception:
                row_values[formula_field_id] = "ERROR"

        values_by_entity[row_id] = row_values

    return values_by_entity


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



class ShotNestedGroupsResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = get_project_id()
        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        episodes = shots_service.get_episodes_for_project(project_id)
        sequences = shots_service.get_sequences_for_project(project_id)
        shots = shots_service.get_shots_for_project(project_id)

        shot_counts_by_sequence = {}
        for shot in shots:
            sequence_id = str(get_entity_parent_id(shot)) if get_entity_parent_id(shot) else None
            shot_counts_by_sequence[sequence_id] = shot_counts_by_sequence.get(sequence_id, 0) + 1

        sequences_by_episode = {}
        for sequence in sequences:
            sequence_id = str(get_attr(sequence, "id"))
            count = shot_counts_by_sequence.get(sequence_id, 0)

            if count <= 0:
                continue

            episode_id = str(get_entity_parent_id(sequence)) if get_entity_parent_id(sequence) else "no-episode"

            if episode_id not in sequences_by_episode:
                sequences_by_episode[episode_id] = []

            sequences_by_episode[episode_id].append({
                "id": sequence_id,
                "name": get_attr(sequence, "name") or "",
                "count": count,
            })

        groups = []
        for episode in episodes:
            episode_id = str(get_attr(episode, "id"))
            children = sorted(
                sequences_by_episode.get(episode_id, []),
                key=lambda item: item["name"],
            )

            if not children:
                continue

            groups.append({
                "id": episode_id,
                "name": get_attr(episode, "name") or "",
                "count": sum(child["count"] for child in children),
                "children": children,
            })

        no_episode_children = sorted(
            sequences_by_episode.get("no-episode", []),
            key=lambda item: item["name"],
        )

        if no_episode_children:
            groups.append({
                "id": "no-episode",
                "name": "No Episode",
                "count": sum(child["count"] for child in no_episode_children),
                "children": no_episode_children,
            })

        return {"groups": groups}


class AssetNestedGroupsResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = get_project_id()
        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        episodes = shots_service.get_episodes_for_project(project_id)
        asset_types = assets_service.get_asset_types_for_project(project_id)
        assets = assets_service.get_assets({"project_id": project_id}, is_admin=True)

        asset_type_map = {
            str(get_attr(asset_type, "id")): get_attr(asset_type, "name") or ""
            for asset_type in asset_types
        }

        children_by_pack = {}

        for asset in assets:
            pack_id = get_asset_pack_id(asset)
            asset_type_id = str(get_attr(asset, "entity_type_id")) if get_attr(asset, "entity_type_id") else "no-asset-type"

            if pack_id not in children_by_pack:
                children_by_pack[pack_id] = {}

            if asset_type_id not in children_by_pack[pack_id]:
                children_by_pack[pack_id][asset_type_id] = {
                    "id": asset_type_id,
                    "name": asset_type_map.get(asset_type_id, "No Asset Type"),
                    "count": 0,
                }

            children_by_pack[pack_id][asset_type_id]["count"] += 1

        groups = []

        main_pack_children = sorted(
            [
                child for child in children_by_pack.get("main-pack", {}).values()
                if child["count"] > 0
            ],
            key=lambda item: item["name"],
        )

        if main_pack_children:
            groups.append({
                "id": "main-pack",
                "name": "Main Pack",
                "count": sum(child["count"] for child in main_pack_children),
                "children": main_pack_children,
            })

        for episode in episodes:
            episode_id = str(get_attr(episode, "id"))
            children = sorted(
                [
                    child for child in children_by_pack.get(episode_id, {}).values()
                    if child["count"] > 0
                ],
                key=lambda item: item["name"],
            )

            if not children:
                continue

            groups.append({
                "id": episode_id,
                "name": get_attr(episode, "name") or "",
                "count": sum(child["count"] for child in children),
                "children": children,
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
        parent_id = request.args.get("parent_id")

        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        return make_table_response(project_id, "asset", build_asset_rows(project_id, asset_type_id, parent_id))


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
        episodes = shots_service.get_episodes_for_project(project_id)
        has_episodes = len(episodes) > 0

        episode_map = {
            str(get_attr(episode, "id")): get_attr(episode, "name") or ""
            for episode in episodes
        }

        sequence_map = get_sequence_map(project_id)

        sequence_episode_map = {}
        for sequence in shots_service.get_sequences_for_project(project_id):
            sequence_id = str(get_attr(sequence, "id"))
            episode_id = str(get_entity_parent_id(sequence)) if get_entity_parent_id(sequence) else None
            sequence_episode_map[sequence_id] = episode_map.get(episode_id, "No Episode") if episode_id else "No Episode"

        if entity_type == "episode":
            rows = build_episode_rows(project_id)
            hierarchy_header = ["Episode"]

            def hierarchy_values(row):
                return [row.get("name") or ""]

        elif entity_type == "sequence":
            rows = build_sequence_rows(project_id)
            hierarchy_header = ["Episode", "Sequence"] if has_episodes else ["Sequence"]

            def hierarchy_values(row):
                if has_episodes:
                    return [row.get("group_name") or "No Episode", row.get("name") or ""]
                return [row.get("name") or ""]

        elif entity_type == "shot":
            rows = build_shot_rows(project_id)
            hierarchy_header = ["Episode", "Sequence", "Shot"] if has_episodes else ["Sequence", "Shot"]

            def hierarchy_values(row):
                sequence_id = row.get("sequence_id")
                sequence_name = row.get("group_name") or sequence_map.get(sequence_id, "No Sequence")

                if has_episodes:
                    episode_name = sequence_episode_map.get(sequence_id, "No Episode")
                    return [episode_name, sequence_name, row.get("name") or ""]

                return [sequence_name, row.get("name") or ""]

        elif entity_type == "asset":
            rows = build_asset_rows(project_id)
            hierarchy_header = ["Episode / Main Pack", "Asset Type", "Asset"] if has_episodes else ["Asset Type", "Asset"]

            def hierarchy_values(row):
                asset_type_name = row.get("group_name") or "No Asset Type"

                if has_episodes:
                    parent_id = row.get("parent_id")
                    pack_name = "Main Pack" if parent_id == "main-pack" else episode_map.get(parent_id, "Main Pack")
                    return [pack_name, asset_type_name, row.get("name") or ""]

                return [asset_type_name, row.get("name") or ""]

        else:
            rows = []
            hierarchy_header = ["Name"]

            def hierarchy_values(row):
                return [row.get("name") or ""]

        values_by_entity = get_values_for_rows(entity_type, [row["id"] for row in rows])
        values_by_entity = add_formula_values(rows, columns, values_by_entity)

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(hierarchy_header + [column.name for column in columns])

        for row in rows:
            values = values_by_entity.get(row["id"], {})
            csv_row = hierarchy_values(row)

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

