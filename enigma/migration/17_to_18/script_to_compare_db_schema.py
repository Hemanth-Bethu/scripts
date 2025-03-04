import psycopg2
import pandas as pd
import os
import re
import json

DB_HOST = "localhost"
DB_PORT = "5432"
DB_USER = "hemanth"
DB_PASSWORD = "hemanth@1234"
DB_17 = "enigma_17_uat"
DB_18 = "enigma18"

OUTPUT_DIR = "D:/projects/18/comparision"
DIFF_EXCEL_FILE = f"{OUTPUT_DIR}/schema_diff.xlsx"

TABLES_TO_MIGRATE = [
    "res_partner", "res_company", "res_users",
    "purchase_order", "contract", "contract_claim",
    "account_account", "xaana_account_component_type", "xaana_account_component",
    "xaana_account_component_ledger", "xaana_account_component_sequence",
    "xaana_account_component_account", "xaana_account_component_link",
    "invoicescan_voucher", "account_move", "account_group", "account_journal",
    "account_move_line", "account_tax", "payment_term", "invoice_payment_term",
    "currency", "partner_bank", "sale_order_template", "purchase_order_line",
    "sale_discount_product", "sale_down_payment_product", "contract_line",
    "approved_by", "reviewed_by", "rejected_by", "next_approver",
    "message_main_attachment", "document", "voucher_document",
    "voucher_document_job", "merged_pdf", "company_mail_server",
    "oauth_provider", "onboarding", "role", "industry", "fiscal_position",
    "incoterm", "resource_calendar", "state", "team", "user", "stock_move",
    "ir_attachment",
]


def parse_fk_reference(definition):
    """
    Extracts the referenced table and column from a Postgres FK definition string.
    Example:
        FOREIGN KEY (account_id) REFERENCES account_account(id) ON DELETE CASCADE
    Returns: (referenced_table, referenced_column) or (None, None) if not found.
    """
    match = re.search(r"REFERENCES\s+([^\s]+)\s*\(([^)]+)\)", definition, re.IGNORECASE)
    if match:
        ref_table = match.group(1)
        ref_col = match.group(2)
        return ref_table, ref_col
    return None, None


def parse_fk_local_columns(definition):
    """
    Extract the local column(s) from a constraint definition.
    Example:
        FOREIGN KEY (account_id) REFERENCES account_account(id) ON DELETE CASCADE
    Returns: list of local columns (often just 1).
    """
    local_match = re.search(r"FOREIGN KEY\s*\(([^)]+)\)", definition, re.IGNORECASE)
    if local_match:
        raw = local_match.group(1).strip()
        return [col.strip() for col in raw.split(",")]
    return []


def detect_many_to_many(schema, table):
    """
    Checks if 'table' is likely a many-to-many bridging table by:
      1. Having exactly TWO foreign keys.
      2. Possibly the table name ends with '_rel' (common pattern).
    """
    if table not in schema["foreign_keys"]:
        return False

    fks = schema["foreign_keys"][table]
    if len(fks) != 2:
        return False

    # Common Odoo bridging pattern _rel
    if table.endswith("_rel"):
        return True

    return True  # If you want to treat ANY table with exactly 2 FKs as bridging M2M


