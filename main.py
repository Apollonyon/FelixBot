import os

import aiosqlite
import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils.data_manager import load_data

# --- IMPORTS ---
from utils.database import initialize_database

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")


class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!", intents=discord.Intents.all(), help_command=None
        )
        # Fix: Initialize db variable as None so it doesn't crash on error
        self.db = None

    async def setup_hook(self):
            # 1. Initialize DB Table
            await initialize_database()

            # 2. Open Persistent Connection
            # Make sure to import DB_NAME from utils.database at the top of main.py!
            from utils.database import DB_NAME
            self.db = await aiosqlite.connect(DB_NAME)

        # 3. Load Cogs
            print("--- Loading Cogs ---")
            for filename in os.listdir("./cogs"):
                if filename.endswith(".py"):
                    try:
                        await self.load_extension(f"cogs.{filename[:-3]}")
                        print(f"Loaded extension: {filename}")
                    except Exception as e:
                        print(f"Failed to load {filename}: {e}")
        print("--- Cogs Loaded ---")

    async def close(self):
        await self.db.close()
        await super().close()


client = MyBot()


# Sync command to register Slash Commands manually
@client.command()
@commands.is_owner()
async def sync(ctx):
    try:
        synced = await client.tree.sync()
        await ctx.send(f"Synced {len(synced)} command(s) globally.")
    except Exception as e:
        await ctx.send(f"Error syncing: {e}")


@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")


if TOKEN:
    client.run(TOKEN)
else:
    print("Error: Token not found.")
