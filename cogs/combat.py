import asyncio
import random

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from utils.database import get_or_create_uuid

# --- 1. TYPE CHART (Simplified) ---
# Multipliers for damage calculations
TYPE_CHART = {
    "normal": {"rock": 0.5, "ghost": 0.0, "steel": 0.5},
    "fire": {
        "fire": 0.5,
        "water": 0.5,
        "grass": 2.0,
        "ice": 2.0,
        "bug": 2.0,
        "rock": 0.5,
        "dragon": 0.5,
        "steel": 2.0,
    },
    "water": {
        "fire": 2.0,
        "water": 0.5,
        "grass": 0.5,
        "ground": 2.0,
        "rock": 2.0,
        "dragon": 0.5,
    },
    "grass": {
        "fire": 0.5,
        "water": 2.0,
        "grass": 0.5,
        "poison": 0.5,
        "ground": 2.0,
        "flying": 0.5,
        "bug": 0.5,
        "rock": 2.0,
        "dragon": 0.5,
        "steel": 0.5,
    },
    "electric": {
        "water": 2.0,
        "grass": 0.5,
        "electric": 0.5,
        "ground": 0.0,
        "flying": 2.0,
        "dragon": 0.5,
    },
    "ice": {
        "fire": 0.5,
        "water": 0.5,
        "grass": 2.0,
        "ice": 0.5,
        "ground": 2.0,
        "flying": 2.0,
        "dragon": 2.0,
        "steel": 0.5,
    },
    "fighting": {
        "normal": 2.0,
        "ice": 2.0,
        "poison": 0.5,
        "flying": 0.5,
        "psychic": 0.5,
        "bug": 0.5,
        "rock": 2.0,
        "ghost": 0.0,
        "dark": 2.0,
        "steel": 2.0,
        "fairy": 0.5,
    },
    "poison": {
        "grass": 2.0,
        "poison": 0.5,
        "ground": 0.5,
        "rock": 0.5,
        "ghost": 0.5,
        "steel": 0.0,
        "fairy": 2.0,
    },
    "ground": {
        "fire": 2.0,
        "water": 0.5,
        "grass": 0.5,
        "ice": 0.5,
        "poison": 2.0,
        "flying": 0.0,
        "electric": 2.0,
        "rock": 2.0,
        "steel": 2.0,
    },
    "flying": {
        "grass": 2.0,
        "electric": 0.5,
        "fighting": 2.0,
        "bug": 2.0,
        "rock": 0.5,
        "steel": 0.5,
    },
    "psychic": {
        "fighting": 2.0,
        "poison": 2.0,
        "psychic": 0.5,
        "dark": 0.0,
        "steel": 0.5,
    },
    "bug": {
        "fire": 0.5,
        "grass": 2.0,
        "fighting": 0.5,
        "poison": 0.5,
        "flying": 0.5,
        "psychic": 2.0,
        "ghost": 0.5,
        "dark": 2.0,
        "steel": 0.5,
        "fairy": 0.5,
    },
    "rock": {
        "fire": 2.0,
        "ice": 2.0,
        "fighting": 0.5,
        "ground": 0.5,
        "flying": 2.0,
        "bug": 2.0,
        "steel": 0.5,
    },
    "ghost": {"normal": 0.0, "psychic": 2.0, "ghost": 2.0, "dark": 0.5},
    "dragon": {"dragon": 2.0, "steel": 0.5, "fairy": 0.0},
    "dark": {"fighting": 0.5, "psychic": 2.0, "ghost": 2.0, "dark": 0.5, "fairy": 0.5},
    "steel": {
        "fire": 0.5,
        "water": 0.5,
        "electric": 0.5,
        "ice": 2.0,
        "rock": 2.0,
        "steel": 0.5,
        "fairy": 2.0,
    },
    "fairy": {
        "fire": 0.5,
        "fighting": 2.0,
        "poison": 0.5,
        "dragon": 2.0,
        "dark": 2.0,
        "steel": 0.5,
    },
}