def get_schema_details(db_name):
    """
    Fetches table structures, indexes, foreign keys, views, sequences, triggers, and module mapping
    from a Postgres DB.
    Also fetches 'is_nullable' and 'column_default' for columns in DB_18 (only for 'db_name' param).
    We store them in schema["columns_extras"][table][column] = {
       "is_nullable": "YES"/"NO",
       "column_default": <string or None>
    }
    So we can identify not-null columns + default expressions.
    """
    schema = {
        "tables": {},
        "modules": {},
        "indexes": {},
        "foreign_keys": {},
        "views": {},
        "sequences": {},
        "triggers": {},
        "columns_extras": {}
    }

    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cur = conn.cursor()

        # Tables & Columns
        cur.execute("""
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position;
        """)
        for table, column, datatype, is_nullable, default_val in cur.fetchall():
            if table not in schema["tables"]:
                schema["tables"][table] = {}
            schema["tables"][table][column] = datatype

            if table not in schema["columns_extras"]:
                schema["columns_extras"][table] = {}
            schema["columns_extras"][table][column] = {
                "is_nullable": is_nullable,
                "column_default": default_val
            }

        # Table-to-Module Mapping
        cur.execute("""
            SELECT ir_model.model, ir_model_data.module
            FROM ir_model
            JOIN ir_model_data ON ir_model.id = ir_model_data.res_id
            WHERE ir_model_data.model = 'ir.model';
        """)
        for table_model, module in cur.fetchall():
            # Odoo model "res.company" => table "res_company"
            schema["modules"][table_model.replace(".", "_")] = module

        # Indexes
        cur.execute("""
            SELECT tablename, indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public';
        """)
        for table, index, definition in cur.fetchall():
            if table not in schema["indexes"]:
                schema["indexes"][table] = {}
            schema["indexes"][table][index] = definition

        # Foreign Keys
        cur.execute("""
            SELECT
                conrelid::regclass AS table_name,
                conname AS constraint_name,
                pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE contype = 'f'
            ORDER BY table_name;
        """)
        for table, constraint, definition in cur.fetchall():
            if table not in schema["foreign_keys"]:
                schema["foreign_keys"][table] = {}
            schema["foreign_keys"][table][constraint] = definition

        # Views
        cur.execute("""
            SELECT table_name, view_definition
            FROM information_schema.views
            WHERE table_schema = 'public';
        """)
        for view_name, definition in cur.fetchall():
            schema["views"][view_name] = definition

        # Sequences
        cur.execute("""
            SELECT c.relname as sequence_name
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'S' AND n.nspname = 'public';
        """)
        for (sequence_name,) in cur.fetchall():
            schema["sequences"][sequence_name] = "SEQUENCE"

        # Triggers
        cur.execute("""
            SELECT event_object_table, trigger_name, action_statement
            FROM information_schema.triggers
            WHERE trigger_schema = 'public';
        """)
        for table, trigger, action in cur.fetchall():
            if table not in schema["triggers"]:
                schema["triggers"][table] = {}
            schema["triggers"][table][trigger] = action

        cur.close()
        conn.close()
        print(f"✅ Full schema extracted successfully from {db_name}")
        return schema

    except Exception as e:
        print(f"❌ Error extracting schema from {db_name}: {e}")
        return {}


