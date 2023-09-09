import argparse
import os
import subprocess
import json
import shutil
import getpass
import uuid
import sys

def is_sudo():
    return os.geteuid() == 0

def get_temp_dir(is_sudo):
    if is_sudo:
        return "/usr/share/aapp-cli/temp"
    else:
        home_dir = os.path.expanduser("~")
        return os.path.join(home_dir, ".aapp-cli", "tmp")

def get_app_bundle_dir(is_sudo):
    if is_sudo:
        return "/usr/apps"
    else:
        home_dir = os.path.expanduser("~")
        return os.path.join(home_dir, ".apps")

def find_main_file(root_dir):
    # Recursively search for a Python file containing the main() function
    for root, _, files in os.walk(root_dir):
        for filename in files:
            if filename.endswith(".py"):
                file_path = os.path.join(root, filename)
                with open(file_path, "r") as file:
                    file_content = file.read()
                    if "def main()" in file_content:
                        return os.path.relpath(file_path, root_dir)
    return None

def bootstrap_app(args):
    is_running_as_sudo = is_sudo()

    # Determine temp and app bundle directories based on sudo status
    temp_dir = get_temp_dir(is_running_as_sudo)
    app_bundle_dir = get_app_bundle_dir(is_running_as_sudo)

    # Ensure the target directories exist and create them if they don't
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(app_bundle_dir, exist_ok=True)

    # Step 1: Download and install the PyPI package using 'apkg'
    package_name = args.package_name

    # Example: apkg get-pypi package_name -t /target/dir/
    package_dir = os.path.join(app_bundle_dir, package_name)  # Set the package directory in the app bundle
    apkg_command = ["apkg", "get-pypi", package_name, "-t", package_dir]  # Use package_dir as the target

    try:
        subprocess.run(apkg_command, check=True)
    except subprocess.CalledProcessError:
        print(f"Failed to download and install '{package_name}' from PyPI.")
        return

    print(f"'{package_name}' successfully installed in '{package_dir}'.")

    # Step 2: Check if a 'bin' folder exists within the package directory
    bin_folder = os.path.join(package_dir, "bin")

    if os.path.exists(bin_folder) and os.path.isdir(bin_folder):
        # If 'bin' folder exists, use binaries within it
        bin_files = [f for f in os.listdir(bin_folder) if os.path.isfile(os.path.join(bin_folder, f))]
        if bin_files:
            # Use the first binary found as the executable
            executable = os.path.join("bin", bin_files[0])
        else:
            print(f"No binary files found in 'bin' folder of '{package_name}'.")
            executable = None
    else:
        # If 'bin' folder doesn't exist, find the main Python file
        main_file_rel_path = find_main_file(package_dir)
        if main_file_rel_path:
            # Use the main file as the executable
            executable = main_file_rel_path
        else:
            print(f"No 'main()' function found in '{package_name}' and no 'bin' folder found.")
            executable = None

    if executable:
        # Step 3: Create metadata.json with the executable information
        app_name = package_name.replace("-", "_")  # Modify the app name as needed

        metadata = {
            "name": app_name,
            "bin": executable,  # Set the executable path
            "version": "1.0.0",  # You can specify the version here
            "description": f"App bundle for {app_name}",
        }

        metadata_path = os.path.join(app_bundle_dir, app_name, "metadata.json")
        os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
        with open(metadata_path, "w") as metadata_file:
            json.dump(metadata, metadata_file, indent=4)

        print(f"App bundle created at '{os.path.join(app_bundle_dir, app_name)}'.")
    else:
        print(f"Failed to create app bundle for '{package_name}'.")

def install_app(args):
    # Implement the logic to install an app from a repository
    print(f"Installing app: {args.app_name}")

def run_app(args):
    app_name = args.bundle_name  # The bundle name is used as the app name
    app_bundle_dir = get_app_bundle_dir(is_sudo())
    app_bundle_path = os.path.join(app_bundle_dir, app_name)

    # Check if the app bundle directory exists
    if not os.path.exists(app_bundle_path):
        print(f"App bundle '{app_name}' not found in '{app_bundle_dir}'.")
        return

    metadata_path = os.path.join(app_bundle_path, "metadata.json")

    # Check if metadata.json exists within the app bundle
    if os.path.exists(metadata_path):
        with open(metadata_path, "r") as metadata_file:
            metadata = json.load(metadata_file)

            executable = metadata.get("bin")

            if executable:
                executable_path = os.path.join(app_bundle_path, executable)

                # Check if the executable file exists
                if os.path.exists(executable_path):
                    try:
                        # Pass any additional arguments to the executable
                        subprocess.run([executable_path] + args.args, check=True)
                    except subprocess.CalledProcessError:
                        print(f"Failed to run '{executable_path}'.")
                else:
                    print(f"Executable '{executable_path}' not found.")
            else:
                print("Executable information not found in metadata.json.")
    else:
        print("metadata.json not found in the app bundle.")

def delete_app(args):
    app_name = args.bundle_name  # The bundle name is used as the app name
    app_bundle_dir = get_app_bundle_dir(is_sudo())
    app_bundle_path = os.path.join(app_bundle_dir, app_name)

    # Check if the app bundle directory exists
    if not os.path.exists(app_bundle_path):
        print(f"App bundle '{app_name}' not found in '{app_bundle_dir}'.")
        return

    # Ask for confirmation before deleting
    confirmation = input(f"Delete {app_name}? (Y/n): ").strip().lower()
    
    if confirmation == 'y':
        try:
            # Delete the app bundle folder
            shutil.rmtree(app_bundle_path)
            print(f"Deleted {app_name}.")
        except Exception as e:
            print(f"Failed to delete {app_name}: {e}")
    else:
        print(f"{app_name} was not deleted.")

def main():
    parser = argparse.ArgumentParser(description="aapp-cli: Advanced App CLI")
    subparsers = parser.add_subparsers(title="Available commands", dest="command")

    # Define the 'install' command
    install_parser = subparsers.add_parser("install", help="Install an app from a repository")
    install_parser.add_argument("app_name", help="Name of the app to install")

    # Define the 'bootstrap' command
    bootstrap_parser = subparsers.add_parser("bootstrap", help="Bootstrap an app from a PyPI package")
    bootstrap_parser.add_argument("package_name", help="Name of the package to bootstrap")

    # Define the 'run' command
    run_parser = subparsers.add_parser("run", help="Run an app bundle")
    run_parser.add_argument("bundle_name", help="Name of the app bundle to run")
    run_parser.add_argument("--args", nargs=argparse.REMAINDER, help="Additional arguments for the app")

    # Define the 'delete' command
    delete_parser = subparsers.add_parser("delete", help="Delete an app")
    delete_parser.add_argument("bundle_name", help="Name of the app bundle to delete")

    args = parser.parse_args()

    if args.command == "install":
        install_app(args)
    elif args.command == "bootstrap":
        bootstrap_app(args)
    elif args.command == "run":
        run_app(args)
    elif args.command == "delete":
        delete_app(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

