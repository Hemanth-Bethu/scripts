import psycopg2

# ------------------------------------------------------------------------------
# Database credentials -- update as needed
# ------------------------------------------------------------------------------
DB_HOST = "localhost"
DB_PORT = "5432"
DB_USER = "hemanth"
DB_PASSWORD = "hemanth@1234"
DB_17 = "enigma_17_uat"
DB_18 = "enigma18"


def get_installed_modules(db_name):
    """
    Connect to the given db_name, query ir_module_module to find
    modules in ('installed', 'to install', 'to upgrade').
    Returns a set of module names.
    """
    query = """
        SELECT name
        FROM ir_module_module
        WHERE state in ('installed', 'to install', 'to upgrade')
    """
    modules = set()
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        )
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            for (mod_name,) in rows:
                modules.add(mod_name)
    except Exception as e:
        print(f"❌ Error fetching modules from {db_name}: {e}")
    finally:
        if conn:
            conn.close()

    return modules


if __name__ == "__main__":
    # 1) Fetch modules from both v17 and v18
    v17_modules = get_installed_modules(DB_17)
    v18_modules = get_installed_modules(DB_18)

    # 2) Compare: which modules are in v17 but NOT in v18
    missing_in_v18 = sorted(list(v17_modules - v18_modules))

    # 3) Print results
    print("==============================================")
    print(f"Modules installed in {DB_17} but NOT in {DB_18}: {len(missing_in_v18)}")
    for mod_name in missing_in_v18:
        print(f"  - {mod_name}")
    print("==============================================")

    # Optionally, you could also save them to a file or Excel:
    # with open("modules_missing_in_v18.txt", "w", encoding="utf-8") as f:
    #     for m in missing_in_v18:
    #         f.write(m + "\n")
