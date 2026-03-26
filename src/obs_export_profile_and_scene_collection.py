#!/usr/bin/env python3
# script to export OBS profile and scene collection with assets

import os
import sys
import re
import json
import zipfile
import shutil
from pathlib import Path
from typing import Set
from datetime import datetime
from obswebsocket import obsws, requests # type: ignore

# import websocket connection properties from file in '~/Secrets' dir
sys.path.append(os.path.expanduser("~/Secrets"))
from obs_ws_conn_info import host as ws_host, port as ws_port, password as ws_password # type: ignore

# Set to True if you want to include stream key in the export (service.json)
INCLUDE_SENSITIVE = False
# Storage for advanced-scene-switcher config file path
ADVSS_SETTINGS_FILE = "" # <--- global variable

# Upper-level paths
# Directory where all OBS backups are stored
EXPORT_PATH_PREFIX = "D:/Users/error/OneDrive/Documents/config-backups_local/OBS/Backups"
# Directory where OBS plugin config files are stored
PLUGIN_PATH_PREFIX = "C:/Users/error/AppData/Roaming/obs-studio/plugin_config"

# Sub-dir path building
# Directory to export profile data
PROFILE_EXPORT_PATH = (f"{EXPORT_PATH_PREFIX}/Profile Backups")
# Directory to export scene collection data
SCENE_COLLECTION_EXPORT_PATH = (f"{EXPORT_PATH_PREFIX}/Scene Collection Backups")
# Directory to export Advanced Scene Switcher config
ADVSS_EXPORT_PATH = (f"{EXPORT_PATH_PREFIX}/Plugin Settings Backup/Advanced Scene Switcher")
# Directory where advanced-scene-switcher plugin config files are stored
ADVSS_PLUGIN_CONFIG_DIR = (f"{PLUGIN_PATH_PREFIX}/advanced-scene-switcher")

# Function to get current date and time as a string
def get_date_time_string() -> str:
    """Return a string with the current date and time in the format YYYY.MM.DD.HH.MM.SS."""
    now = datetime.now()
    return now.strftime("%Y.%m.%d.%H.%M.%S")

# Function to get current profile and scene collection from OBS via WebSocket
def obs_websocket_get_current_profile_and_scene_collection() -> tuple[str, str]:
    try:
        # Connect to OBS WebSocket
        ws = obsws(ws_host, ws_port, ws_password)
        ws.connect()
        print("[INFO] Connected to OBS WebSocket.")

        # Get current profile name
        current_profile = ws.call(requests.GetProfileList()).getcurrentProfileName()
        print(f"[INFO] Current OBS Profile: '{current_profile}'")
        # Get current scene collection name
        scene_collection = ws.call(requests.GetSceneCollectionList()).getcurrentSceneCollectionName()
        print(f"[INFO] Current OBS Scene Collection: '{scene_collection}'")

    except Exception as e:
        print(f"[ERROR] {e}")
    # Ensure we disconnect from OBS WebSocket even if an error occurs
    finally:
        try:
            ws.disconnect()
            print("[INFO] Disconnected from OBS WebSocket.")
        except Exception as e:
            print(f"[ERROR] Failed to disconnect from OBS: {e}")
    # Return the current profile and scene collection names
    return current_profile, scene_collection

# Function to find config path based on OS
def get_obs_config_path() -> Path:
    """Return the default OBS Studio config path based on OS."""
    # OBS stores scene collection JSON files in the "basic/scenes" subdirectory of the config path
    if sys.platform.startswith("win"):
        return Path(os.getenv("APPDATA")) / "obs-studio" / "basic" / "scenes"
    # For macOS, OBS stores config in ~/Library/Application Support/obs-studio/basic/scenes
    elif sys.platform.startswith("darwin"):  # macOS
        return Path.home() / "Library" / "Application Support" / "obs-studio" / "basic" / "scenes"
    # For Linux, OBS typically uses ~/.config/obs-studio/basic/scenes
    else:  # Linux and others
        return Path.home() / ".config" / "obs-studio" / "basic" / "scenes"

# Function to find the scene collection JSON file based on the scene collection name
def find_scene_file(scene_name: str) -> Path:
    """Find the JSON file for the given scene collection name."""
    # Use the get_obs_config_path() function to return the config path and a JSON file with the name of the scene collection
    config_path = get_obs_config_path()
    scene_file = config_path / f"{scene_name}.json"
    # Check if the scene collection file exists, if not raise an error
    if not scene_file.exists():
        raise FileNotFoundError(f"Scene collection '{scene_name}' not found in {config_path}")
    return scene_file

