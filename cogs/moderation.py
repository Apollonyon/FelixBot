import discord
from discord import app_commands
from discord.ext import commands

from utils.data_manager import get_guild_data
from utils.database import get_or_create_uuid


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Moderation Cog is ready.")

    # --- DEFINE THE GROUP ---
    mod_group = app_commands.Group(name="mod", description="Moderation tools")

    # --- HELPER: LOGGING SYSTEM ---
    async def log_action(
        self,
        guild: discord.Guild,
        user_id: int,
        mod_id: int,
        action_type: str,
        reason: str,
    ):
        target_uuid = await get_or_create_uuid(user_id)
        mod_uuid = await get_or_create_uuid(mod_id)

        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO mod_logs (target_uuid, mod_uuid, action_type, reason)
                VALUES (?, ?, ?, ?)
            """,
                (target_uuid, mod_uuid, action_type, reason),
            )
        await self.bot.db.commit()

        data = get_guild_data(guild.id)
        channel_id = data["settings"].get("log_channel_id")

        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title=f"Action: {action_type}", color=discord.Color.red()
                )
                embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
                embed.add_field(name="Moderator", value=f"<@{mod_id}>", inline=True)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.set_footer(text=f"UUID: {target_uuid}")
                embed.timestamp = discord.utils.utcnow()
                await channel.send(embed=embed)

    # --- COMMANDS (Attached to mod_group) ---

    @mod_group.command(name="warn", description="Warn a user and log it")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def warn(
        self, interaction: discord.Interaction, member: discord.Member, reason: str
    ):
        try:
            await member.send(
                f"⚠️ You have been warned in **{interaction.guild.name}**. Reason: {reason}"
            )
        except discord.Forbidden:
            pass

        await self.log_action(
            interaction.guild, member.id, interaction.user.id, "WARN", reason
        )
        await interaction.response.send_message(
            f"⚠️ **{member.name}** has been warned.", ephemeral=False
        )

    @mod_group.command(name="kick", description="Kick a user and log it")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason",
    ):
        if member == interaction.user:
            await interaction.response.send_message(
                "You cannot kick yourself!", ephemeral=True
            )
            return
        try:
            await member.kick(reason=reason)
            await self.log_action(
                interaction.guild, member.id, interaction.user.id, "KICK", reason
            )
            await interaction.response.send_message(
                f"👞 **{member.name}** has been kicked.", ephemeral=False
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission.", ephemeral=True
            )

    @mod_group.command(name="ban", description="Ban a user and log it")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason",
    ):
        try:
            await member.ban(reason=reason)
            await self.log_action(
                interaction.guild, member.id, interaction.user.id, "BAN", reason
            )
            await interaction.response.send_message(
                f"🔨 **{member.name}** has been banned.", ephemeral=False
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission.", ephemeral=True
            )

    @mod_group.command(name="history", description="View a user's moderation history")
    async def history(self, interaction: discord.Interaction, member: discord.Member):
        target_uuid = await get_or_create_uuid(member.id)

        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                """
                SELECT action_type, reason, timestamp FROM mod_logs
                WHERE target_uuid = ? ORDER BY timestamp DESC LIMIT 10
            """,
                (target_uuid,),
            )
            rows = await cursor.fetchall()

        if not rows:
            await interaction.response.send_message(
                f"**{member.name}** has a clean record! ✨"
            )
            return

        embed = discord.Embed(
            title=f"Mod Logs for {member.name}", color=discord.Color.orange()
        )
        embed.set_footer(text=f"Privacy UUID: {target_uuid}")

        for action, reason, timestamp in rows:
            embed.add_field(
                name=f"{action} ({str(timestamp)[:16]})", value=reason, inline=False
            )

        await interaction.response.send_message(embed=embed)

    # --- ERROR HANDLING ---
    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "🚫 You don't have permission!", ephemeral=True
            )
        else:
            await interaction.response.send_message(f"Error: {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
