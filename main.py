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
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="$", intents=intents)
        self.db_name = "bot_database.db"

    async def setup_hook(self):
        # 1. Initialize SQLite (Database)
        await initialize_database()
        self.db = await aiosqlite.connect(self.db_name)

        # 2. Initialize JSON (Settings)
        load_data()  # <--- LOAD YOUR JSON HERE

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