# Function to extract media file paths from scene JSON
def extract_media_paths(scene_json_path: Path) -> Set[Path]:
    """Extract all media file paths from the scene JSON."""
    # Recursively search through the scene JSON for any string values that are valid file paths and return a set of unique media file paths
    media_files = set()
    with open(scene_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    def recurse(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and os.path.isfile(v):
                    media_files.add(Path(v))
                else:
                    recurse(v)
        elif isinstance(obj, list):
            for item in obj:
                recurse(item)

    recurse(data)
    return media_files

# Function to export an OBS profile to a ZIP file, optionally removing sensitive files like service.json which contains the stream key
def export_obs_profile(profile_name, export_path, include_sensitive=False) -> None:
    """
    Export an OBS Studio profile to a ZIP file.

    :param profile_name: Name of the OBS profile to export
    :param export_path: Destination path for the ZIP file
    :param include_sensitive: If False, removes service.json (contains stream key)
    """
    # export OBS profile by copying the profile folder, optionally removing sensitive files, and zipping it up
    try:
        obs_config_dir = Path(os.getenv("APPDATA")) / "obs-studio" / "basic" / "profiles"
        profile_dir = obs_config_dir / profile_name

        # Check if the profile directory exists
        if not profile_dir.exists():
            raise FileNotFoundError(f"Profile '{profile_name}' not found in {obs_config_dir}")

        # Create a temporary copy
        temp_dir = Path(export_path).parent / f"{profile_name}_temp"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        shutil.copytree(profile_dir, temp_dir)

        # Remove sensitive file if requested
        if not include_sensitive:
            sensitive_file = temp_dir / "service.json"
            if sensitive_file.exists():
                sensitive_file.unlink()

        # Create ZIP file
        zip_file_path = Path(export_path)
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    file_path = Path(root) / file
                    zipf.write(file_path, file_path.relative_to(temp_dir))
        if os.path.isfile(zip_file_path):
            print(f"[INFO] ✅ Profile '{profile_name}' exported to '{zip_file_path}'")

        # Clean up temp folder
        shutil.rmtree(temp_dir)

        return
    except Exception as e:  
        print(f"[ERROR] ❌ Failed to export profile: {e}")

# Function to update OBS Scene file config with the most recent Advanced Scene Switcher export path 
def update_obs_config(config_pattern: str, new_path: str) -> None:
    """Update Advanced Scene Switcher lastImportPath in the OBS Scene config JSON."""
    try:  
        # Use pathlib to find the config file matching the pattern
        matching_files = Path(config_pattern)
        # Check if any files match the pattern, if not raise an error
        if not matching_files:
            raise FileNotFoundError(f"No config files match pattern: {config_pattern}")
        else:
            with open(matching_files, "r", encoding="utf8") as file:
                data = json.load(file)

            if not isinstance(data, dict):
                raise ValueError("Expected a JSON array at the root.")
            
            # Define the keys to navigate through the JSON structure
            key1 = "modules"
            key2 = "advanced-scene-switcher"
            key3 = "lastImportPath"
            hard_break = False
            # Loop through with a counter using enumerate()
            for index1, item1 in enumerate(data, start=1):
                # Validate that each item is a dictionary
                if not isinstance(item1, dict):
                    if item1 == key1:
                        # If we find the "modules" key, we need to check if its value is a dictionary before proceeding
                        for index2, item2 in enumerate(data[item1], start=1):
                            # Validate that the item is not a dictionary before checking for the key
                            if not isinstance(item2, dict):
                                if item2 == key2:
                                    # If we find the "advanced-scene-switcher" key, we need to check if its value is a dictionary before proceeding
                                    for index3, item3 in enumerate(data[item1][item2], start=1):
                                        # Validate that the item is not a dictionary before checking for the key
                                        if not isinstance(item3, dict): 
                                            if item3 == key3:
                                                # update the value if it were a dictionary
                                                data[item1][item2][item3] = new_path
                                                # validate that the value was updated correctly
                                                if data[item1][item2][item3] == new_path:
                                                    # Set a flag to break out of the outer loops after updating
                                                    hard_break = True
                                                    # print success message with the file name and the new path
                                                    print(f"[INFO] ✅ Updated 'lastImportPath' in '{matching_files}'\n\t to '{new_path}'")
                                                    break  # Exit the innermost loop after updating
                                                # if the value was not updated correctly, print an error message
                                                else:
                                                    print(f"[ERROR] ❌ Failed to update 'lastImportPath' in '{matching_files}'")
                                        else:
                                            print(f"[ERROR] ❌ Expected a dictionary at index '{index3}' \n\t in '{matching_files}', but got {type(item3).__name__}")
                                    if hard_break:  
                                        break  # Exit the second loop if the update was successful
                            else:
                                print(f"[ERROR] ❌ Expected a dictionary at index ['{index2}'] \n\t in '{matching_files}', but got {type(item2).__name__}")    
                        if hard_break:  
                            break  # Exit the outer loop if the update was successful
                else:
                    print(f"[ERROR] ❌ Expected a dictionary at index '{index1}' \n\t in '{matching_files}', but got {type(item1).__name__}")
            # Write the updated JSON back to the file
            with open(matching_files, "w", encoding="utf8") as file:
                json.dump(data, file, indent=4)
            return

    # Handle potential JSON decoding errors or other exceptions
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON in config file: {config_pattern}")
    except Exception as e:
        raise RuntimeError(f"Error updating config: {e}") 

# Function to export the most recent Advanced Scene Switcher config to the backup directory 
def export_advss_config(scene_collection) -> None:
    """Export Advanced Scene Switcher config TXT file."""
    # Define source file for the backup export using the global variable that was set in advanced_scence_switcher_export_handle()
    source_file = ADVSS_SETTINGS_FILE  # <--- global variable
    
    # Define destination folder for the backup export
    destination_folder = ADVSS_EXPORT_PATH
    
    # Define new file name with scene collection name and current date/time
    new_file_name = f"adv-ss-{scene_collection}-{get_date_time_string()}.txt"

    # Ensure destination folder exists
    os.makedirs(destination_folder, exist_ok=True)

    # Construct full destination path
    destination_file = os.path.join(destination_folder, new_file_name)

    # Copy the file from source to destination with the new name
    shutil.copy2(source_file, destination_file)

    print(f"[INFO] ✅ ADVSS settings exported to: '{destination_file}'")
    return

# Function to return the most recent Advanced Scene Switcher config file path from the plugin config directory, matching the current scene collection name  
def get_advss_most_recent_settings_file(scene_collection) -> str:
    """Get the most recent Advanced Scene Switcher config file path from the plugin config directory, matching the current active scene collection name."""
    # Define the OBS plugin config directory for Advanced Scene Switcher - adjust as needed
    advss_plugin_config_dir = ADVSS_PLUGIN_CONFIG_DIR
    # Define the regex pattern to match config files (e.g., settings-backup-*.json)
    substring_to_find = re.compile("^settings-backup-.*.json$")
    
    # List to store matching config files
    matches = []

    # Check if the plugin config directory exists before attempting to list files
    if os.path.isdir(advss_plugin_config_dir):
        try:
            # List all files in the plugin config directory and filter based on the regex pattern
            for entry in os.listdir(advss_plugin_config_dir):
                full_path = os.path.join(advss_plugin_config_dir, entry)
                if os.path.isfile(full_path) and substring_to_find.search(entry):
                    matches.append(entry)
        except PermissionError as e:
            print(f"[ERROR] Permission denied while accessing {advss_plugin_config_dir}: {e}")

        # If no matching config files are found, print an error message and exit the function
        if not matches:
            print(f"[ERROR] No config files matching the pattern were found in \n\t {advss_plugin_config_dir}")
            return
        # If matching config files are found, get the most recent one and set the global variable to its path for use in the export function
        global ADVSS_SETTINGS_FILE # <--- global variable
        ADVSS_SETTINGS_FILE = get_most_recent_file(advss_plugin_config_dir, matches)

        # Get the most recent config file from the backups
        most_recent_file = get_most_recent_file(ADVSS_EXPORT_PATH, None)
    
        return most_recent_file

# Function to get the most recently modified file in a directory and return its path, filtering by a list of matches
def get_most_recent_file(directory: str, matches: list) -> str:
    """Return the most recently modified file in the given directory."""
    try:
        if matches:
            files = [f for f in Path(directory).glob("*") if f.is_file() and f.name in matches]
        else:
            files = [f for f in Path(directory).glob("*") if f.is_file()]
        if not files:
            raise FileNotFoundError(f"No files found in directory: {directory}")
        # Sort by modification time (latest first)
        latest_file = max(files, key=lambda f: f.stat().st_mtime)
        #print(f"[INFO] Most recent file in '{directory}': {latest_file}")
        return str(latest_file.resolve())
    except Exception as e:
        raise RuntimeError(f"Error finding most recent file: {e}")  

# Function to export scene collection and all assets to a ZIP file
def export_scene_collection(scene_name: str, output_zip: str) -> None:
    """Export the scene collection and all assets into a ZIP file."""
    # Get the scene collection file and extract media paths, then create ZIP
    try:
        scene_file = find_scene_file(scene_name)
        media_files = extract_media_paths(scene_file)

        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add the scene JSON
            zipf.write(scene_file, arcname=scene_file.name)

            # Add all media files
            for media in media_files:
                if media.exists():
                    zipf.write(media, arcname=f"assets/{media.name}")
                else:
                    print(f"[INFO] ⚠ Skipping missing file: {media}")

        print(f"[INFO] ✅ Scene '{scene_name}' exported to '{output_zip}'")
        return
    except Exception as e:
        print(f"[ERROR] ❌ Failed to export scene collection: {e}")

if __name__ == "__main__":
    # Get current profile and scene collection from OBS
    current_profile, scene_collection = obs_websocket_get_current_profile_and_scene_collection()
    # Export profile if found, otherwise skip
    if current_profile:
        export_obs_profile(current_profile, f"{PROFILE_EXPORT_PATH}/{current_profile}.zip", INCLUDE_SENSITIVE)

    #   
    recent_advsss_settings_file = get_advss_most_recent_settings_file(scene_collection)
    
    #   
    export_advss_config(scene_collection)
    
    # Update OBS Scene file config with the path to the most recent Advanced Scene Switcher export 
    update_obs_config(find_scene_file(scene_collection), recent_advsss_settings_file) 
    
    # Export scene collection with assets if found, otherwise skip
    if scene_collection:
        export_scene_collection(scene_collection, f"{SCENE_COLLECTION_EXPORT_PATH}/{scene_collection}.zip")

# Wait for user input before exiting
wait = input("Press Enter to exit...")
