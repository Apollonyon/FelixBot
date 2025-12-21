import os
import uuid

import aiosqlite

DB_FOLDER = "data"
DB_NAME = f"{DB_FOLDER}/bot_database.db"


async def initialize_database():
    os.makedirs(DB_FOLDER, exist_ok=True)

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA synchronous=NORMAL;")

        async with db.cursor() as cursor:
            # 1. Users
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_uuid TEXT PRIMARY KEY,
                    discord_id INTEGER UNIQUE,
                    username TEXT
                )
            """)

            # 2. Mod Logs
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS mod_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_uuid TEXT,
                    mod_uuid TEXT,
                    action_type TEXT,
                    reason TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 3. Levels
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS levels (
                    user_uuid TEXT PRIMARY KEY,
                    guild_id INTEGER,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1
                )
            """)

            # 4. Gacha Profile
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS game_profile (
                    user_uuid TEXT PRIMARY KEY,
                    available_pulls INTEGER DEFAULT 0,
                    last_daily DATETIME,
                    coins INTEGER DEFAULT 0
                )
            """)

            # 5. Collection (With Shiny Support)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS collection (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_uuid TEXT,
                    pokemon_id INTEGER,
                    pokemon_name TEXT,
                    is_shiny BOOLEAN DEFAULT 0,
                    is_legendary BOOLEAN DEFAULT 0,
                    caught_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # --- MIGRATION: Force Add Columns if Missing ---
            # This fixes your error!
            try:
                await cursor.execute(
                    "ALTER TABLE collection ADD COLUMN is_shiny BOOLEAN DEFAULT 0"
                )
            except aiosqlite.OperationalError:
                pass  # Column already exists, ignore error

            try:
                await cursor.execute(
                    "ALTER TABLE collection ADD COLUMN is_legendary BOOLEAN DEFAULT 0"
                )
            except aiosqlite.OperationalError:
                pass

        await db.commit()
        print(f"--- Database Initialized (WAL Mode) at {DB_NAME} ---")


async def get_or_create_uuid(db, discord_id: int, username: str = None):
    async with db.cursor() as cursor:
        await cursor.execute(
            "SELECT user_uuid FROM users WHERE discord_id = ?", (discord_id,)
        )
        result = await cursor.fetchone()

        if result:
            uuid_str = result[0]
            if username:
                await cursor.execute(
                    "UPDATE users SET username = ? WHERE discord_id = ?",
                    (username, discord_id),
                )
            return uuid_str
        else:
            new_uuid = str(uuid.uuid4())
            await cursor.execute(
                "INSERT INTO users (user_uuid, discord_id, username) VALUES (?, ?, ?)",
                (new_uuid, discord_id, username),
            )
            return new_uuid
