import json
import os

DATA_FILE = "server_data.json"
SERVER_DATA = {}


def load_data():
    """Load the JSON data from the file into memory."""
    global SERVER_DATA
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                SERVER_DATA = json.load(f)
            except json.JSONDecodeError:
                SERVER_DATA = {}
                print("⚠️ server_data.json was corrupted. Started fresh.")
    else:
        SERVER_DATA = {}
    print("--- Server Data (JSON) Loaded ---")


def save_data():
    """Save the memory data back to the JSON file."""
    with open(DATA_FILE, "w") as f:
        json.dump(SERVER_DATA, f, indent=4)


def get_guild_data(guild_id: int) -> dict:
    """Retrieve or initialize data for a specific guild."""
    guild_id_str = str(guild_id)

    if guild_id_str not in SERVER_DATA:
        SERVER_DATA[guild_id_str] = {
            "settings": {
                "log_channel_id": None,
                "welcome_channel_id": None,
            },
            "custom_commands": {},
        }
        save_data()  # Save immediately so the file updates

    return SERVER_DATA[guild_id_str]
