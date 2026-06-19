# Kitsu Restricted Metadata Plugin

Admin-only restricted metadata plugin for Kitsu / Zou.

This plugin adds private, project-scoped metadata columns for:

* Episodes
* Sequences
* Shots
* Assets

The metadata is stored in separate plugin database tables and does **not** appear in the standard Kitsu metadata panels.

Only Kitsu Admin users can access the plugin.

---

## Features

* Admin-only access
* Project-specific restricted metadata columns
* Spreadsheet-style editing
* Episode, Sequence, Shot and Asset tabs
* Film and TV / episodic project support
* Lazy-loaded tabs and groups
* Collapsible grouped sections
* Empty groups are hidden
* Kitsu-style table layout and internal scrolling
* Row selection and group selection
* Editing one selected row mirrors the edit to other selected rows
* CSV export with correct hierarchy per active tab
* JSON export
* Formula columns with calculated results
* Formula results included in API row responses and CSV export
* Supported field types:

  * Text
  * Number
  * Checkbox
  * List of values
  * List of tags
  * Checklist
  * Formula

---

## Project Structure Support

### Non-episodic / Film Projects

Sequences are shown directly.

Shots are grouped as:

```text
Sequence
└── Shot
```

Assets are grouped as:

```text
Asset Type
└── Asset
```

---

### Episodic / TV Projects

Sequences are grouped as:

```text
Episode
└── Sequence
```

Shots are grouped as:

```text
Episode
└── Sequence
    └── Shot
```

Assets are grouped as:

```text
Main Pack
└── Asset Type
    └── Asset

Episode
└── Asset Type
    └── Asset
```

---

## Formula Columns

Formula columns are read-only calculated columns.

The formula definition is stored in the plugin field configuration, but formula results are **not** stored as static database values. Results are calculated dynamically whenever rows are requested or CSV exports are generated.

This prevents stale calculated values if referenced cells are changed later.

### Formula Syntax

Reference other columns using square brackets:

```text
[Column Name]
```

Examples:

```text
[Cost] * [Days]
[Area] ^ 2
[Price] * 10%
[Subtotal] + [Tax]
[Total] + [Another Formula Column]
```

### Supported Operators

```text
+
-
*
/
^
()
%
```

### Percentages

```text
[Price] * 10%
```

is treated as:

```text
[Price] * 0.10
```

### Checkbox Values

Checkbox columns can be used in formulas.

```text
Checked = 1
Unchecked = 0
```

### Formula Columns Referencing Formula Columns

Formula columns can reference other formula columns.

Circular references are blocked and display:

```text
ERROR
```

### Unsupported Formula Inputs

These column types cannot be used inside formulas:

```text
List of tags
Checklist
```

Text and List of values columns can be used only if the cell value is numeric.

If a formula is invalid, the cell displays:

```text
ERROR
```

---

## Requirements

You need:

* A working Kitsu / Zou server
* Shell access to the server
* The Zou virtual environment, usually:

```bash
/opt/zou/zouenv
```

* The Zou CLI available at:

```bash
/opt/zou/zouenv/bin/zou
```

* The PostgreSQL database password used by Zou

In the examples below, replace:

```bash
YOUR_DB_PASSWORD
```

with your own Zou database password.

---

## Installation

### 1. Connect to your Kitsu server

SSH into the server where Zou is installed.

Example:

```bash
ssh ubuntu@YOUR-SERVER-IP
```

---

### 2. Install required command line tools

```bash
sudo apt update
sudo apt install -y git zip
```

---

### 3. Clone the plugin repository

```bash
cd ~
git clone https://github.com/PeteDraper/kitsu-restricted-metadata.git
cd kitsu-restricted-metadata
```

---

### 4. Activate the Zou virtual environment

```bash
. /opt/zou/zouenv/bin/activate
```

Your prompt should now show something like:

```bash
(zouenv) ubuntu@ubuntu:~/kitsu-restricted-metadata$
```

---

### 5. Make sure the Zou plugin directory exists

```bash
sudo mkdir -p /opt/zou/plugins
sudo chown -R ubuntu:ubuntu /opt/zou/plugins
```

If your Linux username is not `ubuntu`, replace `ubuntu:ubuntu` with your username.

Example:

```bash
sudo chown -R myuser:myuser /opt/zou/plugins
```

---

### 6. Build the plugin zip

```bash
cd ~/kitsu-restricted-metadata

rm -rf plugins
rm -f /tmp/restricted-metadata.zip

zip -r /tmp/restricted-metadata.zip . \
  -x ".git/*" \
  -x "plugins/*" \
  -x "__pycache__/*"
```

