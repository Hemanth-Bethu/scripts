import os
import json
import psycopg2

DB_HOST = "localhost"
DB_PORT = "5432"
DB_USER = "hemanth"
DB_PASSWORD = "hemanth@1234"
DB_17 = "enigma_17_uat"
DB_18 = "enigma7_18_1"

SOURCE_DB_CONFIG = {"dbname": DB_17, "user": DB_USER, "password": DB_PASSWORD, "host": DB_HOST, "port": DB_PORT}
DEST_DB_CONFIG = {"dbname": DB_18, "user": DB_USER, "password": DB_PASSWORD, "host": DB_HOST, "port": DB_PORT}

MAPPING_DIR = r"D:\\projects\\18\\comparision\\table mapping"
SOURCE_COMPANY_ID = 6

ID_MAPS = {}


def get_connection(db_config):
    """Establishes a connection to the database."""
    return psycopg2.connect(**db_config)


def load_table_json(table_name):
    """Loads JSON configuration for a given table."""
    path = os.path.join(MAPPING_DIR, f"{table_name}.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Mapping file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def reset_sequence(dest_conn, table_name, pk="id"):
    """Resets the sequence for a table."""
    seq = f"{table_name}_{pk}_seq"
    with dest_conn.cursor() as cr:
        cr.execute(f"SELECT COALESCE(MAX({pk}),0) FROM {table_name}")
        max_id = cr.fetchone()[0]
        cr.execute(f"SELECT setval('{seq}', %s, true)", (max_id + 1,))
    dest_conn.commit()
    print(f"Sequence {seq} set to {max_id + 1}.")


def delete_if_conflict(cr_dest, table_name, new_id):
    """Deletes existing records to avoid ID conflicts before inserting new ones."""
    cr_dest.execute(f"DELETE FROM {table_name} WHERE id=%s", (new_id,))


def convert_dicts_to_json(vals):
    """Converts dictionaries and lists to JSON strings for insertion into the database."""
    return [json.dumps(v) if isinstance(v, (dict, list)) else v for v in vals]


def migrate_straight_fields(cr_dest, table_name, rows, normal_field_mapping, default_field_mapping, old_cols_sorted):
    """Handles direct column mappings and default values."""
    new_cols = list(normal_field_mapping.values()) + list(default_field_mapping.keys())
    placeholders = ", ".join(["%s"] * len(new_cols))
    insert_sql = f"INSERT INTO {table_name} ({', '.join(new_cols)}) VALUES ({placeholders})"

    for row in rows:
        row = convert_dicts_to_json(list(row))
        values = [row[old_cols_sorted.index(old_col)] for old_col in normal_field_mapping.keys()]
        values += list(default_field_mapping.values())  # Add default values

        new_id = row[old_cols_sorted.index("id")]
        delete_if_conflict(cr_dest, table_name, new_id)  # Avoid conflicts
        cr_dest.execute(insert_sql, values)
        ID_MAPS.setdefault(table_name, {})[new_id] = new_id  # Store mapping


def migrate_m2o_to_m2m(cr_dest, table_name, rows, m2o_to_m2m_mappings, old_cols_sorted):
    """Handles Many2One to Many2Many field conversions."""
    for row in rows:
        row = list(row)
        new_id = row[old_cols_sorted.index("id")]

        for old_col, rel_info in m2o_to_m2m_mappings.items():
            old_ref_id = row[old_cols_sorted.index(old_col)]
            if old_ref_id is None:
                continue

            # Resolve new reference ID
            ref_table = rel_info.get("ref_table")
            new_ref_id = ID_MAPS.get(ref_table, {}).get(old_ref_id, old_ref_id)

            # Insert into Many2Many relation table
            rel_sql = f"INSERT INTO {rel_info['relation_table']} ({rel_info['relation_local_key']}, {rel_info['relation_target_key']}) VALUES (%s, %s)"
            cr_dest.execute(rel_sql, (new_id, new_ref_id))


def migrate_table(src_conn, dest_conn, table_name):
    """Handles full table migration including normal fields and Many2One to Many2Many transformations."""
    cfg = load_table_json(table_name)

    normal_field_mapping = cfg.get("normal_field_mapping", {})
    m2o_to_m2m_mappings = cfg.get("m2o_to_m2m_mappings", {})
    default_field_mapping = cfg.get("default_field_mapping", {})
    filter_by_company = cfg.get("company_id_mapping", {})

    old_colset = set(normal_field_mapping.keys()) | set(m2o_to_m2m_mappings.keys()) | {"id"}
    old_cols_sorted = sorted(list(old_colset))

    select_sql = f"SELECT {', '.join(old_cols_sorted)} FROM {table_name}"
    if "company_id" in filter_by_company:
        select_sql += f" WHERE company_id = {SOURCE_COMPANY_ID}"

    with src_conn.cursor() as cr_src, dest_conn.cursor() as cr_dest:
        cr_src.execute(select_sql)
        rows = cr_src.fetchall()

        migrate_straight_fields(cr_dest, table_name, rows, normal_field_mapping, default_field_mapping, old_cols_sorted)
        migrate_m2o_to_m2m(cr_dest, table_name, rows, m2o_to_m2m_mappings, old_cols_sorted)

    dest_conn.commit()
    print(f"Migrated {len(rows)} rows into {table_name}.")


def reset_sequence_for_tables(dest_conn, table_list):
    """Resets sequences for all specified tables."""
    for tbl in table_list:
        reset_sequence(dest_conn, tbl)


def main():
    """Main function to initiate migration for all tables."""
    src_conn = get_connection(SOURCE_DB_CONFIG)
    dest_conn = get_connection(DEST_DB_CONFIG)
    try:
        tables_to_migrate = ["res_company", "res_partner", "res_users"]
        for table in tables_to_migrate:
            migrate_table(src_conn, dest_conn, table)

        reset_sequence_for_tables(dest_conn, tables_to_migrate)
    except Exception as ex:
        print("Migration error:", ex)
        src_conn.rollback()
        dest_conn.rollback()
    finally:
        src_conn.close()
        dest_conn.close()


if __name__ == "__main__":
    main()
