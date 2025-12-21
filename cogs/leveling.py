import random

import discord
from discord import app_commands
from discord.ext import commands

from utils.database import get_or_create_uuid


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Anti-Spam: 1 XP gain every 60 seconds per user
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

        # Check cooldown (prevents spamming for XP)
        if self.get_ratelimit(message):
            return

        # USE THE SHARED BOT CONNECTION
        db = self.bot.db

        # Pass 'db' into the function
        user_uuid = await get_or_create_uuid(db, message.author.id, message.author.name)

        await self.add_xp(db, user_uuid, message.author, message.guild, message.channel)

    async def add_xp(self, db, user_uuid, user, guild, channel):
        xp_to_add = random.randint(15, 35)

        async with db.cursor() as cursor:
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

                    # Reward: +1 Pull for leveling up
                    await cursor.execute(
                        "INSERT INTO game_profile (user_uuid, available_pulls, coins) VALUES (?, 1, 0) ON CONFLICT(user_uuid) DO UPDATE SET available_pulls = available_pulls + 1",
                        (user_uuid,),
                    )

                    # Send Level Up Message
                    await channel.send(
                        f"🎉 {user.mention} has reached **Level {new_level}**! \n🎁 **Bonus:** +1 Pull added."
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

        # IMPORTANT: Commit changes using the shared connection
        await db.commit()

    # --- COMMANDS ---

    @xp_group.command(name="rank", description="Check your current level")
    async def rank(
        self, interaction: discord.Interaction, member: discord.Member = None
    ):
        target = member or interaction.user
        db = self.bot.db

        target_uuid = await get_or_create_uuid(db, target.id, target.name)

        async with db.cursor() as cursor:
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

        # Calculate progress bar
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

        db = self.bot.db

        async with db.cursor() as cursor:
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
