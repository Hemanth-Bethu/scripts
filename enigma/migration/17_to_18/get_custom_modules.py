import os
import pandas as pd


def get_module_list(path):
    """Return a set of module names in the given addons directory."""
    return {d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))}


def main():
    # Define project paths
    project1 = r'D:\projects\xaana_enigma_17\addons'
    project2 = r'D:\projects\18\enigma18\addons'

    # Get modules from both projects
    modules_project1 = get_module_list(project1)
    modules_project2 = get_module_list(project2)

    # Find modules in project1 but not in project2
    custom_modules = sorted(modules_project1 - modules_project2)

    # Print the result
    print("Custom modules available in xaana_enigma_17 but not in enigma18:")
    for module in custom_modules:
        print(module)

    # Save to an Excel file
    df = pd.DataFrame({'Module Name': custom_modules})
    excel_file = "custom_modules.xlsx"
    df.to_excel(excel_file, index=False)

    print(f"Module list saved to {excel_file}")


if __name__ == "__main__":
    main()