def compare_schemas(schema_17, schema_18):
    """
    Compares two database schemas and organizes differences into categories,
    ignoring 'old_enigma_id' field.
    """
    print("🔹 Comparing schemas...")

    schema_diffs = {
        "tables": [],
        "modules": [],
        "indexes": {},
        "foreign_keys": {},
        "views": {},
        "sequences": {},
        "triggers": {},
    }

    summary = []
    field_level_changes = []

    # Compare Tables
    tables_17 = set(schema_17["tables"].keys())
    tables_18 = set(schema_18["tables"].keys())

    added_tables = sorted(list(tables_18 - tables_17))
    removed_tables = sorted(list(tables_17 - tables_18))
    tables_with_diff = []
    unchanged_tables = []

    for table in tables_17.intersection(tables_18):
        cols_17 = schema_17["tables"][table]
        cols_18 = schema_18["tables"][table]

        # Ignore 'old_enigma_id'
        cols_17 = {k: v for k, v in cols_17.items() if k != "old_enigma_id"}
        cols_18 = {k: v for k, v in cols_18.items() if k != "old_enigma_id"}

        added_cols = set(cols_18.keys()) - set(cols_17.keys())
        removed_cols = set(cols_17.keys()) - set(cols_18.keys())
        modified_cols = {
            col: (cols_17[col], cols_18[col])
            for col in (cols_17.keys() & cols_18.keys())
            if cols_17[col] != cols_18[col]
        }

        if added_cols or removed_cols or modified_cols:
            tables_with_diff.append(table)
        else:
            unchanged_tables.append(table)

        # Record field-level changes
        for field in added_cols:
            field_level_changes.append({
                "Table Name": table,
                "Field Name": field,
                "Field Details": f"Type: {cols_18[field]}",
                "Status": "Added"
            })

        for field in removed_cols:
            field_level_changes.append({
                "Table Name": table,
                "Field Name": field,
                "Field Details": f"Type: {cols_17[field]}",
                "Status": "Removed"
            })

        for field, (old_type, new_type) in modified_cols.items():
            field_level_changes.append({
                "Table Name": table,
                "Field Name": field,
                "Field Details": f"Changed from {old_type} to {new_type}",
                "Status": "Changed"
            })

    # Compare Indexes
    for table, indexes in schema_17["indexes"].items():
        if table in schema_18["indexes"]:
            for index, definition in indexes.items():
                if index not in schema_18["indexes"][table]:
                    schema_diffs["indexes"].setdefault(table, {})[index] = "Removed"
                elif schema_18["indexes"][table][index] != definition:
                    schema_diffs["indexes"].setdefault(table, {})[index] = "Modified"

    for table, indexes in schema_18["indexes"].items():
        for index, definition in indexes.items():
            if table not in schema_17["indexes"] or index not in schema_17["indexes"][table]:
                schema_diffs["indexes"].setdefault(table, {})[index] = "Added"

    # Compare Foreign Keys
    for table, fks_17 in schema_17["foreign_keys"].items():
        if table in schema_18["foreign_keys"]:
            fks_18 = schema_18["foreign_keys"][table]
            for fk, definition in fks_17.items():
                if fk not in fks_18:
                    schema_diffs["foreign_keys"].setdefault(table, {})[fk] = "Removed"
                elif fks_18[fk] != definition:
                    schema_diffs["foreign_keys"].setdefault(table, {})[fk] = "Modified"

    for table, fks_18 in schema_18["foreign_keys"].items():
        if table in schema_17["foreign_keys"]:
            fks_17 = schema_17["foreign_keys"][table]
        else:
            fks_17 = {}
        for fk, definition in fks_18.items():
            if fk not in fks_17:
                schema_diffs["foreign_keys"].setdefault(table, {})[fk] = "Added"

    # Compare Views
    for view, definition in schema_17["views"].items():
        if view not in schema_18["views"]:
            schema_diffs["views"][view] = "Removed"
        elif schema_18["views"][view] != definition:
            schema_diffs["views"][view] = "Modified"

    for view, definition in schema_18["views"].items():
        if view not in schema_17["views"]:
            schema_diffs["views"][view] = "Added"

    # Compare Sequences
    for seq in schema_17["sequences"]:
        if seq not in schema_18["sequences"]:
            schema_diffs["sequences"][seq] = "Removed"

    for seq in schema_18["sequences"]:
        if seq not in schema_17["sequences"]:
            schema_diffs["sequences"][seq] = "Added"

    # Compare Triggers
    for table, triggers_17 in schema_17["triggers"].items():
        if table in schema_18["triggers"]:
            triggers_18 = schema_18["triggers"][table]
            for trig, action in triggers_17.items():
                if trig not in triggers_18:
                    schema_diffs["triggers"].setdefault(table, {})[trig] = "Removed"
                elif triggers_18[trig] != action:
                    schema_diffs["triggers"].setdefault(table, {})[trig] = "Modified"

    for table, triggers_18 in schema_18["triggers"].items():
        if table in schema_17["triggers"]:
            triggers_17 = schema_17["triggers"][table]
        else:
            triggers_17 = {}
        for trig, action in triggers_18.items():
            if trig not in triggers_17:
                schema_diffs["triggers"].setdefault(table, {})[trig] = "Added"

    # Summary
    summary.append({"Category": "Tables Added", "Count": len(added_tables)})
    summary.append({"Category": "Tables Removed", "Count": len(removed_tables)})
    summary.append({"Category": "Tables Modified", "Count": len(tables_with_diff)})
    summary.append({"Category": "Tables Unchanged", "Count": len(unchanged_tables)})

    return (
        schema_diffs,
        summary,
        added_tables,
        removed_tables,
        tables_with_diff,
        unchanged_tables,
        field_level_changes,
    )


