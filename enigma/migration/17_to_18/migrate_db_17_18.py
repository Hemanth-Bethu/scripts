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

MAPPING_DIR = r"D:\\projects\\18\\comparision\\table mapping"
SOURCE_COMPANY_ID = 6

ID_MAPS = {}

def get_connection(db_config):
    return psycopg2.connect(
        dbname=db_config["dbname"],
        user=db_config["user"],
        password=db_config["password"],
        host=db_config["host"],
        port=db_config["port"],
    )

def load_table_json(table_name):
    path = os.path.join(MAPPING_DIR, f"{table_name}.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Mapping file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def convert_dicts_to_json(vals):
    if isinstance(vals, list):
        for i, v in enumerate(vals):
            if isinstance(v, (dict, list)):
                vals[i] = json.dumps(v)
    return vals

def delete_if_conflict(cr_dest, table_name, new_id):
    sql = f"DELETE FROM {table_name} WHERE id=%s"
    cr_dest.execute(sql, (new_id,))

def reset_sequence(dest_conn, table_name, pk="id"):
    seq = f"{table_name}_{pk}_seq"
    sql_max = f"SELECT COALESCE(MAX({pk}),0) FROM {table_name}"
    with dest_conn.cursor() as cr:
        cr.execute(sql_max)
        max_id = cr.fetchone()[0]
        cr.execute(f"SELECT setval('{seq}', %s, true)", (max_id+1,))
    dest_conn.commit()
    print(f"Sequence {seq} set to {max_id+1}.")

def migrate_table(src_conn, dest_conn, table_name):
    cfg = load_table_json(table_name)
    normal_field_mapping = cfg.get("normal_field_mapping", {})
    m2o_to_m2m_mappings = cfg.get("m2o_to_m2m_mappings", {})
    default_field_mapping = cfg.get("default_field_mapping", {})
    filter_by_company = cfg.get("company_id_mapping", {})

    old_colset = set(normal_field_mapping.keys()) | set(m2o_to_m2m_mappings.keys())
    if "id" not in old_colset:
        old_colset.add("id")
    old_cols_sorted = sorted(list(old_colset))

    new_cols_main = list(normal_field_mapping.values())
    select_part = ", ".join(old_cols_sorted)
    select_sql = f"SELECT {select_part} FROM {table_name}"

    if "company_id" in filter_by_company:
        select_sql += f" WHERE company_id = {SOURCE_COMPANY_ID}"

    placeholders = ", ".join(["%s"] * len(new_cols_main))
    insert_part = ", ".join(new_cols_main)
    insert_sql = f"INSERT INTO {table_name} ({insert_part}) VALUES ({placeholders})"

    with src_conn.cursor() as cr_src:
        cr_src.execute(select_sql)
        rows = cr_src.fetchall()

    if table_name not in ID_MAPS:
        ID_MAPS[table_name] = {}

    inserted_count = 0
    with dest_conn.cursor() as cr_dest:
        for row in rows:
            row = convert_dicts_to_json(list(row))
            values_main = []
            old_id_val = row[old_cols_sorted.index("id")]

            for old_col, new_col in normal_field_mapping.items():
                i_old = old_cols_sorted.index(old_col)
                values_main.append(row[i_old])

            for col, default_value in default_field_mapping.items():
                if col not in new_cols_main:
                    new_cols_main.append(col)
                    values_main.append(default_value)

            new_id_val = old_id_val
            delete_if_conflict(cr_dest, table_name, new_id_val)
            cr_dest.execute(insert_sql, values_main)
            ID_MAPS[table_name][old_id_val] = new_id_val

            # Process Many2One → Many2Many conversion
            for old_col, rel_info in m2o_to_m2m_mappings.items():
                i_m2o = old_cols_sorted.index(old_col)
                old_ref_id = row[i_m2o]
                if old_ref_id is None:
                    continue

                relation_table = rel_info["relation_table"]
                local_key = rel_info["relation_local_key"]
                target_key = rel_info["relation_target_key"]
                ref_table = rel_info.get("ref_table")

                # Find new_ref_id from ID_MAPS if mapped
                if ref_table and old_ref_id in ID_MAPS.get(ref_table, {}):
                    new_ref_id = ID_MAPS[ref_table][old_ref_id]
                else:
                    new_ref_id = old_ref_id

                # Insert into Many2Many relation table
                rel_sql = f"INSERT INTO {relation_table} ({local_key}, {target_key}) VALUES (%s, %s)"
                cr_dest.execute(rel_sql, (new_id_val, new_ref_id))

            inserted_count += 1

    dest_conn.commit()
    print(f"Migrated {inserted_count} rows into {table_name}.")

def reset_sequence_for_tables(dest_conn, table_list):
    for tbl in table_list:
        reset_sequence(dest_conn, tbl, pk="id")

def main():
    src_conn = get_connection(SOURCE_DB_CONFIG)
    dest_conn = get_connection(DEST_DB_CONFIG)
    try:
        migrate_table(src_conn, dest_conn, "res_company")
        migrate_table(src_conn, dest_conn, "res_partner")
        migrate_table(src_conn, dest_conn, "res_users")
        reset_sequence_for_tables(dest_conn, ["res_company", "res_partner", "res_users"])
    except Exception as ex:
        print("Migration error:", ex)
        src_conn.rollback()
        dest_conn.rollback()
    finally:
        src_conn.close()
        dest_conn.close()

if __name__ == "__main__":
    main()