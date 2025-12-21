import asyncio
import datetime
import random
from io import BytesIO

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image

from utils.database import get_or_create_uuid

# --- CONFIGURATION ---

# Complete list of Legendaries, Mythicals, and Ultra Beasts (Gen 1-9)
LEGENDARY_IDS = [
    # Gen 1
    144,
    145,
    146,
    150,
    151,
    # Gen 2
    243,
    244,
    245,
    249,
    250,
    251,
    # Gen 3
    377,
    378,
    379,
    380,
    381,
    382,
    383,
    384,
    385,
    386,
    # Gen 4
    480,
    481,
    482,
    483,
    484,
    485,
    486,
    487,
    488,
    490,
    491,
    492,
    493,
    # Gen 5
    494,
    638,
    639,
    640,
    641,
    642,
    643,
    644,
    645,
    646,
    647,
    648,
    649,
    # Gen 6
    716,
    717,
    718,
    719,
    720,
    721,
    # Gen 7
    772,
    773,
    785,
    786,
    787,
    788,
    789,
    790,
    791,
    792,
    800,
    801,
    802,
    807,
    793,
    794,
    795,
    796,
    797,
    798,
    799,
    803,
    804,
    805,
    806,
    # Gen 8
    888,
    889,
    890,
    891,
    892,
    894,
    895,
    896,
    897,
    898,
    # Gen 9
    1001,
    1002,
    1003,
    1004,
    1007,
    1008,
]

SHINY_CHANCE = 0.05  # 5% Chance
LEGENDARY_CHANCE = 0.02  # 2% Chance


