import asyncio
import datetime
import random
from io import BytesIO

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from utils.database import get_or_create_uuid

# --- CONFIGURATION ---

# Complete list of Legendaries (Gen 1-9)
LEGENDARY_IDS = [
    144,
    145,
    146,
    150,
    151,
    243,
    244,
    245,
    249,
    250,
    251,
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
    716,
    717,
    718,
    719,
    720,
    721,
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
    1001,
    1002,
    1003,
    1004,
    1007,
    1008,
]

SHINY_CHANCE = 0.05
LEGENDARY_CHANCE = 0.02
EVOLUTION_COST = 3  # You need 3 duplicates to evolve 1


# --- HELPER: Image Collage ---
# --- HELPER: Image Collage (HD + Transparent) ---
def generate_collage(images_data, counts=None, names=None):
    if not images_data:
        return None

    # 1. MASSIVE SCALING (3x)
    # This makes the image huge so Discord's preview looks sharp.
    scale = 3
    sprite_size = 96 * scale  # 288px
    text_height = 40 * scale  # Space for text
    cell_w = 120 * scale  # 360px wide
    cell_h = sprite_size + text_height

    columns = 5
    rows = (len(images_data) + columns - 1) // columns

    # 2. TRANSPARENT BACKGROUND
    # (0, 0, 0, 0) = Fully Transparent
    canvas = Image.new("RGBA", (columns * cell_w, rows * cell_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # 3. LOAD A HUGE FONT
    # We need a size around 40-50px for this resolution
    font = None
    try:
        # Linux / VPS standard
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 45
        )
    except:
        try:
            # Windows standard
            font = ImageFont.truetype("arial.ttf", 45)
        except:
            pass  # Fallback to default (will look tiny, but code won't crash)

    # If font failed to load, we use default but it will be small.
    # We print a warning to your console so you know.
    if not font:
        print("⚠️ WARNING: Could not load a custom font. Text will be tiny.")
        font = ImageFont.load_default()

    for i, (img_bytes, is_shiny) in enumerate(images_data):
        try:
            with Image.open(BytesIO(img_bytes)) as img:
                img = img.convert("RGBA")

                # Resize sprite with NEAREST NEIGHBOR (keeps pixel art crisp)
                img = img.resize((sprite_size, sprite_size), resample=Image.NEAREST)

                # Math for grid position
                col = i % columns
                row = i // columns
                x_base = col * cell_w
                y_base = row * cell_h

                # Center sprite
                sprite_x = x_base + (cell_w - sprite_size) // 2
                canvas.paste(img, (sprite_x, y_base), img)

                # --- DRAW NAME ---
                if names and i < len(names):
                    name_text = names[i][:13]  # Limit to 13 chars

                    # Calculate text width
                    try:
                        bbox = draw.textbbox((0, 0), name_text, font=font)
                        text_w = bbox[2] - bbox[0]
                    except:
                        text_w = draw.textlength(name_text, font=font)

                    text_x = x_base + (cell_w - text_w) // 2
                    text_y = (
                        y_base + sprite_size - (10 * scale)
                    )  # Tuck it just under the feet

                    # THICK BLACK OUTLINE (Stroke)
                    # This is crucial for transparent backgrounds!
                    stroke = 4 * scale  # Very thick stroke
                    draw.text(
                        (text_x, text_y),
                        name_text,
                        font=font,
                        fill="white",
                        stroke_width=stroke,
                        stroke_fill="black",
                    )

                # --- DRAW COUNT (x3) ---
                if counts and i < len(counts) and counts[i] > 1:
                    count_text = f"x{counts[i]}"
                    # Top Right Corner
                    cx = x_base + cell_w - (30 * scale)
                    cy = y_base + (10 * scale)

                    # Green text, black border
                    draw.text(
                        (cx, cy),
                        count_text,
                        font=font,
                        fill="#00ff00",
                        stroke_width=stroke,
                        stroke_fill="black",
                    )

        except Exception as e:
            print(f"Image error: {e}")

    output_buffer = BytesIO()
    canvas.save(output_buffer, format="PNG")
    output_buffer.seek(0)
    return output_buffer


# --- VIEW: Box Pagination ---
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

        desc = "Use the **ID** to rename, buddy, or trade!\n\n"
        for row in page_data:
            unique_id, p_id, name, shiny, nickname = row
            display_name = f"**{nickname}** ({name})" if nickname else f"**{name}**"
            icon = "✨" if shiny else ""
            if p_id in LEGENDARY_IDS:
                display_name = f"🔥 {display_name} 🔥"
            desc += f"`ID: {unique_id}` — {display_name} {icon}\n"

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
        self.page = self.page - 1 if self.page > 0 else self.total_pages - 1
        await interaction.response.edit_message(embed=self.get_embed())

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page = self.page + 1 if self.page < self.total_pages - 1 else 0
        await interaction.response.edit_message(embed=self.get_embed())


# --- VIEW: Visual Pokedex ---
class PokedexView(discord.ui.View):
    def __init__(self, full_data, user_name):
        super().__init__(timeout=60)
        self.full_data = full_data
        self.user_name = user_name
        self.page = 0
        self.items_per_page = 20  # 5x4 Grid

    async def generate_page_image(self):
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        page_data = self.full_data[start:end]

        image_tasks = []
        counts = []
        names = []  # <--- New List

        async with aiohttp.ClientSession() as session:
            for row in page_data:
                # Row format: (id, name, count, shinies)
                poke_id, poke_name, count, shinies = row

                counts.append(count)
                names.append(poke_name)  # <--- Save Name

                # Show Shiny sprite if they have ANY shinies of this species
                is_shiny_display = shinies > 0
                url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{'shiny/' if is_shiny_display else ''}{poke_id}.png"
                image_tasks.append(session.get(url))

            responses = await asyncio.gather(*image_tasks)
            image_bytes = [await r.read() for r in responses if r.status == 200]

            collage_data = [(b, False) for b in image_bytes]

        # Pass names to the helper
        return await asyncio.to_thread(generate_collage, collage_data, counts, names)

    async def update_message(self, interaction):
        await interaction.response.defer()
        img_buffer = await self.generate_page_image()

        if not img_buffer:
            await interaction.followup.send("Error generating image.", ephemeral=True)
            return

        file = discord.File(img_buffer, filename="pokedex.png")
        embed = discord.Embed(
            title=f"📖 Pokedex: {self.user_name}", color=discord.Color.red()
        )
        embed.set_image(url="attachment://pokedex.png")
        embed.set_footer(
            text=f"Page {self.page + 1} • Total Unique: {len(self.full_data)}"
        )

        await interaction.edit_original_response(
            embed=embed, attachments=[file], view=self
        )

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def prev_btn(self, interaction, button):
        total_pages = (
            len(self.full_data) + self.items_per_page - 1
        ) // self.items_per_page
        self.page = self.page - 1 if self.page > 0 else total_pages - 1
        await self.update_message(interaction)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction, button):
        total_pages = (
            len(self.full_data) + self.items_per_page - 1
        ) // self.items_per_page
        self.page = self.page + 1 if self.page < total_pages - 1 else 0
        await self.update_message(interaction)


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
            await cursor.execute(
                "SELECT user_uuid FROM collection WHERE id = ?", (self.author_poke_id,)
            )
            check_a = await cursor.fetchone()
            await cursor.execute(
                "SELECT user_uuid FROM collection WHERE id = ?", (self.partner_poke_id,)
            )
            check_b = await cursor.fetchone()

            if (
                not check_a
                or check_a[0] != author_uuid
                or not check_b
                or check_b[0] != partner_uuid
            ):
                await interaction.response.send_message(
                    "❌ Trade Failed: Ownership changed!", ephemeral=True
                )
                return

            # Clear Buddy status before trading
            await cursor.execute(
                "UPDATE game_profile SET buddy_id = NULL WHERE buddy_id = ?",
                (self.author_poke_id,),
            )
            await cursor.execute(
                "UPDATE game_profile SET buddy_id = NULL WHERE buddy_id = ?",
                (self.partner_poke_id,),
            )

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
            content=f"🤝 **Trade Complete!**\n{self.author.mention} ↔ {self.partner.mention}",
            view=None,
            embed=None,
        )

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.partner.id, self.author.id]:
            return
        self.value = False
        self.stop()
        await interaction.response.edit_message(
            content="❌ Trade Cancelled.", view=None, embed=None
        )