# --- 2. MOVES POOL (Auto-Assigned based on Type) ---
MOVES_DB = {
    "normal": [("Tackle", 40), ("Quick Attack", 40), ("Hyper Beam", 120), ("Rest", 0)],
    "fire": [
        ("Ember", 40),
        ("Flamethrower", 90),
        ("Fire Blast", 110),
        ("Will-O-Wisp", 0),
    ],
    "water": [("Water Gun", 40), ("Surf", 90), ("Hydro Pump", 110), ("Rain Dance", 0)],
    "grass": [
        ("Vine Whip", 45),
        ("Razor Leaf", 55),
        ("Solar Beam", 120),
        ("Synthesis", 0),
    ],
    "electric": [
        ("Thundershock", 40),
        ("Thunderbolt", 90),
        ("Thunder", 110),
        ("Thunder Wave", 0),
    ],
    "ice": [("Ice Shard", 40), ("Ice Beam", 90), ("Blizzard", 110), ("Hail", 0)],
    "fighting": [
        ("Karate Chop", 50),
        ("Brick Break", 75),
        ("Close Combat", 120),
        ("Bulk Up", 0),
    ],
    "poison": [("Acid", 40), ("Sludge Bomb", 90), ("Gunk Shot", 120), ("Toxic", 0)],
    "ground": [
        ("Mud Shot", 55),
        ("Earthquake", 100),
        ("Fissure", 120),
        ("Sandstorm", 0),
    ],
    "flying": [("Peck", 35), ("Aerial Ace", 60), ("Brave Bird", 120), ("Roost", 0)],
    "psychic": [
        ("Confusion", 50),
        ("Psychic", 90),
        ("Future Sight", 120),
        ("Calm Mind", 0),
    ],
    "bug": [
        ("Bug Bite", 60),
        ("X-Scissor", 80),
        ("Megahorn", 120),
        ("Quiver Dance", 0),
    ],
    "rock": [
        ("Rock Throw", 50),
        ("Rock Slide", 75),
        ("Stone Edge", 100),
        ("Polish", 0),
    ],
    "ghost": [
        ("Lick", 30),
        ("Shadow Ball", 80),
        ("Poltergeist", 110),
        ("Confuse Ray", 0),
    ],
    "dragon": [
        ("Twister", 40),
        ("Dragon Claw", 80),
        ("Outrage", 120),
        ("Dragon Dance", 0),
    ],
    "dark": [("Bite", 60), ("Crunch", 80), ("Dark Pulse", 80), ("Nasty Plot", 0)],
    "steel": [
        ("Metal Claw", 50),
        ("Iron Head", 80),
        ("Flash Cannon", 80),
        ("Iron Defense", 0),
    ],
    "fairy": [
        ("Fairy Wind", 40),
        ("Moonblast", 95),
        ("Play Rough", 90),
        ("Moonlight", 0),
    ],
}

# --- 3. BATTLE LOGIC ---


def get_moves_for_type(p_type):
    # Get moves specific to type, fallback to Normal
    moves = MOVES_DB.get(p_type, MOVES_DB["normal"])
    # Return 4 moves: 2 Type moves + 1 Normal Move + 1 Heal/Status
    normal_moves = MOVES_DB["normal"]

    # Simple set: Move 1 (Weak), Move 2 (Strong), Move 3 (Tackle), Move 4 (Heal/Status)
    deck = [moves[0], moves[1], normal_moves[0], moves[3]]
    return deck


