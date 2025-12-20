import random

import discord
from discord import app_commands
from discord.ext import commands

from utils.database import get_or_create_uuid


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cd = commands.CooldownMapping.from_cooldown(
            1, 60.0, commands.BucketType.user
        )

    @commands.Cog.listener()
    async def on_ready(self):
        print("Leveling Cog is ready.")

    # --- DEFINE THE GROUP ---
    xp_group = app_commands.Group(name="xp", description="Leveling and Experience")

    # --- MATH & EVENTS ---
    def get_ratelimit(self, message: discord.Message):
        bucket = self._cd.get_bucket(message)
        return bucket.update_rate_limit()

    def calculate_xp_for_next_level(self, level: int):
        # Formula: 5 * (L^2) + 50 * L + 100
        return 5 * (level**2) + (50 * level) + 100

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if self.get_ratelimit(message):
            return

        user_uuid = await get_or_create_uuid(message.author.id, message.author.name)

        await self.add_xp(user_uuid, message.author, message.guild, message.channel)

    async def add_xp(self, user_uuid, user, guild, channel):
        xp_to_add = random.randint(15, 35)

        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT xp, level FROM levels WHERE user_uuid = ?", (user_uuid,)
            )
            result = await cursor.fetchone()

            if result is None:
                await cursor.execute(
                    "INSERT INTO levels (user_uuid, guild_id, xp, level) VALUES (?, ?, ?, ?)",
                    (user_uuid, guild.id, xp_to_add, 1),
                )
            else:
                current_xp, current_level = result
                new_xp = current_xp + xp_to_add
                xp_threshold = self.calculate_xp_for_next_level(current_level)

                if new_xp >= xp_threshold:
                    new_level = current_level + 1
                    remaining_xp = new_xp - xp_threshold

                    # Reward: +1 Pull
                    await cursor.execute(
                        "INSERT OR IGNORE INTO game_profile (user_uuid) VALUES (?)",
                        (user_uuid,),
                    )
                    await cursor.execute(
                        "UPDATE game_profile SET available_pulls = available_pulls + 1 WHERE user_uuid = ?",
                        (user_uuid,),
                    )

                    # We mention the user so they see it
                    await channel.send(
                        f"🎉 {user.mention} has reached **Level {new_level}**! \n🎁 **Bonus:** +1 Poké Ball added."
                    )

                    await cursor.execute(
                        "UPDATE levels SET xp = ?, level = ? WHERE user_uuid = ?",
                        (remaining_xp, new_level, user_uuid),
                    )
                else:
                    await cursor.execute(
                        "UPDATE levels SET xp = ? WHERE user_uuid = ?",
                        (new_xp, user_uuid),
                    )
                    await self.bot.db.commit()

    # --- COMMANDS ---

    @xp_group.command(name="rank", description="Check your current level")
    async def rank(
        self, interaction: discord.Interaction, member: discord.Member = None
    ):
        target = member or interaction.user
        target_uuid = await get_or_create_uuid(target.id)

        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT xp, level FROM levels WHERE user_uuid = ?", (target_uuid,)
            )
            result = await cursor.fetchone()

        if result is None:
            await interaction.response.send_message(
                f"❌ **{target.name}** hasn't earned any XP yet!", ephemeral=True
            )
            return

        current_xp, level = result
        xp_needed_total = self.calculate_xp_for_next_level(level)
        percentage = min(1.0, max(0.0, current_xp / xp_needed_total))

        blocks = int(percentage * 10)
        bar = "🟦" * blocks + "⬜" * (10 - blocks)

        embed = discord.Embed(title=f"Rank: {target.name}", color=discord.Color.blue())
        embed.add_field(name="Level", value=f"**{level}**", inline=True)
        embed.add_field(
            name="XP Progress", value=f"{current_xp} / {xp_needed_total}", inline=True
        )
        embed.add_field(
            name="Progress", value=f"{bar} {int(percentage * 100)}%", inline=False
        )
        embed.set_thumbnail(
            url=target.avatar.url if target.avatar else target.default_avatar.url
        )

        await interaction.response.send_message(embed=embed)

    @xp_group.command(name="leaderboard", description="See the top users")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()

        async with self.bot.db.cursor() as cursor:
            await cursor.execute("""
                    SELECT users.username, levels.level, levels.xp
                    FROM levels
                    JOIN users ON levels.user_uuid = users.user_uuid
                    ORDER BY levels.level DESC, levels.xp DESC LIMIT 10
                """)
            rows = await cursor.fetchall()

        if not rows:
            await interaction.followup.send("No data found!")
            return

        embed = discord.Embed(title="🏆 Server Leaderboard", color=discord.Color.gold())
        description = ""

        for index, row in enumerate(rows, start=1):
            username, level, xp = row

            name = username if username else "Unknown User"

            medal = (
                "🥇"
                if index == 1
                else "🥈"
                if index == 2
                else "🥉"
                if index == 3
                else f"#{index}"
            )
            description += f"{medal} **{name}** — Lv {level} ({xp} XP)\n"

        embed.description = description
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Leveling(bot))
