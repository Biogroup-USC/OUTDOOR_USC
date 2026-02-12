import bw2data as bd
import bw2io as bi
import multiprocessing


def import_ecoinvent(projectName, version="3.9.1", system_model="consequential"):

    print("The following projects are available in Brightway:")
    print(list(bd.projects))

    # Create project if needed
    if projectName not in bd.projects:
        bd.projects.create_project(projectName)

    bd.projects.set_current(projectName)

    # Construct expected database names
    ei_name = f"ecoinvent-{version}-{system_model}"
    bios_name = f"ecoinvent-{version}-biosphere"

    print("\nDatabases currently in this project:")
    print(list(bd.databases))

    # STOP if database already exists
    if ei_name in bd.databases:
        print(f"\nDatabase '{ei_name}' already exists in project '{projectName}'.")
        print("Skipping import.")
        # print in green
        print("\033[92m" + "Brightway already installed" + "\033[0m")
        print(bd.projects.dir)
        print(bd.__version__)

        return

    else:
        try:
            # get input from the user, print the message in bold purple
            print("")
            print("\033[1;35m" + "Please enter your credentials to access the Ecoinvent database" + "\033[0m")
            username = input('Username: ')
            password = input('Password: ')

            # Add use_mp=False to avoid multiprocessing issues
            bi.import_ecoinvent_release(
                version=version,
                system_model=system_model,
                username=username,
                password=password,
            )

            # This prints the directory where the current project is stored
            print(bd.projects.dir)
            print(bd.__version__)

        except Exception as e:
            print("The following error occurred:", e)
            return


def check_project_database(projectName):
    # Save current project to restore it later
    current = bd.projects.current

    if projectName not in bd.projects:
        print(f"Project '{projectName}' does not exist")
        return False

    # Switch to the project you want to check
    bd.projects.set_current(projectName)

    # Check if databases exist
    if not bd.databases:
        print(f"Project '{projectName}' has no databases")
        bd.projects.set_current(current)  # Restore original project
        return False

    # Check if databases have data
    valid_databases = []
    for dbName in bd.databases:
        db = bd.Database(dbName)
        size = len(db)
        if size > 0:
            valid_databases.append((dbName, size))

    # Restore original project
    bd.projects.set_current(current)

    if valid_databases:
        print(f"Project '{projectName}' has functional databases:")
        for dbName, size in valid_databases:
            print(f"  - {dbName}: {size} datasets")
        return True
    else:
        print(f"Project '{projectName}' has empty databases")
        return False

# This is the crucial part that prevents multiprocessing issues on Windows
if __name__ == "__main__":
    # Add freeze_support for Windows
    multiprocessing.freeze_support()
    import_ecoinvent(projectName='outdoor', version="3.11", system_model="cutoff")

    # Check the project database
    check_project_database(projectName='outdoor')