---

### 7. Install the plugin into Zou

Replace `YOUR_DB_PASSWORD` with your real Zou database password.

```bash
cd /opt/zou

DB_PASSWORD=YOUR_DB_PASSWORD \
/opt/zou/zouenv/bin/zou install-plugin \
--path /tmp/restricted-metadata.zip \
--force
```

Example:

```bash
cd /opt/zou

DB_PASSWORD=zC4LdTmrz9dM \
/opt/zou/zouenv/bin/zou install-plugin \
--path /tmp/restricted-metadata.zip \
--force
```

A successful install should show routes similar to:

```text
/plugins/restricted-metadata/health
/plugins/restricted-metadata/context
/plugins/restricted-metadata/columns
/plugins/restricted-metadata/columns/<column_id>
/plugins/restricted-metadata/groups/episodes
/plugins/restricted-metadata/groups/sequences
/plugins/restricted-metadata/groups/shot-episodes
/plugins/restricted-metadata/groups/asset-types
/plugins/restricted-metadata/groups/asset-packs
/plugins/restricted-metadata/rows/episodes
/plugins/restricted-metadata/rows/sequences
/plugins/restricted-metadata/rows/shots
/plugins/restricted-metadata/rows/assets
/plugins/restricted-metadata/cell
/plugins/restricted-metadata/bulk-set
/plugins/restricted-metadata/asset-types
/plugins/restricted-metadata/export/json
/plugins/restricted-metadata/export/csv
/plugins/restricted-metadata/frontend
/plugins/restricted-metadata/frontend/<path:filename>
```

---

### 8. Restart Zou

```bash
sudo systemctl restart zou
```

---

### 9. Hard refresh Kitsu

macOS:

```text
Cmd + Shift + R
```

Windows / Linux:

```text
Ctrl + Shift + R
```

---

## Testing the Installation

### 1. Test the plugin route locally

Run:

```bash
curl http://127.0.0.1:5000/plugins/restricted-metadata/health
```

If you are not authenticated, this should return a JWT warning such as:

```json
{"msg":"Missing JWT in cookies or headers"}
```

That is expected. It means the route exists and is protected.

---

### 2. Open Kitsu in your browser

Log in as an Admin user.

Open a project.

You should see the plugin entry in the Kitsu plugin menu.

Open:

```text
Restricted Metadata
```

---

## Using the Plugin

### 1. Choose an entity tab

Available tabs:

* Episodes
* Sequences
* Shots
* Assets

If the project does not use Episodes, the Episode tab is hidden.

---

### 2. Create a restricted metadata column

Click:

```text
Manage Columns
```

Enter:

```text
Column name
```

Choose a type:

```text
Text
Number
Checkbox
List of values
List of tags
Checklist
Formula
```

For these field types, enter comma-separated options:

```text
List of values
List of tags
Checklist
```

Example:

```text
Low, Medium, High
```

For Formula, enter the formula expression into the Options / Formula field.

Example:

```text
[Cost] * [Days]
```

Click:

```text
Create Column
```

The column appears in the current entity table.

---

### 3. Edit cells

Each row has its own private value for each restricted metadata column.

Example:

```text
Shot 001 | Vendor Grade = A
Shot 002 | Vendor Grade = B
Shot 003 | Vendor Grade = C
```

---

### 4. Bulk edit selected rows

Select multiple rows using the row checkboxes.

Then edit one selected row.

The same value is applied to all selected rows.

Group rows also have checkboxes:

* In Shots on non-episodic projects, selecting a Sequence group selects all loaded shots in that sequence.
* In Shots on episodic projects, selecting a Sequence group inside an Episode selects all loaded shots in that sequence.
* In Sequences on episodic projects, selecting an Episode group selects all loaded sequences in that episode.
* In Assets on non-episodic projects, selecting an Asset Type group selects all loaded assets in that asset type.
* In Assets on episodic projects, selecting an Asset Type group inside Main Pack or an Episode selects all loaded assets in that asset type.

Selections remain active until manually deselected.

---

## CSV Export

Click:

```text
Export CSV
```

CSV export follows the active tab and the project structure.

---

### Episodic Project CSV Layouts

Episodes:

```text
Episode,<custom columns>
```

Sequences:

```text
Episode,Sequence,<custom columns>
```

Shots:

```text
Episode,Sequence,Shot,<custom columns>
```

Assets:

```text
Episode / Main Pack,Asset Type,Asset,<custom columns>
```

---

### Non-Episodic Project CSV Layouts

Sequences:

```text
Sequence,<custom columns>
```

