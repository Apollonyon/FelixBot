import asyncio
import datetime
import random
from io import BytesIO

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image  # New Library for processing images

# Import database connection
from utils.database import get_or_create_uuid


# --- HELPER: Image Collage Generator ---
def generate_collage(images_bytes):
    """
    Takes a list of image bytes, creates a 5-column grid.
    Sprites are usually 96x96. We'll make 100x100 slots.
    """
    if not images_bytes:
        return None

    # Settings
    img_width, img_height = 96, 96
    columns = 5
    rows = (len(images_bytes) + columns - 1) // columns  # Calculate needed rows

    # Create blank canvas (Transparent background)
    canvas_width = columns * img_width
    canvas_height = rows * img_height
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

    for i, img_data in enumerate(images_bytes):
        try:
            # Open the image from bytes
            with Image.open(BytesIO(img_data)) as img:
                # Calculate position
                x = (i % columns) * img_width
                y = (i // columns) * img_height

                # Paste onto canvas
                canvas.paste(img, (x, y))
        except Exception as e:
            print(f"Error processing image {i}: {e}")

    # Save to bytes to send to Discord
    output_buffer = BytesIO()
    canvas.save(output_buffer, format="PNG")
    output_buffer.seek(0)  # Reset pointer to start
    return output_buffer


# --- VIEW (Buttons for Pokedex) ---
class PokedexView(discord.ui.View):
    def __init__(self, pokemon_list, user_name):
        super().__init__(timeout=60)
        self.pokemon_list = pokemon_list
        self.user_name = user_name
        self.index = 0

    def get_embed(self):
        poke_id, poke_name, count = self.pokemon_list[self.index]
        image_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{poke_id}.png"

        embed = discord.Embed(
            title=f"📖 Pokedex: {self.user_name}", color=discord.Color.red()
        )
        embed.description = f"**#{poke_id} {poke_name}**"
        embed.add_field(name="Times Caught", value=str(count), inline=True)
        embed.set_image(url=image_url)
        embed.set_footer(text=f"Page {self.index + 1} of {len(self.pokemon_list)}")
        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.primary)
    async def previous_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.index > 0:
            self.index -= 1
        else:
            self.index = len(self.pokemon_list) - 1
        await interaction.response.edit_message(embed=self.get_embed())

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.index < len(self.pokemon_list) - 1:
            self.index += 1
        else:
            self.index = 0
        await interaction.response.edit_message(embed=self.get_embed())