def collect_relationship_info(schema):
    """
    Scan *every* foreign key in 'schema' once and build a dictionary of relationships that includes:
      - many2one from the child table perspective
      - one2many from the parent table perspective
      - many2many bridging if a table has exactly two FKs (and is recognized as bridging)

    Returns a dict:
      {
         "many2one": [ (child_table, child_col, parent_table, parent_col), ... ],
         "one2many": [ (parent_table, child_table, child_col), ... ],
         "many2many": [ (bridge_table, tableA, tableB), ... ],
      }
    """
    rel_info = {
        "many2one": [],
        "one2many": [],
        "many2many": []
    }

    # First gather bridging tables
    bridging_tables = []
    for t in schema["foreign_keys"]:
        if detect_many_to_many(schema, t):
            bridging_tables.append(t)

    # For each bridging table, find the two references
    for bt in bridging_tables:
        fks = schema["foreign_keys"][bt]
        fk_constraints = list(fks.items())  # list of (constraint_name, definition)
        if len(fk_constraints) != 2:
            continue
        # Usually 2 references
        (c1, d1), (c2, d2) = fk_constraints[0], fk_constraints[1]
        ref_table1, _ = parse_fk_reference(d1)
        ref_table2, _ = parse_fk_reference(d2)
        if ref_table1 and ref_table2:
            rel_info["many2many"].append((bt, ref_table1, ref_table2))

    # Now gather normal many2one from child → parent
    # We'll still do it for bridging tables, but we'll label them many2many separately
    for t in schema["foreign_keys"]:
        for constraint_name, definition in schema["foreign_keys"][t].items():
            ref_table, ref_col = parse_fk_reference(definition)
            local_cols = parse_fk_local_columns(definition)
            if not ref_table or not ref_col:
                continue

            # (A) child has many2one to parent
            rel_info["many2one"].append((t, local_cols, ref_table, [ref_col]))

            # (B) parent has one2many from child
            # (We link on the child table + child col. We store that so the user can see the inverse.)
            # We do NOT do this if the table is bridging and recognized as many2many
            # but if you want to see that as well, you can keep it anyway
            if t not in bridging_tables:  # if bridging, we skip or you can comment this check out
                # We can store the entire set of local cols for clarity
                rel_info["one2many"].append((ref_table, t, local_cols))

    return rel_info


def compare_schemas_with_relationships(schema_17, schema_18):
    """
    Compares schemas, then classifies each foreign key by:
      - Checking if the table is a bridging table (many-to-many).
      - Otherwise, many-to-one (from the local perspective).
      - Also collects the one2many side from the parent's perspective.
    """
    (
        schema_diffs,
        summary,
        added_tables,
        removed_tables,
        tables_with_diff,
        unchanged_tables,
        field_level_changes,
    ) = compare_schemas(schema_17, schema_18)

    updated_foreign_keys = []

    # We want to reflect changes that appear in 'schema_diffs["foreign_keys"]'
    # and label them with the correct relationship type
    for table, fks_dict in schema_diffs["foreign_keys"].items():
        for fk_constraint_name, status in fks_dict.items():
            definition_18 = schema_18["foreign_keys"].get(table, {}).get(fk_constraint_name)
            definition_17 = schema_17["foreign_keys"].get(table, {}).get(fk_constraint_name)
            if status == "Removed":
                fk_def = definition_17
            else:
                # 'Added' or 'Modified': parse the new
                fk_def = definition_18 if definition_18 else definition_17

            ref_table, ref_col = parse_fk_reference(fk_def) if fk_def else (None, None)
            # If bridging, we say many2many. Otherwise many2one from the child's perspective
            if detect_many_to_many(schema_18, table) or detect_many_to_many(schema_17, table):
                rel_type = "Many-to-Many"
            else:
                rel_type = "Many-to-One"

            details_text = f"{rel_type} Relationship"
            if ref_table and ref_col:
                details_text += f" → References {ref_table}({ref_col})"

            updated_foreign_keys.append({
                "Table Name": table,
                "Field Name": fk_constraint_name,
                "Change Type": "Foreign Key",
                "Details": details_text,
                "Status": status
            })

    return (
        schema_diffs,
        summary,
        added_tables,
        removed_tables,
        tables_with_diff,
        unchanged_tables,
        field_level_changes,
        updated_foreign_keys
    )


