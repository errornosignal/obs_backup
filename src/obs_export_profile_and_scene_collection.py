#!/usr/bin/env python3
# script to export OBS profile and scene collection with assets

import os
import shutil
import zipfile
from pathlib import Path
import json
from obswebsocket import obsws, requests # type: ignore
import obs_ws_pass


host = "localhost" # Change to your OBS IP address if not running on the same machine
port = 4455 # Default for OBS 28+
password = obs_ws_pass.password  # Leave empty if authentication is disabled

INCLUDE_SENSITIVE = False # Set to True if you want to include stream key in the export (service.json)

PROFILE_EXPORT_PATH = r"%UserProfile%\OneDrive\Documents\config-backups_local\OBS\Backups\Profile Backups" # Directory to export profile data
PROFILE_EXPORT_PATH = os.path.expandvars(PROFILE_EXPORT_PATH)

SCENE_FILE_PATH = r"%AppData%\obs-studio\basic\scenes"  # OBS scene collection JSON files are stored here by default - adjust only if you have a custom setup  
SCENE_FILE_PATH = os.path.expandvars(SCENE_FILE_PATH)

SCENE_COLLECTION_EXPORT_PATH = r"%UserProfile%\OneDrive\Documents\config-backups_local\OBS\Backups\Scene Collection Backups" #  Directory to export scene collection data
SCENE_COLLECTION_EXPORT_PATH = os.path.expandvars(SCENE_COLLECTION_EXPORT_PATH)

# Function to get current profile and scene collection from OBS via WebSocket
def obs_websocket_get_current_profile_and_scene_collection():
    try:
        # Connect to OBS WebSocket
        ws = obsws(host, port, password)
        ws.connect()
        print("[INFO] Connected to OBS WebSocket.")

        # Get current profile name
        current_profile = ws.call(requests.GetProfileList()).getcurrentProfileName()
        print(f"[INFO] Current OBS Profile: {current_profile}")

        scene_collection = ws.call(requests.GetSceneCollectionList()).getcurrentSceneCollectionName()
        print(f"[INFO] Current OBS Scene Collection: {scene_collection}")

    except Exception as e:
        print(f"[ERROR] {e}")

    finally:
        try:
            ws.disconnect()
            print("[INFO] Disconnected from OBS.")
        except Exception as e:
            print(f"[ERROR] Failed to disconnect from OBS: {e}")
    return current_profile, scene_collection

# Function to export OBS profile to ZIP file
def export_obs_profile(profile_name, export_path, include_sensitive=False):
    """
    Export an OBS Studio profile to a ZIP file.

    :param profile_name: Name of the OBS profile to export
    :param export_path: Destination path for the ZIP file
    :param include_sensitive: If False, removes service.json (contains stream key)
    """
    
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

    # Clean up temp folder
    shutil.rmtree(temp_dir)

    print(f"[INFO] Profile '{profile_name}' exported to {zip_file_path}")

# Function to export OBS scene collection with assets
def export_obs_scene_collection(scene_collection, scene_json_path, output_zip_path):
    """
    Exports an OBS scene collection JSON and all referenced assets into a ZIP file.
    """

    # Resolve the scene collection JSON path
    scene_json_path = Path(scene_json_path).expanduser().resolve()
    # Check if the scene collection JSON file exists
    if not os.path.exists(scene_json_path):
        raise FileNotFoundError(f"Scene collection file not found: {scene_json_path}")

    # Load the scene collection JSON
    with open(scene_json_path, "r", encoding="utf-8") as f:
        try:
            scene_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON file: {e}")

    # Create a temporary export folder
    export_folder = scene_json_path.parent / (scene_json_path.stem + "_export")
    if export_folder.exists():
        shutil.rmtree(export_folder)
    export_folder.mkdir(parents=True)

    # Copy the JSON file
    shutil.copy(scene_json_path, export_folder / scene_json_path.name)

    # Collect asset file paths
    asset_paths = set()
    def find_paths(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and os.path.isfile(v):
                    asset_paths.add(Path(v).resolve())
                else:
                    find_paths(v)
        elif isinstance(obj, list):
            for item in obj:
                find_paths(item)

    find_paths(scene_data)

    # Copy assets
    for asset in asset_paths:
        try:
            dest_path = export_folder / asset.name
            shutil.copy(asset, dest_path)
        except Exception as e:
            print(f"[ERROR] Warning: Could not copy {asset}: {e}")

    # Create ZIP archive
    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in export_folder.rglob("*"):
            zipf.write(file_path, file_path.relative_to(export_folder))

    print(f"[INFO] Scene Collection '{scene_collection}' exported to {output_zip_path}")

# Main execution
if __name__ == "__main__":
    # Get current profile and scene collection from OBS via WebSocket
    current_profile, scene_collection = obs_websocket_get_current_profile_and_scene_collection()
    # Export current profile with or without sensitive data based on the setting and only if a profile is currently active
    if current_profile:
        export_obs_profile(current_profile, f"{PROFILE_EXPORT_PATH}\\{current_profile}.zip", INCLUDE_SENSITIVE)
    # Export scene collection with assets if a scene collection is currently active
    if scene_collection:
        export_obs_scene_collection(scene_collection, f"{SCENE_FILE_PATH}\\{scene_collection}.json", f"{SCENE_COLLECTION_EXPORT_PATH}\\{scene_collection}_with_assets.zip")

# Wait for user input before exiting to allow time to read any messages in the console
wait = input("Press Enter to exit...")


