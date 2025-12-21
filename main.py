import asyncio
import os

import aiosqlite
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Import database configuration
# This ensures main.py uses the exact same DB path as your setup script
from utils.database import DB_NAME, initialize_database

# Load environment variables (for local testing)
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")


class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=discord.Intents.all(),  # Requires "Privileged Intents" in Dev Portal
            help_command=None,
        )
        # Initialize db as None so the bot doesn't crash if it fails before connecting
        self.db = None

    async def setup_hook(self):
        print("--- Starting Setup ---")

        # 1. Initialize Database Tables (and create 'data' folder)
        await initialize_database()
        print("--- Database Tables Checked ---")

        # 2. Open Persistent Database Connection
        # We use the DB_NAME imported from utils.database to ensure consistency
        self.db = await aiosqlite.connect(DB_NAME)
        print(f"--- Connected to Database at {DB_NAME} ---")

        # 3. Load Cogs
        # Add any new cogs to this list (filename without .py)
        initial_extensions = [
            "cogs.leveling",
            "cogs.pokemon",
            "cogs.music",
            "cogs.admin",
            "cogs.help",
            "cogs.combat",
        ]

        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
                print(f"Loaded extension: {extension}")
            except Exception as e:
                print(f"Failed to load extension {extension}: {e}")

        # 4. Sync Slash Commands
        # This registers your /commands with Discord
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

    async def close(self):
        # Safely close the database when the bot shuts down
        if self.db:
            await self.db.close()
            print("--- Database Connection Closed ---")
        await super().close()

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")


client = MyBot()


# Optional: Manual Sync Command (!sync)
@client.command()
async def sync(ctx):
    try:
        synced = await client.tree.sync()
        await ctx.send(f"Synced {len(synced)} commands.")
    except Exception as e:
        await ctx.send(f"Sync failed: {e}")


if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_TOKEN not found. Check your .env or Coolify variables.")
    else:
        client.run(TOKEN)