def save_diff_to_excel_with_relationships(
    schema_diffs,
    summary,
    added_tables,
    removed_tables,
    tables_with_diff,
    unchanged_tables,
    field_level_changes,
    updated_foreign_keys,
    schema_18
):
    """
    Saves schema comparison results to an Excel file, including:
      - Summary
      - Added/Removed/Modified Tables
      - Combined "Schema Changes" (columns + foreign keys)
      - Indexes, Views, Sequences, Triggers
      - ALSO saves a separate 'Relationships' sheet
        that enumerates many2one, one2many, many2many from the final (DB_18) perspective.
    """
    os.makedirs(os.path.dirname(DIFF_EXCEL_FILE), exist_ok=True)

    # Collect the final (DB_18) relationship info for a separate sheet
    full_relationships = collect_relationship_info(schema_18)

    # Flatten them for Excel
    m2one_rows = []
    for (child_table, child_cols, parent_table, parent_cols) in full_relationships["many2one"]:
        m2one_rows.append({
            "Relationship": "many2one",
            "Child Table": child_table,
            "Child Cols": ", ".join(child_cols),
            "Parent Table": parent_table,
            "Parent Cols": ", ".join(parent_cols)
        })

    o2m_rows = []
    for (parent_table, child_table, child_cols) in full_relationships["one2many"]:
        o2m_rows.append({
            "Relationship": "one2many",
            "Parent Table": parent_table,
            "Child Table": child_table,
            "Child Cols": ", ".join(child_cols)
        })

    m2m_rows = []
    for (bridge_table, tableA, tableB) in full_relationships["many2many"]:
        m2m_rows.append({
            "Relationship": "many2many",
            "Bridge Table": bridge_table,
            "Table A": tableA,
            "Table B": tableB
        })

    with pd.ExcelWriter(DIFF_EXCEL_FILE, engine="xlsxwriter") as writer:
        # 1) Summary
        df_summary = pd.DataFrame(summary)
        df_summary.to_excel(writer, sheet_name="Summary", index=False)

        # 2) Added/Removed/Modified
        if added_tables:
            df_added = pd.DataFrame({"Added Tables": added_tables})
            df_added.to_excel(writer, sheet_name="Added Tables", index=False)

        if removed_tables:
            df_removed = pd.DataFrame({"Removed Tables": removed_tables})
            df_removed.to_excel(writer, sheet_name="Removed Tables", index=False)

        if tables_with_diff:
            df_tbl_mod = pd.DataFrame({"Tables Modified": tables_with_diff})
            df_tbl_mod.to_excel(writer, sheet_name="Tables Modified", index=False)

        # 3) Combined "Schema Changes"
        schema_changes = []

        # Field-level changes
        for change in field_level_changes:
            schema_changes.append({
                "Table Name": change["Table Name"],
                "Field Name": change["Field Name"],
                "Change Type": "Column",
                "Details": change["Field Details"],
                "Status": change["Status"]
            })

        # Foreign key changes
        for fk_entry in updated_foreign_keys:
            schema_changes.append({
                "Table Name": fk_entry["Table Name"],
                "Field Name": fk_entry["Field Name"],
                "Change Type": fk_entry["Change Type"],
                "Details": fk_entry["Details"],
                "Status": fk_entry["Status"]
            })

        if schema_changes:
            df_schema_changes = pd.DataFrame(schema_changes)
            df_schema_changes.to_excel(writer, sheet_name="Schema Changes", index=False)

        # 4) Index Differences
        index_changes = []
        for table, indexes in schema_diffs["indexes"].items():
            for index, definition in indexes.items():
                index_changes.append({
                    "Table": table,
                    "Index Name": index,
                    "Definition": definition
                })
        if index_changes:
            df_indexes = pd.DataFrame(index_changes)
            df_indexes.to_excel(writer, sheet_name="Indexes", index=False)

        # 5) View Differences
        if schema_diffs["views"]:
            df_views = pd.DataFrame(list(schema_diffs["views"].items()),
                                    columns=["View Name", "Definition"])
            df_views.to_excel(writer, sheet_name="Views", index=False)

        # 6) Sequence Differences
        if schema_diffs["sequences"]:
            df_sequences = pd.DataFrame(list(schema_diffs["sequences"].items()),
                                        columns=["Sequence Name", "Type"])
            df_sequences.to_excel(writer, sheet_name="Sequences", index=False)

        # 7) Trigger Differences
        trigger_changes = []
        for table, triggers in schema_diffs["triggers"].items():
            for trig, action in triggers.items():
                trigger_changes.append({
                    "Table": table,
                    "Trigger Name": trig,
                    "Action": action
                })
        if trigger_changes:
            df_triggers = pd.DataFrame(trigger_changes)
            df_triggers.to_excel(writer, sheet_name="Triggers", index=False)

        # 8) Relationships: many2one, one2many, many2many
        #    from the final DB_18 schema perspective
        #    We'll put each in its own area of the "Relationships" sheet
        #    or as separate sheets if you prefer
        if m2one_rows or o2m_rows or m2m_rows:
            # If you want them on a single sheet, we’ll do something like below
            df_m2one = pd.DataFrame(m2one_rows)
            df_o2m = pd.DataFrame(o2m_rows)
            df_m2m = pd.DataFrame(m2m_rows)

            df_m2one.to_excel(writer, sheet_name="Relationships", startrow=0, index=False)
            row_offset = len(df_m2one) + 2
            df_o2m.to_excel(writer, sheet_name="Relationships", startrow=row_offset, index=False)
            row_offset += len(df_o2m) + 2
            df_m2m.to_excel(writer, sheet_name="Relationships", startrow=row_offset, index=False)

        print(f"✅ Schema differences + relationships saved to: {DIFF_EXCEL_FILE}")