Shots:

```text
Sequence,Shot,<custom columns>
```

Assets:

```text
Asset Type,Asset,<custom columns>
```

Formula results are included in CSV exports.

---

## API Endpoints

CSV export:

```text
/api/plugins/restricted-metadata/export/csv?production_id=PROJECT_ID&entity_type=shot
```

JSON export:

```text
/api/plugins/restricted-metadata/export/json?production_id=PROJECT_ID
```

Valid CSV `entity_type` values:

```text
episode
sequence
shot
asset
```

---

## Updating the Plugin

To update to the latest GitHub version:

```bash
cd ~/kitsu-restricted-metadata
git pull origin main
```

Rebuild the zip:

```bash
rm -rf plugins
rm -f /tmp/restricted-metadata.zip

zip -r /tmp/restricted-metadata.zip . \
  -x ".git/*" \
  -x "plugins/*" \
  -x "__pycache__/*"
```

Reinstall:

```bash
cd /opt/zou

DB_PASSWORD=YOUR_DB_PASSWORD \
/opt/zou/zouenv/bin/zou install-plugin \
--path /tmp/restricted-metadata.zip \
--force
```

Restart Zou:

```bash
sudo systemctl restart zou
```

Hard refresh Kitsu in your browser:

```text
Cmd + Shift + R
```

or on Windows/Linux:

```text
Ctrl + Shift + R
```

---

## Publishing Changes to GitHub

After making local changes:

```bash
cd ~/kitsu-restricted-metadata

git status
git add -A
git commit -m "Update restricted metadata plugin"
git push origin main
```

Optional release tag:

```bash
git tag -a v0.3.0 -m "Nested groups formulas CSV export and UI refinements"
git push origin v0.3.0
```

---

## Troubleshooting

### Plugin route shows JWT error

This is normal when testing with curl:

```json
{"msg":"Missing JWT in cookies or headers"}
```

It means the plugin route exists and is protected.

---

### Plugin does not appear in Kitsu

Restart Zou:

```bash
sudo systemctl restart zou
```

Check the service:

```bash
sudo systemctl status zou --no-pager
```

Check logs:

```bash
sudo journalctl -u zou -n 120 --no-pager
```

---

### Plugin page says not found

Check that the frontend route was registered during installation:

```text
/plugins/restricted-metadata/frontend
/plugins/restricted-metadata/frontend/<path:filename>
```

If not, rebuild and reinstall the zip.

---

### Database password error

If installation or testing fails with:

```text
password authentication failed
```

make sure you are passing the database password:

```bash
DB_PASSWORD=YOUR_DB_PASSWORD /opt/zou/zouenv/bin/zou install-plugin --path /tmp/restricted-metadata.zip --force
```

---

### Existing old Checklist columns do not display correctly

Older development versions used:

```text
multi_select
```

The current version uses:

```text
checklist
```

To convert old columns:

```bash
cd /opt/zou

DB_PASSWORD=YOUR_DB_PASSWORD /opt/zou/zouenv/bin/python - <<'PY'
from zou.app import app, db
from sqlalchemy import text

with app.app_context():
    db.session.execute(text("""
        UPDATE plugin_restricted_metadata_fields
        SET field_type = 'checklist'
        WHERE field_type = 'multi_select'
    """))
    db.session.commit()
    print("Converted multi_select columns to checklist")
PY
```

Restart Zou afterwards:

```bash
sudo systemctl restart zou
```

---

### Formula columns show ERROR

Check the formula syntax.

Valid examples:

```text
[Cost] * [Days]
[Area] ^ 2
[Price] * 10%
[Subtotal] + [Tax]
```

Common causes of `ERROR`:

* Referenced column does not exist
* Referenced text value is not numeric
* Referenced List of values entry is not numeric
* Formula references a Tags column
* Formula references a Checklist column
* Formula has a circular reference
* Formula syntax is invalid

---

## Developer Notes

The plugin stores restricted metadata in separate plugin tables:

```text
plugin_restricted_metadata_fields
plugin_restricted_metadata_values
```

Formula definitions are stored in field configuration.

Formula results are calculated dynamically.

Formula results are not written as static cell values.

The plugin does not store restricted values in Kitsu’s standard custom metadata descriptors.

This is intentional because Kitsu’s normal metadata is visible through standard Kitsu entity pages and APIs, while this plugin is designed for Admin-only sensitive metadata.

---

## Security

This plugin is Admin-only.

All backend routes call Zou’s admin permission check before returning or changing data.

Do not use this plugin for non-admin access until role-based permissions have been intentionally added and tested.