# --- MAIN COG ---
class PokemonGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.NON_LEGENDARY_IDS = list(set(range(1, 1026)) - set(LEGENDARY_IDS))

    @commands.Cog.listener()
    async def on_ready(self):
        print("Pokemon Cog is ready.")

    pokemon_group = app_commands.Group(
        name="pokemon", description="Gacha Game Commands"
    )

    # --- CORE LOGIC: Fetch Pokemon ---
    async def fetch_pokemon(self, session):
        is_legendary = random.random() < LEGENDARY_CHANCE
        is_shiny = random.random() < SHINY_CHANCE
        poke_id = (
            random.choice(LEGENDARY_IDS)
            if is_legendary
            else random.choice(self.NON_LEGENDARY_IDS)
        )

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

    # --- EVOLUTION LOGIC ---
    async def get_next_evolution(self, session, pokemon_id):
        # 1. Get Species Data
        url = f"https://pokeapi.co/api/v2/pokemon-species/{pokemon_id}"
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            species_data = await resp.json()

        # 2. Get Chain URL
        chain_url = species_data["evolution_chain"]["url"]
        async with session.get(chain_url) as resp:
            if resp.status != 200:
                return None
            chain_data = await resp.json()

        chain = chain_data["chain"]

        # 3. Recursive search to find current Pokemon in the tree
        def find_node(node, target_id):
            # Extract ID from URL (e.g., https://.../1/)
            node_id = int(node["species"]["url"].split("/")[-2])
            if node_id == target_id:
                return node
            for child in node["evolves_to"]:
                res = find_node(child, target_id)
                if res:
                    return res
            return None

        current_node = find_node(chain, pokemon_id)

        # 4. Check if it evolves
        if not current_node or not current_node["evolves_to"]:
            return None  # Final evolution already

        # 5. Pick evolution (Random for branching like Eevee)
        next_node = random.choice(current_node["evolves_to"])
        next_id = int(next_node["species"]["url"].split("/")[-2])
        next_name = next_node["species"]["name"].capitalize()

        return next_id, next_name

    # --- COMMANDS ---

    @pokemon_group.command(
        name="evolve", description="Merge 3 duplicates to get the next evolution!"
    )
    @app_commands.describe(name="Name of the Pokemon (e.g. Charmander)")
    async def evolve(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        pokemon_name = name.capitalize()
        user_uuid = await get_or_create_uuid(
            self.bot.db, interaction.user.id, interaction.user.name
        )

        async with self.bot.db.cursor() as cursor:
            # 1. Check if user has enough duplicates (Need 3)
            # We sort by is_shiny ASC so we sacrifice Normal ones before Shiny ones!
            await cursor.execute(
                """
                SELECT id, pokemon_id, is_shiny, is_legendary
                FROM collection
                WHERE user_uuid = ? AND pokemon_name = ?
                ORDER BY is_shiny ASC
                LIMIT ?
            """,
                (user_uuid, pokemon_name, EVOLUTION_COST),
            )

            duplicates = await cursor.fetchall()

            if len(duplicates) < EVOLUTION_COST:
                await interaction.followup.send(
                    f"❌ You need **{EVOLUTION_COST}** {pokemon_name} to evolve, but you only have **{len(duplicates)}**."
                )
                return

            current_poke_id = duplicates[0][1]

            # 2. Fetch Evolution Data (API)
            async with aiohttp.ClientSession() as session:
                evo_result = await self.get_next_evolution(session, current_poke_id)

            if not evo_result:
                await interaction.followup.send(
                    f"❌ **{pokemon_name}** cannot evolve any further!"
                )
                return

            next_id, next_name = evo_result

            # 3. EXECUTE EVOLUTION
            # Delete the 3 duplicates
            ids_to_delete = [d[0] for d in duplicates]
            placeholders = ",".join("?" * len(ids_to_delete))

            await cursor.execute(
                f"DELETE FROM collection WHERE id IN ({placeholders})",
                tuple(ids_to_delete),
            )

            # Determine Stats of new Pokemon (Inherit Shiny/Legendary if lucky?)
            # Logic: If you sacrifice a Shiny, the evolution is Shiny.
            # (Since we ordered by ASC, if the last one is Shiny, it means we used a shiny)
            is_shiny_evo = any(d[2] for d in duplicates)
            is_legendary_evo = any(d[3] for d in duplicates)

            # Insert the New Pokemon
            await cursor.execute(
                """
                INSERT INTO collection (user_uuid, pokemon_id, pokemon_name, is_shiny, is_legendary)
                VALUES (?, ?, ?, ?, ?)
            """,
                (user_uuid, next_id, next_name, is_shiny_evo, is_legendary_evo),
            )

        await self.bot.db.commit()

        # Fetch Image for cool embed
        img_url = ""
        async with aiohttp.ClientSession() as session:
            url = f"https://pokeapi.co/api/v2/pokemon/{next_id}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    d = await resp.json()
                    img_url = (
                        d["sprites"]["front_shiny"]
                        if is_shiny_evo
                        else d["sprites"]["front_default"]
                    )

        embed = discord.Embed(
            title="🧬 Evolution Successful!", color=discord.Color.teal()
        )
        embed.description = (
            f"Your **3x {pokemon_name}** merged into **1x {next_name}**!"
        )
        if is_shiny_evo:
            embed.description += "\n✨ **It's Shiny!**"
        if img_url:
            embed.set_thumbnail(url=img_url)

        await interaction.followup.send(embed=embed)

    @pokemon_group.command(name="rename", description="Give your Pokemon a nickname")
    @app_commands.describe(id="The ID from /pokemon box", name="The new nickname")
    async def rename(self, interaction: discord.Interaction, id: int, name: str):
        await interaction.response.defer()
        if len(name) > 30:
            await interaction.followup.send("❌ Nickname too long! Max 30 chars.")
            return
        user_uuid = await get_or_create_uuid(
            self.bot.db, interaction.user.id, interaction.user.name
        )
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT pokemon_name FROM collection WHERE id = ? AND user_uuid = ?",
                (id, user_uuid),
            )
            result = await cursor.fetchone()
            if not result:
                await interaction.followup.send(f"❌ You don't own Pokemon ID `{id}`.")
                return
            await cursor.execute(
                "UPDATE collection SET nickname = ? WHERE id = ?", (name, id)
            )
        await self.bot.db.commit()
        await interaction.followup.send(f"✅ ID `{id}` is now **{name}**!")

    @pokemon_group.command(
        name="pokedex", description="View your collection (Visual Grid)"
    )
    async def pokedex(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_uuid = await get_or_create_uuid(
            self.bot.db, interaction.user.id, interaction.user.name
        )

        async with self.bot.db.cursor() as cursor:
            # Group by Pokemon ID
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

        # Initialize View and Send First Image
        view = PokedexView(rows, interaction.user.name)
        img_buffer = await view.generate_page_image()
        file = discord.File(img_buffer, filename="pokedex.png")

        embed = discord.Embed(
            title=f"📖 Pokedex: {interaction.user.name}", color=discord.Color.red()
        )
        embed.set_image(url="attachment://pokedex.png")
        embed.set_footer(text=f"Page 1 • Total Unique: {len(rows)}")

        await interaction.followup.send(embed=embed, file=file, view=view)

    @pokemon_group.command(name="buddy", description="Set your Partner Pokemon")
    @app_commands.describe(id="The ID from /pokemon box")
    async def buddy(self, interaction: discord.Interaction, id: int):
        await interaction.response.defer()
        user_uuid = await get_or_create_uuid(
            self.bot.db, interaction.user.id, interaction.user.name
        )
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT pokemon_name FROM collection WHERE id = ? AND user_uuid = ?",
                (id, user_uuid),
            )
            if not await cursor.fetchone():
                await interaction.followup.send(f"❌ You don't own Pokemon ID `{id}`.")
                return
            await cursor.execute(
                "INSERT OR IGNORE INTO game_profile (user_uuid) VALUES (?)",
                (user_uuid,),
            )
            await cursor.execute(
                "UPDATE game_profile SET buddy_id = ? WHERE user_uuid = ?",
                (id, user_uuid),
            )
        await self.bot.db.commit()
        await interaction.followup.send(f"❤️ Buddy Updated!")

    @pokemon_group.command(name="profile", description="View your Trainer Card")
    async def profile(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_uuid = await get_or_create_uuid(
            self.bot.db, interaction.user.id, interaction.user.name
        )
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT coins, available_pulls, buddy_id FROM game_profile WHERE user_uuid = ?",
                (user_uuid,),
            )
            data = await cursor.fetchone()
            if not data:
                await interaction.followup.send("Start playing first!")
                return
            coins, pulls, buddy_id = data

            buddy_img, buddy_name = None, "None"
            if buddy_id:
                await cursor.execute(
                    "SELECT pokemon_id, pokemon_name, nickname, is_shiny FROM collection WHERE id = ?",
                    (buddy_id,),
                )
                bd = await cursor.fetchone()
                if bd:
                    buddy_name = bd[2] if bd[2] else bd[1]
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"https://pokeapi.co/api/v2/pokemon/{bd[0]}"
                        ) as r:
                            if r.status == 200:
                                d = await r.json()
                                buddy_img = (
                                    d["sprites"]["front_shiny"]
                                    if bd[3]
                                    else d["sprites"]["front_default"]
                                )

        embed = discord.Embed(
            title=f"🆔 Trainer: {interaction.user.name}", color=discord.Color.gold()
        )
        embed.add_field(name="💰 Coins", value=f"{coins}", inline=True)
        embed.add_field(name="📦 Pulls", value=f"{pulls}", inline=True)
        embed.add_field(name="❤️ Buddy", value=f"{buddy_name}", inline=True)
        if buddy_img:
            embed.set_thumbnail(url=buddy_img)
        else:
            embed.set_thumbnail(
                url=interaction.user.avatar.url if interaction.user.avatar else None
            )
        await interaction.followup.send(embed=embed)

    @pokemon_group.command(name="box", description="Manage your Pokémon Storage")
    async def box(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_uuid = await get_or_create_uuid(
            self.bot.db, interaction.user.id, interaction.user.name
        )
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT id, pokemon_id, pokemon_name, is_shiny, nickname FROM collection WHERE user_uuid = ? ORDER BY id DESC",
                (user_uuid,),
            )
            rows = await cursor.fetchall()
        if not rows:
            await interaction.followup.send("Box empty!")
            return
        view = BoxView(rows, interaction.user.name)
        await interaction.followup.send(embed=view.get_embed(), view=view)

    @pokemon_group.command(name="trade", description="Trade Pokemon with a friend")
    async def trade(
        self,
        interaction: discord.Interaction,
        partner: discord.Member,
        your_id: int,
        their_id: int,
    ):
        if partner.bot or partner.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ Invalid partner.", ephemeral=True
            )
            return
        await interaction.response.defer()
        db = self.bot.db
        author_uuid = await get_or_create_uuid(
            db, interaction.user.id, interaction.user.name
        )
        partner_uuid = await get_or_create_uuid(db, partner.id, partner.name)
        async with db.cursor() as cursor:
            await cursor.execute(
                "SELECT pokemon_name, is_shiny, nickname FROM collection WHERE id = ? AND user_uuid = ?",
                (your_id, author_uuid),
            )
            y = await cursor.fetchone()
            await cursor.execute(
                "SELECT pokemon_name, is_shiny, nickname FROM collection WHERE id = ? AND user_uuid = ?",
                (their_id, partner_uuid),
            )
            t = await cursor.fetchone()
        if not y or not t:
            await interaction.followup.send("❌ Invalid ownership.")
            return

        y_n = y[2] if y[2] else y[0]
        t_n = t[2] if t[2] else t[0]
        embed = discord.Embed(
            title="🤝 Trade Offer",
            description=f"{interaction.user.mention} wants to trade with {partner.mention}!",
            color=discord.Color.gold(),
        )
        embed.add_field(
            name=f"{interaction.user.name}",
            value=f"**{y_n}**\n(ID: {your_id})",
            inline=True,
        )
        embed.add_field(
            name=f"{partner.name}", value=f"**{t_n}**\n(ID: {their_id})", inline=True
        )
        view = TradeView(self.bot, interaction.user, partner, your_id, their_id)
        await interaction.followup.send(content=partner.mention, embed=embed, view=view)

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
                """INSERT INTO game_profile (user_uuid, available_pulls, last_daily, coins) VALUES (?, 5, ?, 0) ON CONFLICT(user_uuid) DO UPDATE SET available_pulls = available_pulls + 5, last_daily = ?""",
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
        embed = discord.Embed(title="🛒 Pokémon Shop", color=discord.Color.gold())
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
            remaining_pulls = pulls - amount
            await cursor.execute(
                "UPDATE game_profile SET available_pulls = available_pulls - ? WHERE user_uuid = ?",
                (amount, user_uuid),
            )
        await self.bot.db.commit()
        # Fetching pokemon
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_pokemon(session) for _ in range(amount)]
            results = await asyncio.gather(*tasks)
        caught = [p for p in results if p is not None]

        # Saving to the database
        async with self.bot.db.cursor() as cursor:
            for p in caught:
                await cursor.execute(
                    "INSERT INTO collection (user_uuid, pokemon_id, pokemon_name, is_shiny, is_legendary) VALUES (?, ?, ?, ?, ?)",
                    (user_uuid, p["id"], p["name"], p["is_shiny"], p["is_legendary"]),
                )
        await self.bot.db.commit()

        # Displaying the results aka caught pokemon
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
            footer_text = f" Remaining Pulls: {remaining_pulls}"
            if p["is_legendary"]:
                embed.set_footer(text=footer_text + " 🔥 LEGENDARY PULL!")
            if p["is_shiny"]:
                embed.set_footer(text=footer_text + " ✨ SHINY PULL!")
            await interaction.followup.send(embed=embed)
        else:
            desc = ""
            for p in caught:
                icon = "✨" if p["is_shiny"] else ""
                bold = "**" if p["is_legendary"] else ""
                desc += f"• {bold}{p['name']} {icon}{bold}\n"
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
            embed.set_footer(text=f"Remaining Pulls: {remaining_pulls}")
            if file:
                embed.set_image(url="attachment://pulls.png")
                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send(embed=embed)

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
            await cursor.execute(
                "SELECT count(*) FROM collection WHERE user_uuid = ? AND pokemon_name = ?",
                (user_uuid, pokemon_name),
            )
            count_row = await cursor.fetchone()
            owned_count = count_row[0] if count_row else 0
            if owned_count < amount:
                await interaction.followup.send(
                    f"❌ You only have **{owned_count}** {pokemon_name}(s)."
                )
                return
            await cursor.execute(
                "DELETE FROM collection WHERE id IN (SELECT id FROM collection WHERE user_uuid = ? AND pokemon_name = ? LIMIT ?)",
                (user_uuid, pokemon_name, amount),
            )
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
                """INSERT INTO game_profile (user_uuid, available_pulls, last_daily, coins) VALUES (?, ?, ?, 0) ON CONFLICT(user_uuid) DO UPDATE SET available_pulls = available_pulls + ?""",
                (user_uuid, amount, datetime.datetime.now().isoformat(), amount),
            )
        await self.bot.db.commit()
        await interaction.response.send_message(
            f"✅ Gave {amount} pulls to {member.name}.", ephemeral=True
        )

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
                results.append("✅ Added 'is_shiny'")
            except Exception as e:
                results.append(f"ℹ️ Shiny: {e}")
            try:
                await cursor.execute(
                    "ALTER TABLE collection ADD COLUMN is_legendary BOOLEAN DEFAULT 0"
                )
                results.append("✅ Added 'is_legendary'")
            except Exception as e:
                results.append(f"ℹ️ Legendary: {e}")
            try:
                await cursor.execute(
                    "ALTER TABLE collection ADD COLUMN nickname TEXT DEFAULT NULL"
                )
                results.append("✅ Added 'nickname'")
            except Exception as e:
                results.append(f"ℹ️ Nickname: {e}")
            try:
                await cursor.execute(
                    "ALTER TABLE game_profile ADD COLUMN buddy_id INTEGER DEFAULT NULL"
                )
                results.append("✅ Added 'buddy_id'")
            except Exception as e:
                results.append(f"ℹ️ Buddy: {e}")
        await db.commit()
        await interaction.followup.send(
            f"**Database Repair Report:**\n" + "\n".join(results)
        )


async def setup(bot):
    await bot.add_cog(PokemonGame(bot))