def get_ir_model_data_mapping(db_name):
    """
    Fetch table-to-module mapping using ir_model_data in Odoo.
    """
    mapping = {}
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cur = conn.cursor()
        cur.execute("""
            SELECT ir_model.model, ir_model_data.module
            FROM ir_model
            JOIN ir_model_data ON ir_model.id = ir_model_data.res_id
            WHERE ir_model_data.model = 'ir.model';
        """)
        for model, module in cur.fetchall():
            mapping[model.replace(".", "_")] = module
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error fetching ir_model_data mapping: {e}")
    return mapping


def gather_relationships(schema, table):
    """
    Returns a list of relationship details for the given table's foreign keys
    in the given 'schema'.
    Also identifies if the table is a bridging table (many2many).
    """
    results = []

    # Detect if this table itself is a many-to-many bridge
    is_m2m_bridge = detect_many_to_many(schema, table)

    # If it's a many2many bridge, store it as a many2many relation
    if is_m2m_bridge:
        fks = schema["foreign_keys"][table]
        fk_constraints = list(fks.items())  # list of (constraint_name, definition)

        if len(fk_constraints) == 2:
            # Extract both referenced tables
            (c1, d1), (c2, d2) = fk_constraints
            ref_table1, _ = parse_fk_reference(d1)
            ref_table2, _ = parse_fk_reference(d2)

            if ref_table1 and ref_table2:
                results.append({
                    "relationship_type": "many2many",
                    "bridge_table": table,
                    "table_a": ref_table1,
                    "table_b": ref_table2
                })

    # If not a many2many bridge, gather many2one relations
    if not is_m2m_bridge and table in schema["foreign_keys"]:
        for constraint_name, definition in schema["foreign_keys"][table].items():
            ref_table, ref_col = parse_fk_reference(definition)
            local_cols = parse_fk_local_columns(definition)

            if ref_table:
                # Many2One Relation
                results.append({
                    "relationship_type": "many2one",
                    "constraint_name": constraint_name,
                    "local_columns": local_cols,
                    "referenced_table": ref_table,
                    "referenced_columns": [ref_col] if ref_col else []
                })

                # One2Many Relation (Inverse)
                results.append({
                    "relationship_type": "one2many",
                    "parent_table": ref_table,
                    "child_table": table,
                    "child_columns": local_cols
                })

    return results

