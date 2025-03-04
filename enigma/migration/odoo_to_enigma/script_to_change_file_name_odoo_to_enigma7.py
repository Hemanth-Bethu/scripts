import os

def rename_files_and_directories_in_directory(project_dir):
    # Walk through all directories and files in the project directory
    for root, dirs, files in os.walk(project_dir, topdown=False):  # `topdown=False` ensures deeper files/folders are processed first
        # Rename files
        for file in files:
            if 'odoo' in file:
                new_name = file.replace('odoo', 'enigma7')
            elif 'Odoo' in file:
                new_name = file.replace('Odoo', 'Enigma7')
            elif 'ODOO' in file:
                new_name = file.replace('ODOO', 'ENIGMA')
            else:
                continue

            # Define full paths
            old_file_path = os.path.join(root, file)
            new_file_path = os.path.join(root, new_name)

            # Rename the file
            try:
                os.rename(old_file_path, new_file_path)
                print(f"Renamed file: {old_file_path} -> {new_file_path}")
            except Exception as e:
                print(f"Failed to rename file {old_file_path}: {e}")

        # Rename directories
        for dir_name in dirs:
            if 'odoo' in dir_name:
                new_name = dir_name.replace('odoo', 'enigma7')
            elif 'Odoo' in dir_name:
                new_name = dir_name.replace('Odoo', 'Enigma7')
            elif 'ODOO' in dir_name:
                new_name = dir_name.replace('ODOO', 'ENIGMA')
            else:
                continue

            # Define full paths
            old_dir_path = os.path.join(root, dir_name)
            new_dir_path = os.path.join(root, new_name)

            # Rename the directory
            try:
                os.rename(old_dir_path, new_dir_path)
                print(f"Renamed directory: {old_dir_path} -> {new_dir_path}")
            except Exception as e:
                print(f"Failed to rename directory {old_dir_path}: {e}")

def main():
    # Specify the project directory you want to process
    project_dir = 'C:\\Users\\bethu\\Downloads\\spiffy_theme_backend'  # Replace with the actual directory path
    rename_files_and_directories_in_directory(project_dir)

if __name__ == "__main__":
    main()
