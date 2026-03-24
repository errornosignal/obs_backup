#!/usr/bin/env python3
# script to export OBS profile and scene collection with assets

import os
import sys
import json
import zipfile
import shutil
from pathlib import Path
from typing import Set
from obswebsocket import obsws, requests # type: ignore
import obs_ws_pass # Separate file to store OBS WebSocket password for security - create obs_ws_pass.py with a variable named 'password' containing your OBS WebSocket password

host = "localhost" # Change to your OBS IP address if not running on the same machine
port = 4455 # Default for OBS 28+
password = obs_ws_pass.password  # import from obs_ws_pass.py
INCLUDE_SENSITIVE = False # Set to True if you want to include stream key in the export (service.json)

# Directory to export profile data - adjust as needed
PROFILE_EXPORT_PATH = os.path.expandvars(r"%UserProfile%\OneDrive\Documents\config-backups_local\OBS\Backups\Profile Backups")
# Directory to export scene collection data - adjust as needed
SCENE_COLLECTION_EXPORT_PATH = os.path.expandvars(r"%UserProfile%\OneDrive\Documents\config-backups_local\OBS\Backups\Scene Collection Backups")

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
        # Get current scene collection name
        scene_collection = ws.call(requests.GetSceneCollectionList()).getcurrentSceneCollectionName()
        print(f"[INFO] Current OBS Scene Collection: {scene_collection}")

    except Exception as e:
        print(f"[ERROR] {e}")
    # Ensure we disconnect from OBS WebSocket even if an error occurs
    finally:
        try:
            ws.disconnect()
            print("[INFO] Disconnected from OBS.")
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
    #
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

# Function to export OBS profile to ZIP file
def export_obs_profile(profile_name, export_path, include_sensitive=False):
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

        # Clean up temp folder
        shutil.rmtree(temp_dir)

        print(f"[INFO] ✅ Profile '{profile_name}' exported to '{zip_file_path}'")
    except Exception as e:  
        print(f"[ERROR] ❌ Failed to export profile: {e}")

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
    except Exception as e:
        print(f"[ERROR] ❌ Failed to export scene collection: {e}")

if __name__ == "__main__":
    # Get current profile and scene collection from OBS
    current_profile, scene_collection = obs_websocket_get_current_profile_and_scene_collection()
    # Export profile if found, otherwise skip
    if current_profile:
        export_obs_profile(current_profile, f"{PROFILE_EXPORT_PATH}\\{current_profile}.zip", INCLUDE_SENSITIVE)
    # Export scene collection with assets if found, otherwise skip
    if scene_collection:
        export_scene_collection(scene_collection, f"{SCENE_COLLECTION_EXPORT_PATH}\\{scene_collection}.zip")

# Wait for user input before exiting
wait = input("Press Enter to exit...")