# --- HELPER: Image Collage ---
def generate_collage(images_data):
    """
    images_data is a list of tuples: (bytes, is_shiny)
    """
    if not images_data:
        return None

    img_width, img_height = 96, 96
    columns = 3  # Skinnier grid for better phone viewing
    rows = (len(images_data) + columns - 1) // columns

    canvas_width = columns * img_width
    canvas_height = rows * img_height
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

    for i, (img_bytes, is_shiny) in enumerate(images_data):
        try:
            with Image.open(BytesIO(img_bytes)) as img:
                img = img.convert("RGBA")

                # Logic: Paste into grid
                x = (i % columns) * img_width
                y = (i // columns) * img_height

                canvas.paste(img, (x, y), img)
        except Exception as e:
            print(f"Error processing image {i}: {e}")

    output_buffer = BytesIO()
    canvas.save(output_buffer, format="PNG")
    output_buffer.seek(0)
    return output_buffer


# --- VIEW: Box Pagination (Browse Storage) ---
class BoxView(discord.ui.View):
    def __init__(self, full_data, user_name):
        super().__init__(timeout=60)
        self.full_data = full_data
        self.user_name = user_name
        self.page = 0
        self.items_per_page = 20
        self.total_pages = (
            len(full_data) + self.items_per_page - 1
        ) // self.items_per_page

    def get_embed(self):
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        page_data = self.full_data[start:end]

        desc = "Use these **IDs** to trade!\n\n"
        for row in page_data:
            unique_id, p_id, name, shiny, date = row

            icon = "✨" if shiny else ""
            is_legendary = p_id in LEGENDARY_IDS
            bold = "**" if is_legendary else ""

            desc += f"`ID: {unique_id}` — {bold}{name}{bold} {icon}\n"

        embed = discord.Embed(
            title=f"📦 {self.user_name}'s Box",
            description=desc,
            color=discord.Color.blue(),
        )
        embed.set_footer(
            text=f"Page {self.page + 1}/{self.total_pages} • Total: {len(self.full_data)}"
        )
        return embed

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def prev_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.page > 0:
            self.page -= 1
        else:
            self.page = self.total_pages - 1
        await interaction.response.edit_message(embed=self.get_embed())

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.page < self.total_pages - 1:
            self.page += 1
        else:
            self.page = 0
        await interaction.response.edit_message(embed=self.get_embed())


# --- VIEW: Trade Confirmation ---
class TradeView(discord.ui.View):
    def __init__(self, bot, author, partner, author_poke_id, partner_poke_id):
        super().__init__(timeout=60)
        self.bot = bot
        self.author = author
        self.partner = partner
        self.author_poke_id = author_poke_id
        self.partner_poke_id = partner_poke_id
        self.value = None

    @discord.ui.button(label="✅ Accept Trade", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.partner.id:
            await interaction.response.send_message(
                "❌ This trade request isn't for you!", ephemeral=True
            )
            return

        db = self.bot.db
        author_uuid = await get_or_create_uuid(db, self.author.id, self.author.name)
        partner_uuid = await get_or_create_uuid(db, self.partner.id, self.partner.name)

        async with db.cursor() as cursor:
            # Check ownership one last time
            await cursor.execute(
                "SELECT user_uuid FROM collection WHERE id = ?", (self.author_poke_id,)
            )
            check_a = await cursor.fetchone()
            await cursor.execute(
                "SELECT user_uuid FROM collection WHERE id = ?", (self.partner_poke_id,)
            )
            check_b = await cursor.fetchone()

            if not check_a or check_a[0] != author_uuid:
                await interaction.response.send_message(
                    "❌ Trade Failed: Original owner no longer has the Pokemon!",
                    ephemeral=True,
                )
                return
            if not check_b or check_b[0] != partner_uuid:
                await interaction.response.send_message(
                    "❌ Trade Failed: Partner no longer has the Pokemon!",
                    ephemeral=True,
                )
                return

            # EXECUTE SWAP
            await cursor.execute(
                "UPDATE collection SET user_uuid = ? WHERE id = ?",
                (partner_uuid, self.author_poke_id),
            )
            await cursor.execute(
                "UPDATE collection SET user_uuid = ? WHERE id = ?",
                (author_uuid, self.partner_poke_id),
            )

        await db.commit()

        self.value = True
        self.stop()
        await interaction.response.edit_message(
            content=f"🤝 **Trade Complete!**\n{self.author.mention} ↔ {self.partner.mention}\nCheck your boxes!",
            view=None,
            embed=None,
        )

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if (
            interaction.user.id != self.partner.id
            and interaction.user.id != self.author.id
        ):
            return

        self.value = False
        self.stop()
        await interaction.response.edit_message(
            content="❌ Trade Cancelled.", view=None, embed=None
        )


# --- VIEW: Pokedex Buttons ---
class PokedexView(discord.ui.View):
    def __init__(self, pokemon_list, user_name):
        super().__init__(timeout=60)
        self.pokemon_list = pokemon_list
        self.user_name = user_name
        self.index = 0

    def get_embed(self):
        poke_id, poke_name, count, shinies = self.pokemon_list[self.index]
        image_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{poke_id}.png"

        embed = discord.Embed(
            title=f"📖 Pokedex: {self.user_name}", color=discord.Color.red()
        )
        shiny_text = f" (✨ {shinies})" if shinies > 0 else ""
        embed.description = f"**#{poke_id} {poke_name}**"
        embed.add_field(name="Times Caught", value=f"{count}{shiny_text}", inline=True)
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
        # Pre-calculate safe non-legendary list
        self.NON_LEGENDARY_IDS = list(set(range(1, 1026)) - set(LEGENDARY_IDS))

    @commands.Cog.listener()
    async def on_ready(self):
        print("Pokemon Cog is ready.")

    pokemon_group = app_commands.Group(
        name="pokemon", description="Gacha Game Commands"
    )

    # --- CORE LOGIC: Fetch Pokemon ---
    async def fetch_pokemon(self, session):
        # 1. Roll for Rarity
        is_legendary = random.random() < LEGENDARY_CHANCE
        is_shiny = random.random() < SHINY_CHANCE

        # 2. Pick ID
        if is_legendary:
            poke_id = random.choice(LEGENDARY_IDS)
        else:
            poke_id = random.choice(self.NON_LEGENDARY_IDS)

        # 3. Fetch Data
        url = f"https://pokeapi.co/api/v2/pokemon/{poke_id}"
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()

                sprite_url = (
                    data["sprites"]["front_shiny"]
                    if is_shiny
                    else data["sprites"]["front_default"]
                )
                if not sprite_url:
                    sprite_url = data["sprites"]["front_default"]

                return {
                    "id": data["id"],
                    "name": data["name"].capitalize(),
                    "image_url": sprite_url,
                    "is_shiny": is_shiny,
                    "is_legendary": is_legendary,
                }
            return None

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

    # --- MAIN GAME: Pull ---
    @pokemon_group.command(name="pull", description="Use Poké Balls")
    @app_commands.describe(amount="How many to pull? (Optional, Default: 1, Max: 10)")
    async def pull(self, interaction: discord.Interaction, amount: int = 1):
        await interaction.response.defer()

        if amount > 10:
            await interaction.followup.send("❌ Max 10 pulls at a time!")
            return
        if amount < 1:
            await interaction.followup.send("❌ Amount must be at least 1.")
            return

        user_uuid = await get_or_create_uuid(
            self.bot.db, interaction.user.id, interaction.user.name
        )

        # 1. Check & Deduct Pulls
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT available_pulls FROM game_profile WHERE user_uuid = ?",
                (user_uuid,),
            )
            row = await cursor.fetchone()
            pulls = row[0] if row else 0

            if pulls < amount:
                await interaction.followup.send(
                    f"❌ Not enough pulls! You have {pulls}."
                )
                return

            await cursor.execute(
                "UPDATE game_profile SET available_pulls = available_pulls - ? WHERE user_uuid = ?",
                (amount, user_uuid),
            )
        await self.bot.db.commit()

        # 2. Fetch Pokemon
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_pokemon(session) for _ in range(amount)]
            results = await asyncio.gather(*tasks)

        caught = [p for p in results if p is not None]

        # 3. Save to Database (With Shiny Flag)
        async with self.bot.db.cursor() as cursor:
            for p in caught:
                await cursor.execute(
                    "INSERT INTO collection (user_uuid, pokemon_id, pokemon_name, is_shiny, is_legendary) VALUES (?, ?, ?, ?, ?)",
                    (user_uuid, p["id"], p["name"], p["is_shiny"], p["is_legendary"]),
                )
        await self.bot.db.commit()

        # 4. Display Results
        if amount == 1:
            p = caught[0]
            name_display = f"✨ {p['name']} ✨" if p["is_shiny"] else p["name"]
            color = (
                discord.Color.gold()
                if p["is_legendary"]
                else (
                    discord.Color.purple() if p["is_shiny"] else discord.Color.green()
                )
            )

            embed = discord.Embed(title=f"You caught {name_display}!", color=color)
            embed.set_image(url=p["image_url"])
            if p["is_legendary"]:
                embed.set_footer(text="🔥 LEGENDARY PULL!")
            if p["is_shiny"]:
                embed.set_footer(text="✨ SHINY PULL!")

            await interaction.followup.send(embed=embed)
        else:
            # Generate Text List
            desc = ""
            for p in caught:
                icon = "✨" if p["is_shiny"] else ""
                bold = "**" if p["is_legendary"] else ""
                desc += f"• {bold}{p['name']} {icon}{bold}\n"

            # Generate Image Collage
            image_data_list = []
            async with aiohttp.ClientSession() as session:
                for p in caught:
                    if p["image_url"]:
                        async with session.get(p["image_url"]) as resp:
                            if resp.status == 200:
                                image_data_list.append(
                                    (await resp.read(), p["is_shiny"])
                                )

            collage = await asyncio.to_thread(generate_collage, image_data_list)
            file = discord.File(collage, filename="pulls.png") if collage else None

            embed = discord.Embed(
                title=f"🔥 Pull Results", description=desc, color=discord.Color.gold()
            )
            if file:
                embed.set_image(url="attachment://pulls.png")
                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send(embed=embed)

    # --- POKEDEX & BOX ---
    @pokemon_group.command(name="pokedex", description="View your collection summary")
    async def pokedex(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_uuid = await get_or_create_uuid(
            self.bot.db, interaction.user.id, interaction.user.name
        )

        async with self.bot.db.cursor() as cursor:
            # FIX: Added (user_uuid,) tuple
            await cursor.execute(
                """
                SELECT pokemon_id, pokemon_name, count(*) as count, sum(is_shiny) as shinies
                FROM collection
                WHERE user_uuid = ?
                GROUP BY pokemon_id
                ORDER BY pokemon_id ASC
            """,
                (user_uuid,),
            )
            rows = await cursor.fetchall()

        if not rows:
            await interaction.followup.send("Empty collection!")
            return

        view = PokedexView(rows, interaction.user.name)
        await interaction.followup.send(embed=view.get_embed(), view=view)

    @pokemon_group.command(name="box", description="Manage your Pokémon Storage")
    async def box(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_uuid = await get_or_create_uuid(
            self.bot.db, interaction.user.id, interaction.user.name
        )

        async with self.bot.db.cursor() as cursor:
            # Fetch ALL pokemon, ordered by newest first
            # FIX: Added (user_uuid,) tuple
            await cursor.execute(
                """
                SELECT id, pokemon_id, pokemon_name, is_shiny, caught_at
                FROM collection
                WHERE user_uuid = ?
                ORDER BY id DESC
            """,
                (user_uuid,),
            )
            rows = await cursor.fetchall()

        if not rows:
            await interaction.followup.send("Your box is empty! Go catch some Pokémon.")
            return

        view = BoxView(rows, interaction.user.name)
        await interaction.followup.send(embed=view.get_embed(), view=view)

    # --- TRADING SYSTEM ---
    @pokemon_group.command(name="trade", description="Trade Pokemon with a friend")
    @app_commands.describe(
        partner="Who to trade with",
        your_id="ID of YOUR Pokemon",
        their_id="ID of THEIR Pokemon",
    )
    async def trade(
        self,
        interaction: discord.Interaction,
        partner: discord.Member,
        your_id: int,
        their_id: int,
    ):
        if partner.bot or partner.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ You cannot trade with bots or yourself!", ephemeral=True
            )
            return

        await interaction.response.defer()
        db = self.bot.db

        # 1. Verify Ownership
        author_uuid = await get_or_create_uuid(
            db, interaction.user.id, interaction.user.name
        )
        partner_uuid = await get_or_create_uuid(db, partner.id, partner.name)

        async with db.cursor() as cursor:
            # Check Your Pokemon
            await cursor.execute(
                "SELECT pokemon_name, is_shiny FROM collection WHERE id = ? AND user_uuid = ?",
                (your_id, author_uuid),
            )
            your_poke = await cursor.fetchone()

            # Check Their Pokemon
            await cursor.execute(
                "SELECT pokemon_name, is_shiny FROM collection WHERE id = ? AND user_uuid = ?",
                (their_id, partner_uuid),
            )
            their_poke = await cursor.fetchone()

        # 2. Validation Checks
        if not your_poke:
            await interaction.followup.send(
                f"❌ You don't own a Pokémon with ID `{your_id}`!"
            )
            return
        if not their_poke:
            await interaction.followup.send(
                f"❌ {partner.name} doesn't own a Pokémon with ID `{their_id}`!"
            )
            return

        # 3. Construct the Offer
        y_name = f"{your_poke[0]} {'✨' if your_poke[1] else ''}"
        t_name = f"{their_poke[0]} {'✨' if their_poke[1] else ''}"

        embed = discord.Embed(
            title="🤝 Trade Offer",
            description=f"{interaction.user.mention} wants to trade with {partner.mention}!",
            color=discord.Color.gold(),
        )
        embed.add_field(
            name=f"{interaction.user.name} Offers",
            value=f"**{y_name}**\n(ID: {your_id})",
            inline=True,
        )
        embed.add_field(
            name=f"{partner.name} Offers",
            value=f"**{t_name}**\n(ID: {their_id})",
            inline=True,
        )
        embed.set_footer(text="Waiting for partner to accept...")

        view = TradeView(self.bot, interaction.user, partner, your_id, their_id)
        await interaction.followup.send(content=partner.mention, embed=embed, view=view)

    @pokemon_group.command(name="release", description="Sell Pokémon for 20 Coins each")
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
            # Check ownership
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

            # Delete
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

            # Add Coins
            sell_price = 20 * amount
            await cursor.execute(
                "UPDATE game_profile SET coins = coins + ? WHERE user_uuid = ?",
                (sell_price, user_uuid),
            )

        await self.bot.db.commit()
        await interaction.followup.send(
            f"👋 You released **{amount}x {pokemon_name}**.\n💰 You received **{sell_price} Coins**."
        )

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

    # --- 🚨 DATABASE REPAIR COMMAND (RUN THIS ONCE) 🚨 ---
    @pokemon_group.command(
        name="repair_db", description="ADMIN: Fix missing database columns"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def repair_db(self, interaction: discord.Interaction):
        await interaction.response.defer()
        db = self.bot.db
        results = []
        async with db.cursor() as cursor:
            try:
                await cursor.execute(
                    "ALTER TABLE collection ADD COLUMN is_shiny BOOLEAN DEFAULT 0"
                )
                results.append("✅ Success: Added 'is_shiny' column.")
            except Exception as e:
                results.append(f"ℹ️ Status shiny: {e}")

            try:
                await cursor.execute(
                    "ALTER TABLE collection ADD COLUMN is_legendary BOOLEAN DEFAULT 0"
                )
                results.append("✅ Success: Added 'is_legendary' column.")
            except Exception as e:
                results.append(f"ℹ️ Status legendary: {e}")
        await db.commit()
        await interaction.followup.send(
            f"**Database Repair Report:**\n" + "\n".join(results)
        )


async def setup(bot):
    await bot.add_cog(PokemonGame(bot))
