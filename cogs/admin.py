import discord
from discord import app_commands
from discord.ext import commands

from utils.data_manager import get_guild_data, save_data


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Admin Cog is ready.")

    # --- COMMAND: SET LOG CHANNEL ---
    @app_commands.command(
        name="setlogchannel", description="Set the channel where mod logs appear"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_log_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        # 1. Get the data for this server
        data = get_guild_data(interaction.guild.id)

        # 2. Update the setting
        data["settings"]["log_channel_id"] = channel.id

        # 3. Save to file
        save_data()

        await interaction.response.send_message(
            f"✅ Log channel has been set to {channel.mention}"
        )


async def setup(bot):
    await bot.add_cog(Admin(bot))