# --- MAIN COG ---
class PokemonGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Pokemon Cog is ready.")

    pokemon_group = app_commands.Group(
        name="pokemon", description="Gacha Game Commands"
    )

    async def fetch_random_pokemon(self, session=None):
        poke_id = random.randint(1, 1025)
        url = f"https://pokeapi.co/api/v2/pokemon/{poke_id}"

        async def fetch(s):
            async with s.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "id": data["id"],
                        "name": data["name"].capitalize(),
                        "image": data["sprites"]["front_default"],
                    }
                return None

        if session:
            return await fetch(session)
        else:
            async with aiohttp.ClientSession() as temp_session:
                return await fetch(temp_session)

    # --- ECONOMY COMMANDS ---
    @pokemon_group.command(name="balance", description="Check your Coins and Pulls")
    async def balance(self, interaction: discord.Interaction):
        await interaction.response.defer()

        user_uuid = await get_or_create_uuid(
            self.bot.db, interaction.user.id, interaction.user.name
        )

        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT available_pulls, coins FROM game_profile WHERE user_uuid = ?",
                (user_uuid,),
            )
            row = await cursor.fetchone()
            pulls, coins = row if row else (0, 0)

        embed = discord.Embed(
            title=f" Wallet: {interaction.user.name}", color=discord.Color.green()
        )
        embed.add_field(name="Coins", value=f"🪙 **{coins}**", inline=True)
        embed.add_field(name="Pulls", value=f"📦 **{pulls}**", inline=True)
        await interaction.followup.send(embed=embed)

    @pokemon_group.command(name="shop", description="Buy more pulls")
    async def shop(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛒 Pokémon Shop",
            description="Spend your coins here!",
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="📦 1x Pull", value="🪙 100 Coins\n`/pokemon buy pull`", inline=True
        )
        embed.add_field(
            name="📦 10x Pulls",
            value="🪙 900 Coins (Deal!)\n`/pokemon buy bulk`",
            inline=True,
        )
        await interaction.response.send_message(embed=embed)

    @pokemon_group.command(name="buy", description="Buy items from the shop")
    @app_commands.choices(
        item=[
            app_commands.Choice(name="1 Pull (100 Coins)", value="pull"),
            app_commands.Choice(name="10 Pulls (900 Coins)", value="bulk"),
        ]
    )
    async def buy(
        self, interaction: discord.Interaction, item: app_commands.Choice[str]
    ):
        await interaction.response.defer()
        user_uuid = await get_or_create_uuid(
            self.bot.db, interaction.user.id, interaction.user.name
        )

        cost = 100 if item.value == "pull" else 900
        amount = 1 if item.value == "pull" else 10

        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT coins FROM game_profile WHERE user_uuid = ?", (user_uuid,)
            )
            row = await cursor.fetchone()
            current_coins = row[0] if row else 0

            if current_coins < cost:
                await interaction.followup.send(
                    f"❌ You need **{cost} Coins** (You have {current_coins})."
                )
                return

            await cursor.execute(
                "UPDATE game_profile SET coins = coins - ?, available_pulls = available_pulls + ? WHERE user_uuid = ?",
                (cost, amount, user_uuid),
            )

        await self.bot.db.commit()
        await interaction.followup.send(
            f"✅ Purchase successful! Spent **{cost} Coins** for **{amount} Pulls**."
        )

    # --- STANDARD GAME COMMANDS ---

    @pokemon_group.command(name="daily", description="Get 5 free pulls daily!")
    async def daily(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_uuid = await get_or_create_uuid(
            self.bot.db, interaction.user.id, interaction.user.name
        )

        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT last_daily FROM game_profile WHERE user_uuid = ?", (user_uuid,)
            )
            row = await cursor.fetchone()

            if row and row[0]:
                last_daily = datetime.datetime.fromisoformat(row[0])
                if (datetime.datetime.now() - last_daily).total_seconds() < 86400:
                    next_daily = last_daily + datetime.timedelta(days=1)
                    timestamp = int(next_daily.timestamp())
                    await interaction.followup.send(f"⏳ Come back <t:{timestamp}:R>.")
                    return

            await cursor.execute(
                """
                INSERT INTO game_profile (user_uuid, available_pulls, last_daily, coins)
                VALUES (?, 5, ?, 0)
                ON CONFLICT(user_uuid) DO UPDATE SET
                available_pulls = available_pulls + 5,
                last_daily = ?
            """,
                (
                    user_uuid,
                    datetime.datetime.now().isoformat(),
                    datetime.datetime.now().isoformat(),
                ),
            )

        await self.bot.db.commit()
        await interaction.followup.send(f"📦 **Supply Drop!** +5 Poké Balls received.")

    @pokemon_group.command(name="pull", description="Use Poké Balls")
    @app_commands.describe(amount="How many to pull? (Optional, Default: 1, Max: 10)")
    async def pull(self, interaction: discord.Interaction, amount: int = 1):
        await interaction.response.defer()

        if amount > 10:
            await interaction.followup.send("❌ You can only pull 10 at a time!")
            return
        if amount < 1:
            await interaction.followup.send("❌ Amount must be at least 1.")
            return

        user_uuid = await get_or_create_uuid(
            self.bot.db, interaction.user.id, interaction.user.name
        )

        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT available_pulls FROM game_profile WHERE user_uuid = ?",
                (user_uuid,),
            )
            row = await cursor.fetchone()
            pulls = row[0] if row else 0

            if pulls < amount:
                await interaction.followup.send(
                    f"❌ Not enough Poké Balls! You have **{pulls}**, but tried to pull **{amount}**."
                )
                return

            await cursor.execute(
                "UPDATE game_profile SET available_pulls = available_pulls - ? WHERE user_uuid = ?",
                (amount, user_uuid),
            )

        await self.bot.db.commit()

        # Bulk Fetch
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_random_pokemon(session) for _ in range(amount)]
            results = await asyncio.gather(*tasks)

        caught_pokemon = [p for p in results if p is not None]

        if not caught_pokemon:
            await interaction.followup.send(
                "❌ Failed to catch any Pokémon (API Error)."
            )
            return

        # Save to DB
        async with self.bot.db.cursor() as cursor:
            for p in caught_pokemon:
                await cursor.execute(
                    "INSERT INTO collection (user_uuid, pokemon_id, pokemon_name) VALUES (?, ?, ?)",
                    (user_uuid, p["id"], p["name"]),
                )
        await self.bot.db.commit()

        # --- DISPLAY LOGIC ---
        if amount == 1:
            p = caught_pokemon[0]
            embed = discord.Embed(
                title=f"You caught a {p['name']}!",
                description=f"Balls left: {pulls - 1}",
                color=discord.Color.gold(),
            )
            embed.set_image(url=p["image"])
            embed.set_footer(text=f"ID: #{p['id']}")
            await interaction.followup.send(embed=embed)
        else:
            # MULTIPLE PULLS: Generate Collage
            desc = ""
            for p in caught_pokemon:
                desc += f"• **#{p['id']} {p['name']}**\n"

            # Download images for the collage
            image_bytes_list = []
            async with aiohttp.ClientSession() as session:
                for p in caught_pokemon:
                    if p["image"]:
                        async with session.get(p["image"]) as resp:
                            if resp.status == 200:
                                image_bytes_list.append(await resp.read())

            # Create the image file
            collage_buffer = await asyncio.to_thread(generate_collage, image_bytes_list)

            file = None
            if collage_buffer:
                file = discord.File(collage_buffer, filename="pulls.png")

            embed = discord.Embed(
                title=f"🔥 You caught {len(caught_pokemon)} Pokémon!",
                description=desc,
                color=discord.Color.gold(),
            )
            embed.set_footer(text=f"Balls left: {pulls - amount}")

            if file:
                embed.set_image(url="attachment://pulls.png")
                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send(embed=embed)

    @pokemon_group.command(name="pokedex", description="View your collection")
    async def pokedex(self, interaction: discord.Interaction):
        await interaction.response.defer()

        user_uuid = await get_or_create_uuid(
            self.bot.db, interaction.user.id, interaction.user.name
        )

        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT COUNT(DISTINCT pokemon_id) FROM collection WHERE user_uuid = ?",
                (user_uuid,),
            )
            unique_count = await cursor.fetchone()
            unique = unique_count[0] if unique_count else 0

            await cursor.execute(
                """
                SELECT pokemon_id, pokemon_name, COUNT(*) as count
                FROM collection
                WHERE user_uuid = ?
                GROUP BY pokemon_id
                ORDER BY pokemon_id ASC
            """,
                (user_uuid,),
            )
            rows = await cursor.fetchall()

        if not rows:
            await interaction.followup.send("❌ Pokedex empty.")
            return

        view = PokedexView(rows, interaction.user.name)
        embed = view.get_embed()
        embed.description = (
            f"**Progress: {unique} / 1025 Unique Species**\n" + embed.description
        )
        await interaction.followup.send(embed=embed, view=view)

    @pokemon_group.command(name="release", description="Sell Pokémon for 20 Coins each")
    @app_commands.describe(
        name="Name of the Pokémon", amount="How many to release? (Optional, Default: 1)"
    )
    async def release(
        self, interaction: discord.Interaction, name: str, amount: int = 1
    ):
        await interaction.response.defer()
        if amount < 1:
            await interaction.followup.send("❌ Amount must be at least 1.")
            return

        user_uuid = await get_or_create_uuid(
            self.bot.db, interaction.user.id, interaction.user.name
        )
        pokemon_name = name.capitalize()

        async with self.bot.db.cursor() as cursor:
            # 1. Check ownership count
            await cursor.execute(
                "SELECT count(*) FROM collection WHERE user_uuid = ? AND pokemon_name = ?",
                (user_uuid, pokemon_name),
            )
            count_row = await cursor.fetchone()
            owned_count = count_row[0] if count_row else 0

            if owned_count < amount:
                await interaction.followup.send(
                    f"❌ You only have **{owned_count}** {pokemon_name}(s). You cannot release {amount}."
                )
                return

            # 2. Delete N specific rows
            await cursor.execute(
                """
                DELETE FROM collection
                WHERE id IN (
                    SELECT id FROM collection
                    WHERE user_uuid = ? AND pokemon_name = ?
                    LIMIT ?
                )
            """,
                (user_uuid, pokemon_name, amount),
            )

            # 3. Add Coins
            sell_price = 20 * amount
            await cursor.execute(
                "UPDATE game_profile SET coins = coins + ? WHERE user_uuid = ?",
                (sell_price, user_uuid),
            )

        await self.bot.db.commit()
        await interaction.followup.send(
            f"👋 You released **{amount}x {pokemon_name}**.\n💰 You received **{sell_price} Coins**."
        )

    @pokemon_group.command(name="potd", description="See the global Pokémon of the Day")
    async def potd(self, interaction: discord.Interaction):
        await interaction.response.defer()
        today = datetime.date.today().toordinal()
        rng = random.Random(today)
        potd_id = rng.randint(1, 1025)

        url = f"https://pokeapi.co/api/v2/pokemon/{potd_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()

                    description = "A mysterious Pokémon."
                    species_url = data["species"]["url"]
                    async with session.get(species_url) as species_res:
                        if species_res.status == 200:
                            s_data = await species_res.json()
                            for entry in s_data["flavor_text_entries"]:
                                if entry["language"]["name"] == "en":
                                    description = (
                                        entry["flavor_text"]
                                        .replace("\n", " ")
                                        .replace("\f", " ")
                                    )
                                    break

                    embed = discord.Embed(
                        title=f"📅 Pokémon of the Day: {data['name'].capitalize()}",
                        color=discord.Color.purple(),
                    )
                    embed.description = f"**Fun Fact:**\n*{description}*"
                    embed.set_image(url=data["sprites"]["front_default"])
                    embed.set_footer(text=f"ID: #{data['id']}")
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send("Failed to fetch.")

    @pokemon_group.command(name="givepulls", description="Admin: Give pulls")
    @app_commands.checks.has_permissions(administrator=True)
    async def give_pulls(
        self, interaction: discord.Interaction, member: discord.Member, amount: int
    ):
        user_uuid = await get_or_create_uuid(self.bot.db, member.id, member.name)

        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO game_profile (user_uuid, available_pulls, last_daily, coins)
                VALUES (?, ?, ?, 0)
                ON CONFLICT(user_uuid) DO UPDATE SET
                available_pulls = available_pulls + ?
            """,
                (user_uuid, amount, datetime.datetime.now().isoformat(), amount),
            )
        await self.bot.db.commit()
        await interaction.response.send_message(
            f"✅ Gave {amount} pulls to {member.name}.", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(PokemonGame(bot))
