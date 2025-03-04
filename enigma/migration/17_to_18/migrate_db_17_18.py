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

MAPPING_DIR = r"D:\projects\18\comparision\table_mapping"

# The single old company ID we want to migrate
SOURCE_COMPANY_ID = 6

# We keep old->new ID maps for each table
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
    """
    If item is a dict/list, do json.dumps.
    """
    if isinstance(vals, list):
        import json
        for i, v in enumerate(vals):
            if isinstance(v, (dict, list)):
                vals[i] = json.dumps(v)
    return vals


def delete_if_conflict(cr_dest, table_name, new_id):
    """
    Force the same 'id' in the new DB => remove a row if it conflicts.
    """
    sql = f"DELETE FROM {table_name} WHERE id=%s"
    cr_dest.execute(sql, (new_id,))


def reset_sequence(dest_conn, table_name, pk="id"):
    seq = f"{table_name}_{pk}_seq"
    sql_max = f"SELECT COALESCE(MAX({pk}),0) FROM {table_name}"
    with dest_conn.cursor() as cr:
        cr.execute(sql_max)
        max_id = cr.fetchone()[0]
        cr.execute(f"SELECT setval('{seq}', %s, true)", (max_id + 1,))
    dest_conn.commit()
    print(f"Sequence {seq} set to {max_id + 1}.")


