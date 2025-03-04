import os
import pandas as pd


def get_directory_structure(root_dir):
    """
    Walks through a directory and captures the relative paths of all files and folders,
    excluding specified folders such as .venv, .git, .idea, .vscode, __pycache__, i18n, and tests.
    """
    files = set()
    folders = set()
    main_modules = set()
    exclude_dirs = {'.venv', '.git', '.idea', '.vscode', '__pycache__', 'i18n', 'tests'}  # Folders to ignore

    for root, dirs, file_names in os.walk(root_dir):
        # Modify dirs in-place to exclude specified directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        # Check if the current directory is a main module (immediately after addons)
        for dir_name in dirs:
            relative_path = os.path.relpath(os.path.join(root, dir_name), root_dir)
            if os.path.basename(os.path.dirname(relative_path)) == 'addons':
                main_modules.add(relative_path)
            folders.add(relative_path)

        for file_name in file_names:
            relative_path = os.path.relpath(os.path.join(root, file_name), root_dir)
            files.add(relative_path)

    return files, folders, main_modules


def filter_missing_folders_only(missing_files, missing_folders):
    """
    Filters out files from the missing_files set if they belong to a missing folder in missing_folders
    or are located within an i18n or tests folder.
    """
    filtered_files = {file for file in missing_files
                      if not any(file.startswith(folder) for folder in missing_folders)
                      and 'i18n' not in file
                      and 'tests' not in file}
    return filtered_files


def group_files_by_module(missing_files):
    """
    Groups missing files by their respective module under the addons directory.
    """
    module_files = {}
    for file in missing_files:
        if 'addons' in file:
            module = file.split(os.sep)[1]  # Module is the first folder after 'addons'
            if module not in module_files:
                module_files[module] = []
            module_files[module].append(file)
    return module_files


def compare_directories(dir1, dir2):
    """
    Compares two directory structures and identifies files/folders missing in each.
    """
    files1, folders1, main_modules1 = get_directory_structure(dir1)
    files2, folders2, main_modules2 = get_directory_structure(dir2)

    # Calculate missing files and folders
    missing_files_in_dir1 = files2 - files1
    missing_files_in_dir2 = files1 - files2
    missing_folders_in_dir1 = folders2 - folders1
    missing_folders_in_dir2 = folders1 - folders2
    missing_main_modules_in_dir1 = main_modules2 - main_modules1
    missing_main_modules_in_dir2 = main_modules1 - main_modules2

    # Filter out files that are inside entirely missing folders or i18n/tests folders
    missing_files_in_dir1 = filter_missing_folders_only(missing_files_in_dir1, missing_folders_in_dir1)
    missing_files_in_dir2 = filter_missing_folders_only(missing_files_in_dir2, missing_folders_in_dir2)

    # Group missing files by module
    missing_files_in_dir1_by_module = group_files_by_module(missing_files_in_dir1)
    missing_files_in_dir2_by_module = group_files_by_module(missing_files_in_dir2)

    return (missing_files_in_dir1_by_module, missing_files_in_dir2_by_module,
            missing_folders_in_dir1, missing_folders_in_dir2,
            missing_main_modules_in_dir1, missing_main_modules_in_dir2)


def save_to_excel(missing_files_in_dir1_by_module, missing_files_in_dir2_by_module,
                  missing_folders_in_dir1, missing_folders_in_dir2,
                  missing_main_modules_in_dir1, missing_main_modules_in_dir2,
                  output_file):
    """
    Saves missing files/folders data into an Excel file with a detailed structure.
    """
    # Flatten missing files by module into DataFrames
    df_missing_files_in_dir1 = pd.DataFrame([
        {'Module': module, 'Missing_File': file, 'Project': 'Missing in Project 1'}
        for module, files in missing_files_in_dir1_by_module.items() for file in files
    ])
    df_missing_files_in_dir2 = pd.DataFrame([
        {'Module': module, 'Missing_File': file, 'Project': 'Missing in Project 2'}
        for module, files in missing_files_in_dir2_by_module.items() for file in files
    ])

    df_missing_folders_in_dir1 = pd.DataFrame(
        {'Missing_Path': sorted(missing_folders_in_dir1), 'Project': 'Missing in Project 1'}
    )
    df_missing_folders_in_dir2 = pd.DataFrame(
        {'Missing_Path': sorted(missing_folders_in_dir2), 'Project': 'Missing in Project 2'}
    )
    df_missing_main_modules_in_dir1 = pd.DataFrame(
        {'Missing_Main_Module': sorted(missing_main_modules_in_dir1), 'Project': 'Missing in Project 1'}
    )
    df_missing_main_modules_in_dir2 = pd.DataFrame(
        {'Missing_Main_Module': sorted(missing_main_modules_in_dir2), 'Project': 'Missing in Project 2'}
    )

    # Create Excel writer
    with pd.ExcelWriter(output_file) as writer:
        # Write each DataFrame to separate sheets with shortened names
        df_missing_files_in_dir1.to_excel(writer, sheet_name='Files Missing by Module P1', index=False)
        df_missing_files_in_dir2.to_excel(writer, sheet_name='Files Missing by Module P2', index=False)
        df_missing_folders_in_dir1.to_excel(writer, sheet_name='Folders Missing in P1', index=False)
        df_missing_folders_in_dir2.to_excel(writer, sheet_name='Folders Missing in P2', index=False)
        df_missing_main_modules_in_dir1.to_excel(writer, sheet_name='Main Mods Missing in P1', index=False)
        df_missing_main_modules_in_dir2.to_excel(writer, sheet_name='Main Mods Missing in P2', index=False)

    print(f"Comparison saved to {output_file}")


def main():
    # Specify the paths of the two directories you want to compare
    project_dir1 = 'D:\\projects\\enigma18'  # Replace with actual path
    project_dir2 = 'D:\\projects\\xaana_enigma_17'  # Replace with actual path
    output_file = 'project_comparison.xlsx'  # Specify the output Excel file

    # Perform comparison
    (missing_files_in_dir1_by_module, missing_files_in_dir2_by_module,
     missing_folders_in_dir1, missing_folders_in_dir2,
     missing_main_modules_in_dir1, missing_main_modules_in_dir2) = compare_directories(project_dir1, project_dir2)

    # Save the results to an Excel file
    save_to_excel(missing_files_in_dir1_by_module, missing_files_in_dir2_by_module,
                  missing_folders_in_dir1, missing_folders_in_dir2,
                  missing_main_modules_in_dir1, missing_main_modules_in_dir2,
                  output_file)


if __name__ == "__main__":
    main()