def calculate_damage(
    move_name,
    move_power,
    attacker_type,
    defender_type,
    attacker_stats,
    defender_stats,
    ability,
):
    """
    Advanced Damage Formula with Type Effectiveness and Abilities
    """
    if move_power == 0:
        return 0, "status"  # Heals/Buffs handled separately

    level = 50
    atk = attacker_stats["attack"]
    defense = defender_stats["defense"]

    # 1. Base Damage
    damage = (((2 * level / 5 + 2) * move_power * (atk / defense)) / 50) + 2

    # 2. Type Effectiveness
    multiplier = 1.0

    # Check if attacker type matches move type (STAB - Same Type Attack Bonus)
    # For MVP, we assume move type = attacker type for the first 2 moves
    if attacker_type in MOVES_DB and move_name in [
        m[0] for m in MOVES_DB[attacker_type]
    ]:
        damage *= 1.5  # STAB

    # Check Weakness/Resistance
    if attacker_type in TYPE_CHART:
        multiplier = TYPE_CHART[attacker_type].get(defender_type, 1.0)

    damage *= multiplier

    # 3. Ability Logic (Simplified)
    msg = ""
    # "Blaze/Torrent/Overgrow" - Boost damage when low HP (Handled in Battle loop?)
    # "Huge Power" - Double Attack
    if ability == "huge-power":
        damage *= 2
        msg = " (Huge Power!)"

    return int(damage), multiplier, msg


