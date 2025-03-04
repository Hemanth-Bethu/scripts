import re
import os

def replace_odoo_with_enigma7_in_file(file_path):
    # Define the patterns and replacements
    patterns_replacements = {
        r'\bodoo\b': 'enigma7',
        r'\bOdoo\b': 'Enigma7',
        r'\bODOO\b': 'ENIGMA7'
    }

    # Read the file content
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        # Perform the replacements
        for pattern, replacement in patterns_replacements.items():
            content = re.sub(pattern, replacement, content)

        # Write the modified content back to the file
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)

        print(f"Processed file: {file_path}")
    except Exception as e:
        print(f"Could not process file: {file_path}. Error: {e}")

def replace_in_directory(project_dir):
    # Walk through all directories and files in the project directory
    for root, _, files in os.walk(project_dir):
        for file in files:
            # Specify extended file extensions
            if file.endswith(('.py', '.txt', '.xml', '.js', '.csv', '.css', '.scss')):  # Extended extensions
            # if file.endswith(('.md', '.po')):  # Extended extensions
                file_path = os.path.join(root, file)
                replace_odoo_with_enigma7_in_file(file_path)

def main():
    # Specify the project directory you want to process
    project_dir = 'D:\\projects\\xaana_enigma_17\\addons\\report_py3o_fusion_server'  # Replace with the actual directory path
    replace_in_directory(project_dir)

if __name__ == "__main__":
    main()
