import requests
import time
import os
import csv

BASE_URL = "https://directory.peppol.eu/search/1.0/json/menuitem-search"
QUERY = "0151:"
PAGE_SIZE = 20
OUTPUT_CSV = "peppol_0151_abns_incremental.csv"

HEADERS = [
    "ABN", "Entity Name", "Language", "Country", "Registered On",
    "Geo Info", "Identifiers", "Document Types"
]
START_PAGE = 238
def fetch_page(page):
    params = {
        "q": QUERY,
        "start": page * PAGE_SIZE
    }
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    return response.json()

def extract_text_list(doc_types):
    return "; ".join([doc["value"] for doc in doc_types]) if doc_types else ""

def extract_identifiers(identifiers):
    return "; ".join([f'{i["scheme"]}:{i["value"]}' for i in identifiers]) if identifiers else ""

def ensure_csv():
    file_exists = os.path.exists(OUTPUT_CSV)
    f = open(OUTPUT_CSV, mode='a', newline='', encoding='utf-8')
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(HEADERS)
    return f, writer

def append_data(writer, row_data):
    writer.writerow(row_data)

def main():
    first_page = fetch_page(0)
    total = first_page["total-result-count"]
    pages = (total // PAGE_SIZE) + 1
    print(f"Total ABNs with 0151 scheme: {total}, Pages: {pages}")

    for page in range(START_PAGE, pages):
        try:
            data = fetch_page(page)
            f, writer = ensure_csv()
            for match in data.get("matches", []):
                participant_id = match["participantID"]["value"]
                if not participant_id.startswith("0151:"):
                    continue

                abn = participant_id.split(":")[1]
                entity = match["entities"][0]
                name = entity.get("name", [{}])[0].get("name", "")
                language = entity.get("name", [{}])[0].get("language", "")
                country = entity.get("countryCode", "")
                reg_date = entity.get("regDate", "")
                geo_info = entity.get("geoInfo", "")
                identifiers = extract_identifiers(entity.get("identifiers", []))
                doc_types = extract_text_list(match.get("docTypes", []))

                append_data(writer, [
                    abn, name, language, country, reg_date,
                    geo_info, identifiers, doc_types
                ])

            f.close()
            print(f"✅ Page {page + 1}/{pages} saved to CSV")
        except Exception as e:
            print(f"❌ Error on page {page}: {e}")
            break

    print(f"\n🎉 Completed. CSV file is saved as '{OUTPUT_CSV}'.")

if __name__ == "__main__":
    main()