class DuelView(discord.ui.View):
    def __init__(self, bot, p1, p2, p1_data, p2_data):
        super().__init__(timeout=300)
        self.bot = bot
        self.p1 = p1
        self.p2 = p2

        self.p1_data = p1_data
        self.p2_data = p2_data

        # Setup HP (Level 50 approximation: Base HP * 2 + 110)
        self.p1_max_hp = p1_data["stats"]["hp"] * 2 + 50
        self.p2_max_hp = p2_data["stats"]["hp"] * 2 + 50
        self.p1_hp = self.p1_max_hp
        self.p2_hp = self.p2_max_hp

        # Moves
        self.p1_moves = get_moves_for_type(p1_data["type"])
        self.p2_moves = get_moves_for_type(p2_data["type"])

        # State
        self.turn = p1.id
        self.logs = [f"🛑 Battle Start!"]

        # ABILITY: Intimidate Check (On Entry)
        self.apply_entry_abilities()

        # Create Buttons for Moves
        self.update_buttons()

    def apply_entry_abilities(self):
        # P1 Ability
        if self.p1_data["ability"] == "intimidate":
            self.p2_data["stats"]["attack"] *= 0.66
            self.logs.append(
                f"😤 {self.p1_data['name']}'s Intimidate cut {self.p2_data['name']}'s Attack!"
            )
        # P2 Ability
        if self.p2_data["ability"] == "intimidate":
            self.p1_data["stats"]["attack"] *= 0.66
            self.logs.append(
                f"😤 {self.p2_data['name']}'s Intimidate cut {self.p1_data['name']}'s Attack!"
            )

        # Drizzle / Drought could go here

    def update_buttons(self):
        self.clear_items()

        current_moves = self.p1_moves if self.turn == self.p1.id else self.p2_moves

        for i, (move_name, power) in enumerate(current_moves):
            style = discord.ButtonStyle.secondary
            if power == 0:
                style = discord.ButtonStyle.success  # Heal
            elif i == 0:
                style = discord.ButtonStyle.primary  # Main Move
            elif i == 1:
                style = discord.ButtonStyle.danger  # Strong Move

            btn = discord.ui.Button(label=f"{move_name}", style=style, row=0)
            btn.callback = self.make_callback(move_name, power)
            self.add_item(btn)

        # Surrender Button
        surrender_btn = discord.ui.Button(
            label="🏳️ Surrender", style=discord.ButtonStyle.red, row=1
        )
        surrender_btn.callback = self.surrender
        self.add_item(surrender_btn)

    def make_callback(self, name, power):
        async def callback(interaction: discord.Interaction):
            await self.handle_turn(interaction, name, power)

        return callback

    async def handle_turn(self, interaction, move_name, move_power):
        if interaction.user.id != self.turn:
            await interaction.response.send_message("⏳ Not your turn!", ephemeral=True)
            return

        # Define Attacker/Defender
        if self.turn == self.p1.id:
            attacker, defender = self.p1, self.p2
            a_data, d_data = self.p1_data, self.p2_data
            is_p1_attacking = True
        else:
            attacker, defender = self.p2, self.p1
            a_data, d_data = self.p2_data, self.p1_data
            is_p1_attacking = False

        # HEAL / STATUS
        if move_power == 0:
            heal_amt = int(a_data["stats"]["hp"] * 0.5)  # Heal 50% base HP
            if is_p1_attacking:
                self.p1_hp = min(self.p1_max_hp, self.p1_hp + heal_amt)
            else:
                self.p2_hp = min(self.p2_max_hp, self.p2_hp + heal_amt)

            self.logs.append(f"💚 {a_data['name']} used {move_name} and healed!")

        # DAMAGE
        else:
            dmg, multiplier, ability_msg = calculate_damage(
                move_name,
                move_power,
                a_data["type"],
                d_data["type"],
                a_data["stats"],
                d_data["stats"],
                a_data["ability"],
            )

            # Ability Check: Blaze/Torrent/Overgrow (Boosts Type moves at < 1/3 HP)
            current_hp = self.p1_hp if is_p1_attacking else self.p2_hp
            max_hp = self.p1_max_hp if is_p1_attacking else self.p2_max_hp

            starter_abilities = ["blaze", "torrent", "overgrow", "swarm"]
            if a_data["ability"] in starter_abilities and (current_hp < max_hp / 3):
                dmg = int(dmg * 1.5)
                ability_msg = f" ({a_data['ability'].upper()}!)"

            # Apply Damage
            if is_p1_attacking:
                self.p2_hp -= dmg
            else:
                self.p1_hp -= dmg

            # Log Text
            eff_text = ""
            if multiplier > 1:
                eff_text = " It's Super Effective! 💥"
            elif multiplier < 1:
                eff_text = " It's not very effective..."

            self.logs.append(
                f"⚔️ {a_data['name']} used {move_name}!{eff_text}{ability_msg} (-{dmg})"
            )

        # Win Check
        if self.p1_hp <= 0 or self.p2_hp <= 0:
            await self.end_game(interaction)
            return

        # Switch Turn
        self.turn = self.p2.id if self.turn == self.p1.id else self.p1.id
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def surrender(self, interaction):
        if interaction.user.id == self.p1.id:
            self.p1_hp = 0
        elif interaction.user.id == self.p2.id:
            self.p2_hp = 0
        else:
            return
        await self.end_game(interaction)

    async def end_game(self, interaction):
        winner = self.p1 if self.p2_hp <= 0 else self.p2
        loser_name = self.p2_data["name"] if self.p2_hp <= 0 else self.p1_data["name"]

        self.logs.append(f"🏆 {winner.name}'s Pokemon fainted {loser_name}!")

        # Payout
        winner_uuid = await get_or_create_uuid(self.bot.db, winner.id, winner.name)
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "UPDATE game_profile SET coins = coins + 50 WHERE user_uuid = ?",
                (winner_uuid,),
            )
        await self.bot.db.commit()

        embed = self.get_embed()
        embed.color = discord.Color.gold()
        embed.title = f"🏆 {winner.name} Wins!"
        embed.set_footer(text="Winner received 50 Coins")

        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    def get_embed(self):
        # Visualize HP Bars
        def get_bar(curr, maxi):
            ratio = max(0, curr / maxi)
            filled = int(ratio * 10)
            color = "🟩" if ratio > 0.5 else "🟨" if ratio > 0.2 else "🟥"
            return color * filled + "⬛" * (10 - filled)

        embed = discord.Embed(title="⚔️ Pokémon Battle", color=discord.Color.red())

        # P1
        p1_status = ""
        if self.p1_data["ability"] in ["intimidate", "blaze", "huge-power"]:
            p1_status = f" | Abil: {self.p1_data['ability']}"
        embed.add_field(
            name=f"{self.p1.name}'s {self.p1_data['name']}",
            value=f"{get_bar(self.p1_hp, self.p1_max_hp)}\n**{int(self.p1_hp)}/{self.p1_max_hp} HP**{p1_status}",
            inline=True,
        )

        # P2
        p2_status = ""
        if self.p2_data["ability"] in ["intimidate", "blaze", "huge-power"]:
            p2_status = f" | Abil: {self.p2_data['ability']}"
        embed.add_field(
            name=f"{self.p2.name}'s {self.p2_data['name']}",
            value=f"{get_bar(self.p2_hp, self.p2_max_hp)}\n**{int(self.p2_hp)}/{self.p2_max_hp} HP**{p2_status}",
            inline=True,
        )

        # Log
        log_text = "\n".join(self.logs[-4:])
        embed.add_field(
            name="📜 Battle Log", value=f"```\n{log_text}\n```", inline=False
        )

        turn_name = self.p1.name if self.turn == self.p1.id else self.p2.name
        embed.set_footer(text=f"Waiting for {turn_name} to choose a move...")
        return embed