def create_table_mappings_json(schema_17, schema_18, tables_to_migrate, output_dir):
    """
    Generates JSON mappings for each table, separating normal and relational field mappings.
    """
    json_path = os.path.join(output_dir, "table_mapping")
    os.makedirs(json_path, exist_ok=True)
    columns_extras_18 = schema_18.get("columns_extras", {})
    module_mapping = get_ir_model_data_mapping(DB_18)

    for table in tables_to_migrate:
        if table not in schema_17["tables"] or table not in schema_18["tables"]:
            continue

        cols_17 = {k: v for k, v in schema_17["tables"][table].items() if k != "old_enigma_id"}
        cols_18 = {k: v for k, v in schema_18["tables"][table].items() if k != "old_enigma_id"}

        shared_cols = set(cols_17.keys()) & set(cols_18.keys())
        added_cols = set(cols_18.keys()) - set(cols_17.keys())
        removed_cols = set(cols_17.keys()) - set(cols_18.keys())

        unchanged_fields = {
            col: cols_17[col]
            for col in shared_cols
            if cols_17[col] == cols_18[col]
        }
        changed_fields = {
            col: {"old_type": cols_17[col], "new_type": cols_18[col]}
            for col in shared_cols
            if cols_17[col] != cols_18[col]
        }

        added_fields = {}
        default_field_mapping = {}
        for col in added_cols:
            col_type = cols_18[col]
            extras = columns_extras_18.get(table, {}).get(col, {})
            is_nullable = (extras.get("is_nullable") == "NO")
            added_fields[col] = {"data_type": col_type, "not_null": is_nullable}
            if is_nullable:
                default_field_mapping[col] = ""

        removed_fields = {col: cols_17[col] for col in removed_cols}

        normal_field_mapping = {}
        relational_field_mapping = {}

        for col in unchanged_fields:
            normal_field_mapping[col] = col
        for col in changed_fields:
            normal_field_mapping[col] = col

        # Gather relationships from DB_18 perspective
        relationships = gather_relationships(schema_18, table)
        for rel in relationships:
            if rel["relationship_type"] == "many2many":
                relational_field_mapping[f"{rel['table_a']}_to_{rel['table_b']}"] = {
                    "relationship_type": "many2many",
                    "bridge_table": rel["bridge_table"],
                    "table_a": rel["table_a"],
                    "table_b": rel["table_b"]
                }
            elif rel["relationship_type"] == "one2many":
                relational_field_mapping[f"{rel['parent_table']}_to_{rel['child_table']}"] = {
                    "relationship_type": "one2many",
                    "parent_table": rel["parent_table"],
                    "child_table": rel["child_table"],
                    "child_columns": rel["child_columns"]
                }
            else:
                for local_col in rel["local_columns"]:
                    relational_field_mapping[local_col] = {
                        "relationship_type": rel["relationship_type"],
                        "referenced_table": rel["referenced_table"],
                        "referenced_column": rel["referenced_columns"]
                    }

        mapping_data = {
            "table": table,
            "module": module_mapping.get(table, "unknown"),
            "unchanged_fields": unchanged_fields,
            "changed_fields": changed_fields,
            "added_fields": added_fields,
            "removed_fields": removed_fields,
            "normal_field_mapping": normal_field_mapping,
            "relational_field_mapping": relational_field_mapping,
            "relationships": relationships,
            "default_field_mapping": default_field_mapping
        }

        out_file = os.path.join(json_path, f"{table}.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(mapping_data, f, indent=4)

        print(f"✔ Created mapping JSON for table: {table}")

# ------------- MAIN -------------
if __name__ == "__main__":
    # 1) Extract schema details from both DBs
    schema_17 = get_schema_details(DB_17)
    schema_18 = get_schema_details(DB_18)

    # 2) Compare and classify
    (
        schema_diffs,
        summary,
        added_tables,
        removed_tables,
        tables_with_diff,
        unchanged_tables,
        field_level_changes,
        updated_foreign_keys
    ) = compare_schemas_with_relationships(schema_17, schema_18)

    # 3) Export all results to Excel, including one2many, many2many, many2one
    save_diff_to_excel_with_relationships(
        schema_diffs,
        summary,
        added_tables,
        removed_tables,
        tables_with_diff,
        unchanged_tables,
        field_level_changes,
        updated_foreign_keys,
        schema_18
    )

    # 4) Create JSON mappings for each table with extended not-null/default info + relationships
    create_table_mappings_json(schema_17, schema_18, TABLES_TO_MIGRATE, OUTPUT_DIR)