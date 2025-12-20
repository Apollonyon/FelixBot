import random

import discord
from discord import app_commands
from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("General Cog is ready.")

    # --- SLASH COMMANDS ---

    @app_commands.command(name="hello", description="Says hello to you!")
    async def hello(self, interaction: discord.Interaction):
        # We access the user via interaction.user
        await interaction.response.send_message(
            f"Hi there, {interaction.user.mention}!", ephemeral=True
        )

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        # We access the bot instance via self.bot
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Pong! 🏓 ({latency}ms)")

    @app_commands.command(name="coinflip", description="Flip a coin")
    async def coinflip(self, interaction: discord.Interaction):
        outcome = random.choice(["Heads", "Tails"])
        await interaction.response.send_message(f"The coin landed on: **{outcome}**")


# This function is required for main.py to load this file
async def setup(bot):
    await bot.add_cog(General(bot))
