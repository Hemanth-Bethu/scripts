import os
import pandas as pd
from lxml import etree
from tqdm import tqdm
from multiprocessing import Pool, cpu_count

# Configurable paths
INPUT_FOLDERS = [
    r"C:\Users\Hemanth\Downloads\ABN_supplier_part_1",
    r"C:\Users\Hemanth\Downloads\ABN_supplier_part_2"
]
OUTPUT_FOLDER = r"C:\Users\Hemanth\Downloads\ABN_excel_output_2"
RECORD_TAG = "ABR"

def extract_all_fields(elem):
    """Efficient flat extractor — avoids XPath lookups repeatedly"""
    def text(e, tag): return e.find(tag).text if e is not None and e.find(tag) is not None else None
    def attr(e, tag, a): return e.find(tag).get(a) if e is not None and e.find(tag) is not None else None
    def all_texts(e, tag): return "; ".join([n.text for n in e.findall(tag) if n.text]) or None

    abn = elem.find("ABN")
    entity_type = elem.find("EntityType")
    main_name = elem.find("MainEntity/NonIndividualName")
    address = elem.find("MainEntity/BusinessAddress/AddressDetails")
    legal_name = elem.find("LegalEntity/IndividualName")
    asic = elem.find("ASICNumber")
    gst = elem.find("GST")
    dgr = elem.find("DGR")

    return {
        "ABN": abn.text if abn is not None else None,
        "ABN_Status": abn.get("status") if abn is not None else None,
        "ABN_From": abn.get("ABNStatusFromDate") if abn is not None else None,
        "ABR_Last_Updated": elem.get("recordLastUpdatedDate"),

        "Entity_Type_Code": text(entity_type, "EntityTypeInd"),
        "Entity_Type_Label": text(entity_type, "EntityTypeText"),

        "Legal_Name": text(main_name, "NonIndividualNameText"),
        "Legal_Name_Type": main_name.get("type") if main_name is not None else None,

        "State": text(address, "State"),
        "Postcode": text(address, "Postcode"),

        "Given_Name": text(legal_name, "GivenName"),
        "Family_Name": text(legal_name, "FamilyName"),
        "Name_Title": text(legal_name, "NameTitle"),

        "ASIC_Number": asic.text if asic is not None else None,
        "ASIC_Number_Type": asic.get("ASICNumberType") if asic is not None else None,

        "GST_Status": gst.get("status") if gst is not None else None,
        "GST_From": gst.get("GSTStatusFromDate") if gst is not None else None,

        "DGR_From": dgr.get("DGRStatusFromDate") if dgr is not None else None,

        "Trading_Names": all_texts(elem, "OtherEntity/NonIndividualName/NonIndividualNameText"),
        "Business_Names": all_texts(elem, "BusinessName/OrganisationName"),
    }

def parse_abn_file(xml_file):
    context = etree.iterparse(xml_file, events=("end",), tag=RECORD_TAG, recover=True)
    records = []
    for _, elem in context:
        records.append(extract_all_fields(elem))
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]
    return pd.DataFrame(records)

def process_file(args):
    full_path, folder_tag, output_folder = args
    file = os.path.basename(full_path)
    out_name = f"{folder_tag}__{os.path.splitext(file)[0]}.csv"
    out_path = os.path.join(output_folder, out_name)

    try:
        df = parse_abn_file(full_path)
        df.to_csv(out_path, index=False)
        return f"✅ {file} → {len(df)} rows → {out_path}"
    except Exception as e:
        return f"❌ Error processing {file}: {e}"

def process_folder_parallel(input_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    folder_tag = os.path.basename(input_folder)
    files = [
        (os.path.join(input_folder, f), folder_tag, output_folder)
        for f in os.listdir(input_folder)
        if f.lower().endswith(".xml")
    ]

    with Pool(cpu_count()) as pool:
        for result in tqdm(pool.imap_unordered(process_file, files), total=len(files), desc=f"📂 {folder_tag}"):
            print(result)

def main():
    print("🚀 Starting optimized ABN XML → CSV extraction...\n")
    for folder in INPUT_FOLDERS:
        process_folder_parallel(folder, OUTPUT_FOLDER)
    print(f"\n✅ All done. Output saved to: {OUTPUT_FOLDER}")

if __name__ == "__main__":
    main()