class Combat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_buddy_data(self, user_id, user_name):
        user_uuid = await get_or_create_uuid(self.bot.db, user_id, user_name)
        async with self.bot.db.cursor() as cursor:
            # Get Buddy ID
            await cursor.execute(
                "SELECT buddy_id FROM game_profile WHERE user_uuid = ?", (user_uuid,)
            )
            row = await cursor.fetchone()
            if not row or not row[0]:
                return None

            buddy_db_id = row[0]
            await cursor.execute(
                "SELECT pokemon_id, pokemon_name, nickname FROM collection WHERE id = ?",
                (buddy_db_id,),
            )
            p_row = await cursor.fetchone()
            if not p_row:
                return None

            return {"pokedex_id": p_row[0], "name": p_row[2] if p_row[2] else p_row[1]}

    async def fetch_full_data(self, pokedex_id):
        url = f"https://pokeapi.co/api/v2/pokemon/{pokedex_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    # 1. Stats
                    stats = {s["stat"]["name"]: s["base_stat"] for s in data["stats"]}
                    # 2. Type (Primary)
                    p_type = data["types"][0]["type"]["name"]
                    # 3. Ability (First one)
                    ability = data["abilities"][0]["ability"]["name"]

                    return {"stats": stats, "type": p_type, "ability": ability}
        return None

    @app_commands.command(
        name="duel", description="Challenge a friend to a Real Pokemon Battle!"
    )
    async def duel(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot or opponent.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ Invalid opponent.", ephemeral=True
            )
            return

        await interaction.response.defer()

        # 1. Get Buddies
        p1_base = await self.get_buddy_data(interaction.user.id, interaction.user.name)
        p2_base = await self.get_buddy_data(opponent.id, opponent.name)

        if not p1_base:
            await interaction.followup.send("❌ Set a buddy first! `/pokemon buddy`")
            return
        if not p2_base:
            await interaction.followup.send(f"❌ {opponent.name} has no buddy!")
            return

        # 2. Fetch Full API Data (Stats, Type, Abilities)
        p1_full = await self.fetch_full_data(p1_base["pokedex_id"])
        p2_full = await self.fetch_full_data(p2_base["pokedex_id"])

        # Merge Data
        p1_data = {**p1_base, **p1_full}
        p2_data = {**p2_base, **p2_full}

        # 3. Start Duel
        view = DuelView(self.bot, interaction.user, opponent, p1_data, p2_data)
        await interaction.followup.send(
            f"⚔️ **BATTLE START!**\n{interaction.user.mention} 🆚 {opponent.mention}",
            embed=view.get_embed(),
            view=view,
        )


async def setup(bot):
    await bot.add_cog(Combat(bot))
