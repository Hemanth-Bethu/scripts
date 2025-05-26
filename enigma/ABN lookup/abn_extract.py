import xml.etree.ElementTree as ET
import zipfile
import os
import csv

def extract_abn_data(zip_file_path):
    extract_dir = 'abn_data'
    os.makedirs(extract_dir, exist_ok=True)

    # Extract ZIP contents
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    output_file = 'abn_output.csv'
    with open(output_file, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['ABN', 'Entity Type', 'Legal Name', 'GST Status', 'GST Registration Date'])

        # Process each XML file
        for filename in os.listdir(extract_dir):
            if filename.endswith('.xml'):
                file_path = os.path.join(extract_dir, filename)
                try:
                    tree = ET.parse(file_path)
                    root = tree.getroot()

                    for record in root.findall('.//ABR'):
                        abn = record.findtext('ABN') or ''
                        entity_type = record.findtext('EntityType/EntityTypeText') or ''
                        legal_name = record.findtext('MainEntity/LegalName') or ''
                        gst_status = record.findtext('GST/GSTStatus') or ''
                        gst_registration_date = record.findtext('GST/GSTRegistrationDate') or ''

                        writer.writerow([abn, entity_type, legal_name, gst_status, gst_registration_date])
                except ET.ParseError as e:
                    print(f"Error parsing {filename}: {e}")

    print(f"Extraction complete. Output saved to: {output_file}")


if __name__ == '__main__':
    zip_path = 'public_split_1_10.zip'  # Ensure this file exists in the same directory
    extract_abn_data(zip_path)