def migrate_table(src_conn, dest_conn, table_name):
    """
    Migrate rows from old DB to new DB with the help of the JSON config,
    handling:
      - single-company filter
      - no ID changes
      - static values
      - many2one->many2many bridging
    """

    cfg = load_table_json(table_name)

    # Extract relevant sections from JSON
    normal_field_mapping = cfg.get("normal_field_mapping", {})
    static_values = cfg.get("default_field_mapping", {})
    convert_m2o_to_m2m = cfg.get("convert_m2o_to_m2m", {})
    filter_by_company = cfg.get("filter_by_company", False)

    # Collect old columns we want to select from old DB
    old_colset = set(normal_field_mapping.keys())  # old col
    for c in convert_m2o_to_m2m.keys():
        old_colset.add(c)
    # Add 'id' if not present
    if "id" not in old_colset:
        old_colset.add("id")

    # Also, if the table defines unchanged_fields, we might add them if you want
    # but typically we rely on normal_field_mapping or convert_m2o_to_m2m
    # for clarity, let's skip. Or we can do:
    # old_colset |= set(unchanged.keys())

    old_cols_sorted = sorted(list(old_colset), key=lambda x: (x != "id", x))

    # Build new columns
    # For each old col in old_cols_sorted:
    # - if in normal_field_mapping, use the new column from that mapping
    # - else if it's 'id', we keep 'id'
    # - skip columns that go to M2M bridging
    new_cols_main = []
    col_map = {}  # old_col -> new_col
    for old_col in old_cols_sorted:
        if old_col in normal_field_mapping:
            new_col = normal_field_mapping[old_col]
            new_cols_main.append(new_col)
            col_map[old_col] = new_col
        elif old_col == "id":
            new_cols_main.append("id")
            col_map["id"] = "id"
        elif old_col in convert_m2o_to_m2m:
            # We'll skip it from main table, handle in bridging
            pass
        else:
            # Possibly skip or throw an error
            pass

    # Add the static values columns if they are not in new_cols_main
    for new_col in static_values.keys():
        if new_col not in new_cols_main:
            new_cols_main.append(new_col)

    # Build SELECT
    select_part = ", ".join(old_cols_sorted)
    select_sql = f"SELECT {select_part} FROM {table_name}"

    # If we do single-company filtering
    # we assume table has 'company_id'
    # or you define a subselect approach if needed
    if filter_by_company:
        # basic approach: "WHERE company_id = 6"
        # you might have columns named differently, adapt as needed
        select_sql += f" WHERE company_id = {SOURCE_COMPANY_ID}"

    # placeholders for the main insert
    placeholders = ", ".join(["%s"] * len(new_cols_main))
    insert_part = ", ".join(new_cols_main)
    insert_sql = f"INSERT INTO {table_name} ({insert_part}) VALUES ({placeholders})"

    # Query old DB
    with src_conn.cursor() as cr_src:
        cr_src.execute(select_sql)
        rows = cr_src.fetchall()

    # Make sure we have an ID map
    if table_name not in ID_MAPS:
        ID_MAPS[table_name] = {}

    inserted_count = 0

    with dest_conn.cursor() as cr_dest:
        for row in rows:
            row = list(row)
            row = convert_dicts_to_json(row)

            # We'll build the final "values_main" for the main table
            values_main = []

            # Find old_id
            idx_id = old_cols_sorted.index("id")
            old_id_val = row[idx_id]

            # For each new col in new_cols_main, pick a value
            for new_col in new_cols_main:
                if new_col in static_values:
                    # If the user wants a static value
                    val = static_values[new_col]
                else:
                    # find which old_col gave us this new_col
                    # i.e. col_map
                    old_col = None
                    for oc, nc in col_map.items():
                        if nc == new_col:
                            old_col = oc
                            break
                    if old_col is None:
                        # if we didn't find a matching old col, set None or skip
                        val = None
                    else:
                        # find index of old_col
                        i_old = old_cols_sorted.index(old_col)
                        val = row[i_old]

                values_main.append(val)

            # We preserve the same ID => remove conflict
            new_id_val = old_id_val
            delete_if_conflict(cr_dest, table_name, new_id_val)
            cr_dest.execute(insert_sql, values_main)

            # store ID map
            ID_MAPS[table_name][old_id_val] = new_id_val

            # M2O -> M2M bridging
            # e.g. "convert_m2o_to_m2m": {
            #   "old_many2one_col": {
            #     "relation_table": "my_table_other_rel",
            #     "relation_local_key": "my_table_id",
            #     "relation_target_key": "other_id",
            #     "ref_table": "other_table"
            #   }
            # }
            for old_col, rel_info in convert_m2o_to_m2m.items():
                # find old_col index
                i_m2o = old_cols_sorted.index(old_col)
                old_ref_id = row[i_m2o]
                if old_ref_id is None:
                    continue
                relation_table = rel_info["relation_table"]
                local_key = rel_info["relation_local_key"]
                target_key = rel_info["relation_target_key"]
                ref_table = rel_info.get("ref_table")  # e.g. "other_table"

                # find new_ref_id from ID_MAPS if we have it
                if ref_table and old_ref_id in ID_MAPS.get(ref_table, {}):
                    new_ref_id = ID_MAPS[ref_table][old_ref_id]
                else:
                    new_ref_id = old_ref_id  # fallback or None

                # Insert bridging row
                rel_sql = f"INSERT INTO {relation_table} ({local_key}, {target_key}) VALUES (%s, %s)"
                cr_dest.execute(rel_sql, (new_id_val, new_ref_id))

            inserted_count += 1

    dest_conn.commit()
    print(f"Migrated {inserted_count} rows into {table_name} with single-company filtering={filter_by_company}.")


def reset_sequence_for_tables(dest_conn, table_list):
    for tbl in table_list:
        reset_sequence(dest_conn, tbl, pk="id")


def main():
    src_conn = get_connection(SOURCE_DB_CONFIG)
    dest_conn = get_connection(DEST_DB_CONFIG)
    try:
        # Example usage:
        # Migrate "res_company" for single-company approach
        # We'll define "filter_by_company": false in the JSON for "res_company"
        # because we only want that row with id=6, so let's do that in the JSON or rely on the key
        migrate_table(src_conn, dest_conn, "res_company")

        # Then "res_partner" might have "filter_by_company": true in JSON
        # So it automatically does "WHERE company_id=6"
        migrate_table(src_conn, dest_conn, "res_partner")

        # Then "res_users", same approach
        migrate_table(src_conn, dest_conn, "res_users")

        # Potentially "account_account" which has convert_m2o_to_m2m or static_values
        # migrate_table(src_conn, dest_conn, "account_account")

        # etc...

        # Reset sequences for each
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
