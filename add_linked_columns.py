#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path.cwd()
RESOURCES = ROOT / "resources.py"
INIT = ROOT / "__init__.py"
FRONTEND = ROOT / "frontend" / "dist" / "index.html"


def backup(path: Path) -> None:
    target = path.with_suffix(path.suffix + ".linked-backup")
    shutil.copy2(path, target)
    print(f"Backup: {target}")


def require_files() -> None:
    missing = [str(p) for p in (RESOURCES, INIT, FRONTEND) if not p.exists()]
    if missing:
        raise SystemExit("Missing required files:\n" + "\n".join(missing))


def insert_before(text: str, marker: str, addition: str, label: str) -> str:
    if addition.strip() in text:
        return text
    if marker not in text:
        raise RuntimeError(f"Could not find marker for {label}: {marker}")
    return text.replace(marker, addition + marker, 1)


def patch_resources() -> None:
    text = RESOURCES.read_text()

    if '"linked"' not in text:
        text = re.sub(
            r'(VALID_FIELD_TYPES\s*=\s*\{.*?"formula"\s*,?)',
            r'\1\n    "linked",',
            text,
            count=1,
            flags=re.S,
        )

    if '"_native_data"' not in text:
        if '"thumbnail_id": possible_thumbnail(entity),' not in text:
            raise RuntimeError("Could not find entity_to_dict thumbnail field.")
        text = text.replace(
            '"thumbnail_id": possible_thumbnail(entity),',
            '"thumbnail_id": possible_thumbnail(entity),\n'
            '        "_native_data": get_attr(entity, "data") or {},',
            1,
        )

    helpers = r'''
def normalise_native_entity_type(value):
    value = str(value or "").strip().lower().replace("_", "").replace("-", "")
    aliases = {
        "episode": "episode",
        "episodes": "episode",
        "sequence": "sequence",
        "sequences": "sequence",
        "shot": "shot",
        "shots": "shot",
        "asset": "asset",
        "assets": "asset",
    }
    return aliases.get(value, value)


def get_native_metadata_descriptors(project_id, entity_type=None):
    descriptors = projects_service.get_metadata_descriptors(
        project_id,
        for_client=False,
    ) or []

    result = []

    for descriptor in descriptors:
        descriptor_entity_type = normalise_native_entity_type(
            get_attr(descriptor, "entity_type")
            or get_attr(descriptor, "for_entity")
            or get_attr(descriptor, "entity")
        )

        if entity_type and descriptor_entity_type != normalise_native_entity_type(entity_type):
            continue

        field_name = (
            get_attr(descriptor, "field_name")
            or get_attr(descriptor, "name")
            or ""
        )
        display_name = (
            get_attr(descriptor, "name")
            or get_attr(descriptor, "label")
            or field_name
        )
        native_type = (
            get_attr(descriptor, "data_type")
            or get_attr(descriptor, "field_type")
            or get_attr(descriptor, "type")
            or "text"
        )
        choices = (
            get_attr(descriptor, "choices")
            or get_attr(descriptor, "values")
            or get_attr(descriptor, "options")
            or []
        )

        if not field_name:
            continue

        result.append({
            "id": str(get_attr(descriptor, "id") or ""),
            "name": display_name,
            "field_name": field_name,
            "entity_type": descriptor_entity_type,
            "native_type": native_type,
            "choices": choices,
        })

    result.sort(key=lambda item: str(item["name"]).lower())
    return result


def add_linked_values(rows, columns, values_by_entity):
    linked_columns = [
        column for column in columns
        if column.field_type == "linked"
    ]

    if not linked_columns:
        return values_by_entity

    for row in rows:
        row_id = row["id"]
        row_values = dict(values_by_entity.get(row_id, {}))
        native_data = row.get("_native_data") or {}

        for column in linked_columns:
            options = column.options_json or {}
            options = options if isinstance(options, dict) else {}
            field_name = options.get("field_name")
            native_name = options.get("native_name")

            if field_name and field_name in native_data:
                value = native_data.get(field_name)
            elif native_name and native_name in native_data:
                value = native_data.get(native_name)
            else:
                value = ""

            row_values[str(column.id)] = value

        values_by_entity[row_id] = row_values

    return values_by_entity


def public_row(row, values):
    result = dict(row)
    result.pop("_native_data", None)
    result["values"] = values
    return result


def ensure_writable_column(field_id):
    column = RestrictedMetadataField.get(field_id)

    if column.field_type in {"formula", "linked"}:
        raise ValueError(
            f"{column.field_type.capitalize()} columns are read-only."
        )

    return column


'''

    text = insert_before(
        text,
        "def make_table_response(",
        helpers,
        "backend helpers",
    )

    match = re.search(
        r'def make_table_response\(project_id, entity_type, rows\):.*?\n(?=def get_episode_map)',
        text,
        flags=re.S,
    )
    if not match:
        raise RuntimeError("Could not locate make_table_response().")

    replacement = r'''def make_table_response(project_id, entity_type, rows):
    columns = get_columns(project_id, entity_type)
    values_by_entity = get_values_for_rows(
        entity_type,
        [row["id"] for row in rows],
    )
    values_by_entity = add_linked_values(rows, columns, values_by_entity)
    values_by_entity = add_formula_values(rows, columns, values_by_entity)

    return {
        "entity_type": entity_type,
        "columns": [field_to_dict(column) for column in columns],
        "rows": [
            public_row(
                row,
                values_by_entity.get(row["id"], {}),
            )
            for row in rows
        ],
    }


'''
    text = text[:match.start()] + replacement + text[match.end():]

    resource = r'''
class NativeMetadataDescriptorsResource(Resource):
    @jwt_required()
    def get(self):
        require_admin()

        project_id = get_project_id()
        entity_type = request.args.get("entity_type")

        if not project_id:
            return {"error": "project_id or production_id is required"}, 400

        if entity_type not in VALID_ENTITY_TYPES:
            return {"error": "valid entity_type is required"}, 400

        return {
            "descriptors": get_native_metadata_descriptors(
                project_id,
                entity_type,
            )
        }


'''
    text = insert_before(
        text,
        "class ColumnsResource(Resource):",
        resource,
        "native metadata resource",
    )

    validation = r'''
        if field_type == "linked":
            linked_config = data.get("options_json") or {}

            if not isinstance(linked_config, dict):
                return {"error": "linked options_json must be an object"}, 400

            if not linked_config.get("field_name"):
                return {"error": "linked field_name is required"}, 400

            descriptors = get_native_metadata_descriptors(
                project_id,
                entity_type,
            )
            descriptor = next(
                (
                    item for item in descriptors
                    if (
                        linked_config.get("descriptor_id")
                        and item["id"] == str(linked_config.get("descriptor_id"))
                    )
                    or item["field_name"] == linked_config.get("field_name")
                ),
                None,
            )

            if descriptor is None:
                return {
                    "error": "The selected native Kitsu metadata field was not found."
                }, 400

            data["options_json"] = {
                "descriptor_id": descriptor["id"],
                "field_name": descriptor["field_name"],
                "native_name": descriptor["name"],
                "native_type": descriptor["native_type"],
                "choices": descriptor.get("choices") or [],
            }

'''
    if validation.strip() not in text:
        text = insert_before(
            text,
            "        column = RestrictedMetadataField.create(",
            validation,
            "linked validation",
        )

    def add_write_guard(section: str) -> str:
        old = (
            '        field_id = UUID(str(data["field_id"]))\n'
            '        entity_type = data["entity_type"]'
        )
        new = (
            '        field_id = UUID(str(data["field_id"]))\n'
            '        try:\n'
            '            ensure_writable_column(field_id)\n'
            '        except ValueError as exc:\n'
            '            return {"error": str(exc)}, 400\n'
            '        entity_type = data["entity_type"]'
        )
        if "ensure_writable_column(field_id)" in section:
            return section
        if old not in section:
            raise RuntimeError("Could not insert read-only write guard.")
        return section.replace(old, new, 1)

    cell_start = text.find("class CellResource")
    bulk_start = text.find("class BulkSetResource")
    asset_types_start = text.find("class AssetTypesResource")
    if min(cell_start, bulk_start, asset_types_start) < 0:
        raise RuntimeError("Could not locate write resources.")

    cell = add_write_guard(text[cell_start:bulk_start])
    bulk = add_write_guard(text[bulk_start:asset_types_start])
    text = text[:cell_start] + cell + bulk + text[asset_types_start:]

    csv_start = text.find("class ExportCsvResource")
    if csv_start < 0:
        raise RuntimeError("Could not locate ExportCsvResource.")

    csv_section = text[csv_start:]
    if "add_linked_values(rows, columns, values_by_entity)" not in csv_section:
        csv_section, count = re.subn(
            r'(\s+values_by_entity\s*=\s*get_values_for_rows\(\s*entity_type,\s*\[row\["id"\]\s*for\s*row\s*in\s*rows\]\s*\)\s*)'
            r'(\s*values_by_entity\s*=\s*add_formula_values\(rows,\s*columns,\s*values_by_entity\))',
            r'\1        values_by_entity = add_linked_values(rows, columns, values_by_entity)\n\2',
            csv_section,
            count=1,
            flags=re.S,
        )
        if count != 1:
            raise RuntimeError("Could not add Linked values to CSV export.")

    text = text[:csv_start] + csv_section
    RESOURCES.write_text(text)
    print(f"Updated: {RESOURCES}")


