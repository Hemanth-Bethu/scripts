import os
import json
import psycopg2

DB_HOST = "localhost"
DB_PORT = "5432"
DB_USER = "hemanth"
DB_PASSWORD = "hemanth@1234"
DB_17 = "enigma_17_uat"
DB_18 = "enigma7_18_1"

SOURCE_DB_CONFIG = {
    "dbname": DB_17,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "host": DB_HOST,
    "port": DB_PORT,
}
DEST_DB_CONFIG = {
    "dbname": DB_18,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "host": DB_HOST,
    "port": DB_PORT,
}

MAPPING_DIR = r"D:\projects\18\comparision\table mapping"

# We'll store old->new ID maps for each table
ID_MAPS = {
    "res_company": {},
    "res_partner": {},
    "res_users": {},
    # etc. for more tables
}

# The ID of the single old company we want to migrate (we keep it the same in the new DB).
SOURCE_COMPANY_ID = 6

def get_connection(db_config):
    return psycopg2.connect(
        dbname=db_config["dbname"],
        user=db_config["user"],
        password=db_config["password"],
        host=db_config["host"],
        port=db_config["port"],
    )

def load_table_mapping(table_name):
    """
    Reads the JSON mapping file (like res_company.json) from MAPPING_DIR.
    These JSON files define unchanged_fields, changed_fields, fields_mapping, etc.
    """
    path = os.path.join(MAPPING_DIR, f"{table_name}.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Mapping file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_select_insert_statements(table_name, mapping, where_clause=None):
    """
    Creates a SELECT (old DB) / INSERT (new DB) for the columns listed in
    unchanged_fields + changed_fields (plus 'id').
    Uses the 'fields_mapping' dict to rename columns if needed.
    """
    unchanged_fields = mapping.get("unchanged_fields", {})
    changed_fields = mapping.get("changed_fields", {})
    fields_mapping = mapping.get("fields_mapping", {})

    old_colset = set(unchanged_fields.keys()) | set(changed_fields.keys())
    if "id" not in old_colset:
        old_colset.add("id")

    # We'll sort so 'id' is first in the list
    old_cols = sorted(list(old_colset), key=lambda x: (x != "id", x))
    new_cols = [fields_mapping.get(c, c) for c in old_cols]

    select_part = ", ".join(old_cols)
    select_sql = f"SELECT {select_part} FROM {table_name}"
    if where_clause:
        select_sql += f" WHERE {where_clause}"

    placeholders = ", ".join(["%s"] * len(new_cols))
    insert_part = ", ".join(new_cols)
    insert_sql = f"INSERT INTO {table_name} ({insert_part}) VALUES ({placeholders})"

    return select_sql, insert_sql, old_cols, new_cols

def convert_dicts_to_json(values_list):
    """If an item is a dict/list, do json.dumps so psycopg2 won't fail for JSONB columns."""
    import json
    for i, val in enumerate(values_list):
        if isinstance(val, (dict, list)):
            values_list[i] = json.dumps(val)
    return values_list

def delete_if_conflict(cursor, table_name, new_id):
    """
    If we want to preserve the same ID, remove any existing row in the new DB
    that might have that ID (to avoid primary key conflict).
    """
    sql = f"DELETE FROM {table_name} WHERE id=%s"
    cursor.execute(sql, (new_id,))

def reset_sequence(dest_conn, table_name, pk="id"):
    """
    Bump the table_name_id_seq so it doesn't try to reuse IDs we've inserted.
    """
    seq = f"{table_name}_{pk}_seq"
    sql_max = f"SELECT COALESCE(MAX({pk}),0) FROM {table_name}"
    with dest_conn.cursor() as cr:
        cr.execute(sql_max)
        max_id = cr.fetchone()[0]
        cr.execute(f"SELECT setval('{seq}', %s, true)", (max_id + 1,))
    dest_conn.commit()
    print(f"Sequence {seq} reset to {max_id+1}.")

def migrate_res_company(src_conn, dest_conn, old_company_id):
    """
    Migrate exactly one row from res_company with id=old_company_id,
    forcing the same ID in the new DB.
    """
    table_name = "res_company"
    mapping = load_table_mapping(table_name)

    # SELECT * FROM res_company WHERE id=6 (for example)
    select_sql, insert_sql, old_cols, new_cols = build_select_insert_statements(
        table_name,
        mapping,
        where_clause=f"id = {old_company_id}"
    )
    with src_conn.cursor() as cr_src:
        cr_src.execute(select_sql)
        row = cr_src.fetchone()
        if not row:
            print(f"res_company: no row found with id={old_company_id}")
            return None
        row = list(row)

    row = convert_dicts_to_json(row)
    idx_id = old_cols.index("id")
    old_id_val = row[idx_id]

    # We'll use the same ID for new DB
    new_id_val = old_id_val

    with dest_conn.cursor() as cr_dest:
        delete_if_conflict(cr_dest, table_name, new_id_val)
        cr_dest.execute(insert_sql, row)

    dest_conn.commit()

    # store ID map
    ID_MAPS["res_company"][old_id_val] = new_id_val
    print(f"Migrated res_company {old_id_val} -> {new_id_val}")
    return new_id_val

def migrate_res_partner(src_conn, dest_conn, old_company_id):
    """
    Migrate all res_partner rows that have company_id=old_company_id,
    forcing same partner id. Fix references to old company -> new company.
    """
    table_name = "res_partner"
    mapping = load_table_mapping(table_name)
    where_clause = f"company_id={old_company_id}"

    select_sql, insert_sql, old_cols, new_cols = build_select_insert_statements(
        table_name, mapping, where_clause=where_clause
    )

    count = 0
    with src_conn.cursor() as cr_src, dest_conn.cursor() as cr_dest:
        cr_src.execute(select_sql)
        rows = cr_src.fetchall()
        for row in rows:
            row = list(row)
            row = convert_dicts_to_json(row)

            if "company_id" in old_cols:
                i_comp = old_cols.index("company_id")
                old_comp = row[i_comp]
                # Find the new company ID from ID_MAPS
                new_comp = ID_MAPS["res_company"].get(old_comp, old_comp)
                row[i_comp] = new_comp

            idx_id = old_cols.index("id")
            old_pid = row[idx_id]
            new_pid = old_pid  # preserve same ID

            delete_if_conflict(cr_dest, table_name, new_pid)
            cr_dest.execute(insert_sql, row)
            ID_MAPS["res_partner"][old_pid] = new_pid
            count += 1

    dest_conn.commit()
    print(f"Migrated {count} res_partner rows for old company_id={old_company_id}.")

def migrate_res_users(src_conn, dest_conn, old_company_id):
    """
    Migrate all res_users with company_id=old_company_id. 
    Fix references to res_company and res_partner if needed, preserving same ID.
    """
    table_name = "res_users"
    mapping = load_table_mapping(table_name)
    where_clause = f"company_id={old_company_id}"

    select_sql, insert_sql, old_cols, new_cols = build_select_insert_statements(
        table_name, mapping, where_clause
    )
    count = 0
    with src_conn.cursor() as cr_src, dest_conn.cursor() as cr_dest:
        cr_src.execute(select_sql)
        rows = cr_src.fetchall()
        for row in rows:
            row = list(row)
            row = convert_dicts_to_json(row)

            # fix company_id
            if "company_id" in old_cols:
                i_comp = old_cols.index("company_id")
                old_comp = row[i_comp]
                new_comp = ID_MAPS["res_company"].get(old_comp, old_comp)
                row[i_comp] = new_comp

            # fix partner_id if present
            if "partner_id" in old_cols:
                i_partner = old_cols.index("partner_id")
                old_pid = row[i_partner]
                new_pid = ID_MAPS["res_partner"].get(old_pid, old_pid)
                row[i_partner] = new_pid

            idx_id = old_cols.index("id")
            old_uid = row[idx_id]
            new_uid = old_uid

            delete_if_conflict(cr_dest, table_name, new_uid)
            cr_dest.execute(insert_sql, row)
            ID_MAPS["res_users"][old_uid] = new_uid
            count += 1

    dest_conn.commit()
    print(f"Migrated {count} res_users rows for old company_id={old_company_id}.")

def reset_sequences_for_tables(dest_conn, tables):
    for tbl in tables:
        reset_sequence(dest_conn, tbl, pk="id")

def main():
    src_conn = get_connection(SOURCE_DB_CONFIG)
    dest_conn = get_connection(DEST_DB_CONFIG)
    try:
        # 1) Migrate the single res_company row with old ID=6
        new_company_id = migrate_res_company(src_conn, dest_conn, SOURCE_COMPANY_ID)
        if not new_company_id:
            print("No company migrated. Exiting.")
            return

        # 2) Migrate partners for that old company
        migrate_res_partner(src_conn, dest_conn, SOURCE_COMPANY_ID)

        # 3) Migrate users referencing that old company
        migrate_res_users(src_conn, dest_conn, SOURCE_COMPANY_ID)

        # 4) Possibly migrate more tables that reference old company_id=6
        # e.g. 'account_account', 'purchase_order', etc.
        # each function has a "WHERE company_id=6" or subselect.

        # 5) Reset sequences
        reset_sequences_for_tables(dest_conn, ["res_company", "res_partner", "res_users"])
    except Exception as ex:
        print("Migration error:", ex)
        src_conn.rollback()
        dest_conn.rollback()
    finally:
        src_conn.close()
        dest_conn.close()

if __name__ == "__main__":
    main()