def patch_init() -> None:
    text = INIT.read_text()

    if "NativeMetadataDescriptorsResource" not in text:
        if '    ("/context", resources.ProjectContextResource),\n' in text:
            text = text.replace(
                '    ("/context", resources.ProjectContextResource),\n',
                '    ("/context", resources.ProjectContextResource),\n'
                '    ("/native-metadata", resources.NativeMetadataDescriptorsResource),\n',
                1,
            )
        else:
            text, count = re.subn(
                r'(\("/context",\s*resources\.ProjectContextResource\),)',
                r'\1 ("/native-metadata", resources.NativeMetadataDescriptorsResource),',
                text,
                count=1,
            )
            if count != 1:
                raise RuntimeError("Could not add native-metadata route.")

    INIT.write_text(text)
    print(f"Updated: {INIT}")


def patch_frontend() -> None:
    text = FRONTEND.read_text()

    if '<option value="linked">Linked</option>' not in text:
        if '<option value="formula">Formula</option>' not in text:
            raise RuntimeError("Could not find Formula type option.")
        text = text.replace(
            '<option value="formula">Formula</option>',
            '<option value="formula">Formula</option>\n'
            '          <option value="linked">Linked</option>',
            1,
        )

    if 'id="linked-native-column"' not in text:
        match = re.search(r'(<input[^>]+id="column-options"[^>]*>)', text, re.S)
        if not match:
            raise RuntimeError("Could not find #column-options.")
        chooser = r'''
        <select id="linked-native-column" style="display:none">
          <option value="">Choose native Kitsu metadata…</option>
        </select>'''
        text = text[:match.end()] + chooser + text[match.end():]

    if "let nativeMetadataDescriptors" not in text:
        if "    let activePick = null;" not in text:
            raise RuntimeError("Could not locate frontend state.")
        text = text.replace(
            "    let activePick = null;",
            "    let activePick = null;\n"
            "    let nativeMetadataDescriptors = [];\n"
            "    let nativeMetadataEntityType = null;",
            1,
        )

    helpers = r'''
    async function loadNativeMetadataDescriptors(force = false) {
      if (
        !force &&
        nativeMetadataEntityType === entityType &&
        nativeMetadataDescriptors.length
      ) {
        populateLinkedNativeColumnSelector();
        return;
      }

      const data = await apiGet(
        "/native-metadata?production_id=" +
        encodeURIComponent(productionId) +
        "&entity_type=" +
        encodeURIComponent(entityType)
      );

      nativeMetadataDescriptors = data.descriptors || [];
      nativeMetadataEntityType = entityType;
      populateLinkedNativeColumnSelector();
    }

    function populateLinkedNativeColumnSelector() {
      const select = document.getElementById("linked-native-column");
      if (!select) return;

      select.innerHTML =
        '<option value="">Choose native Kitsu metadata…</option>';

      nativeMetadataDescriptors.forEach(descriptor => {
        const option = document.createElement("option");
        option.value = descriptor.id || descriptor.field_name;
        option.textContent =
          descriptor.name +
          (descriptor.native_type ? " (" + descriptor.native_type + ")" : "");
        option.dataset.fieldName = descriptor.field_name;
        option.dataset.nativeName = descriptor.name;
        option.dataset.nativeType = descriptor.native_type || "text";
        option.dataset.choices = JSON.stringify(descriptor.choices || []);
        select.appendChild(option);
      });
    }

    function linkedColumnConfigFromSelector() {
      const select = document.getElementById("linked-native-column");
      const option = select && select.options[select.selectedIndex];

      if (!option || !option.value) return null;

      let choices = [];
      try {
        choices = JSON.parse(option.dataset.choices || "[]");
      } catch (error) {
        choices = [];
      }

      return {
        descriptor_id: option.value,
        field_name: option.dataset.fieldName,
        native_name: option.dataset.nativeName,
        native_type: option.dataset.nativeType || "text",
        choices,
      };
    }

    function formatReadOnlyValue(value) {
      if (value === null || value === undefined) return "";
      if (Array.isArray(value)) return value.join(", ");
      if (typeof value === "object") return JSON.stringify(value);
      if (value === true) return "✓";
      if (value === false) return "";
      return String(value);
    }

'''
    text = insert_before(
        text,
        "    function renderCell(",
        helpers,
        "frontend Linked helpers",
    )

    renderer = '''      if (column.field_type === "linked") {
        return `<span class="formula-result linked-result">${escapeHtml(formatReadOnlyValue(value))}</span>`;
      }

'''
    render_marker = "    function renderCell(row, column, value) {\n"
    if renderer.strip() not in text:
        if render_marker not in text:
            raise RuntimeError("Could not find renderCell().")
        text = text.replace(render_marker, render_marker + renderer, 1)

    if 'linked: "Linked"' not in text:
        if 'formula: "Formula"' not in text:
            raise RuntimeError("Could not find fieldTypeLabel mapping.")
        text = text.replace(
            'formula: "Formula"',
            'formula: "Formula",\n        linked: "Linked"',
            1,
        )

    display_fn = text.find("function getColumnOptionsDisplay")
    if display_fn < 0:
        raise RuntimeError("Could not find getColumnOptionsDisplay().")
    display_end = text.find("function fieldTypeLabel", display_fn)
    display_section = text[display_fn:display_end]

    if 'column.field_type === "linked"' not in display_section:
        old = '''      if (column.field_type === "formula") {
        return getFormulaText(column);
      }'''
        new = '''      if (column.field_type === "formula") {
        return getFormulaText(column);
      }

      if (column.field_type === "linked") {
        const options = column.options_json || {};
        return options.native_name || options.field_name || "";
      }'''
        if old not in display_section:
            raise RuntimeError("Could not patch Linked display name.")
        display_section = display_section.replace(old, new, 1)
        text = text[:display_fn] + display_section + text[display_end:]

    update_fn = text.find("async function updateColumnOptions")
    update_end = text.find("async function deleteColumn", update_fn)
    update_section = text[update_fn:update_end]

    if 'column.field_type === "linked"' not in update_section:
        old = '''      if (column && column.field_type === "formula") {
        optionsJson = { formula: raw };
      } else {'''
        new = '''      if (column && column.field_type === "formula") {
        optionsJson = { formula: raw };
      } else if (column && column.field_type === "linked") {
        return;
      } else {'''
        if old not in update_section:
            raise RuntimeError("Could not patch updateColumnOptions().")
        update_section = update_section.replace(old, new, 1)
        text = text[:update_fn] + update_section + text[update_end:]

    change = re.search(
        r'    function onColumnTypeChange\(\) \{.*?\n    \}\n',
        text,
        re.S,
    )
    if not change:
        change = re.search(
            r'    async function onColumnTypeChange\(\) \{.*?\n    \}\n',
            text,
            re.S,
        )
    if not change:
        raise RuntimeError("Could not find onColumnTypeChange().")

    new_change = r'''    async function onColumnTypeChange() {
      const type = document.getElementById("column-type").value;
      const optionsInput = document.getElementById("column-options");
      const formulaTools = document.getElementById("formula-tools");
      const linkedSelect = document.getElementById("linked-native-column");

      optionsInput.style.display = "";
      linkedSelect.style.display = "none";

      if (type === "formula") {
        optionsInput.placeholder = "Formula, e.g. [Cost] * [Days]";
        formulaTools.classList.add("open");
      } else if (type === "linked") {
        formulaTools.classList.remove("open");
        optionsInput.style.display = "none";
        linkedSelect.style.display = "";
        await loadNativeMetadataDescriptors();
      } else {
        optionsInput.placeholder = "Options, comma separated";
        formulaTools.classList.remove("open");
      }
    }
'''
    text = text[:change.start()] + new_change + text[change.end():]

    create = re.search(
        r'    async function createColumn\(\) \{.*?\n    \}\n\n    function downloadCsv',
        text,
        re.S,
    )
    if not create:
        raise RuntimeError("Could not find createColumn().")

    block = create.group(0)
    if 'fieldType === "linked"' not in block:
        old = '''      if (fieldType === "formula") {
        options = { formula: rawOptions };
      } else {'''
        new = '''      if (fieldType === "formula") {
        options = { formula: rawOptions };
      } else if (fieldType === "linked") {
        options = linkedColumnConfigFromSelector();

        if (!options) {
          alert("Choose a native Kitsu metadata column to link.");
          return;
        }
      } else {'''
        if old not in block:
            raise RuntimeError("Could not patch createColumn().")
        block = block.replace(old, new, 1)
        text = text[:create.start()] + block + text[create.end():]

    if ".linked-result" not in text:
        old = '''    .formula-result {
      color: var(--text-strong);
      cursor: default;
    }'''
        new = '''    .formula-result {
      color: var(--text-strong);
      cursor: default;
    }

    .linked-result {
      opacity: 0.95;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }'''
        if old not in text:
            raise RuntimeError("Could not add Linked cell CSS.")
        text = text.replace(old, new, 1)

    FRONTEND.write_text(text)
    print(f"Updated: {FRONTEND}")


def main() -> None:
    require_files()

    for path in (RESOURCES, INIT, FRONTEND):
        backup(path)

    patch_resources()
    patch_init()
    patch_frontend()

    print("\nLinked-column support applied successfully.")
    print("Review with:")
    print("  git diff -- resources.py __init__.py frontend/dist/index.html")


if __name__ == "__main__":
    main()
