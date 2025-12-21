import discord
from discord import app_commands
from discord.ext import commands


# --- THE DROPDOWN MENU ---
class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Commands List",
                description="List of all available commands",
                emoji="📜",
            ),
            discord.SelectOption(
                label="Rarity & Rates",
                description="Shiny odds and Legendary chances",
                emoji="📊",
            ),
            discord.SelectOption(
                label="How to Trade", description="Guide on Trading & IDs", emoji="🤝"
            ),
            discord.SelectOption(
                label="Economy Guide",
                description="Coins, Shop, and Release",
                emoji="🪙",
            ),
        ]
        super().__init__(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        # 1. COMMANDS LIST
        if self.values[0] == "Commands List":
            embed = discord.Embed(title="📜 Command List", color=discord.Color.blue())
            embed.add_field(
                name="🎮 Pokémon",
                value=(
                    "`/pokemon pull [amount]` - Summon 1-10 Pokémon\n"
                    "`/pokemon daily` - Claim 5 Free Pulls (24h Cooldown)\n"
                    "`/pokemon box` - View your Pokémon & **Unique IDs**\n"
                    "`/pokemon trade` - Trade with a friend\n"
                    "`/pokemon pokedex` - View collection progress\n"
                ),
                inline=False,
            )
            embed.add_field(
                name="🪙 Economy",
                value=(
                    "`/pokemon balance` - Check Coins & Pulls\n"
                    "`/pokemon shop` - Buy Pulls (100 Coins)\n"
                    "`/pokemon release` - Sell Pokémon for 20 Coins\n"
                ),
                inline=False,
            )
            embed.add_field(
                name="📈 Leveling", value="`/xp rank`, `/xp leaderboard`", inline=False
            )
            await interaction.response.edit_message(embed=embed)

        # 2. RARITY & RATES
        elif self.values[0] == "Rarity & Rates":
            embed = discord.Embed(
                title="📊 Rarity & Drop Rates", color=discord.Color.gold()
            )
            embed.description = (
                "The Gacha system uses real-time RNG. Here are the odds:"
            )

            embed.add_field(name="⚪ Common Pull", value="**93%** Chance", inline=True)
            embed.add_field(
                name="🔥 Legendary Pull",
                value="**5%** Chance (1 in 20)\n*Includes Mewtwo, Rayquaza, Arceus, etc.*",
                inline=True,
            )
            embed.add_field(
                name="✨ Shiny Chance",
                value="**2%** Chance (1 in 50)\n*Any Pokémon (Common or Legendary) can be Shiny.*",
                inline=False,
            )

            embed.set_footer(
                text="Legendaries have Gold borders. Shinies have Sparkles."
            )
            await interaction.response.edit_message(embed=embed)

        # 3. HOW TO TRADE
        elif self.values[0] == "How to Trade":
            embed = discord.Embed(title="🤝 Trading Guide", color=discord.Color.green())
            embed.description = "Trading requires the **Unique ID** of the specific Pokémon you want to swap."

            embed.add_field(
                name="Step 1: Find IDs",
                value="Type `/pokemon box`. You will see a list like:\n`ID: 502` — **Charizard** ✨\n`ID: 503` — **Pikachu**",
                inline=False,
            )
            embed.add_field(
                name="Step 2: Start Trade",
                value="Use the command:\n`/pokemon trade partner:@Friend your_id:502 their_id:601`",
                inline=False,
            )
            embed.add_field(
                name="Step 3: Confirm",
                value="Your friend must click the **Green Button** to accept.",
                inline=False,
            )
            await interaction.response.edit_message(embed=embed)

        # 4. ECONOMY
        elif self.values[0] == "Economy Guide":
            embed = discord.Embed(
                title="🪙 Economy Guide", color=discord.Color.light_grey()
            )
            embed.add_field(
                name="How to get Coins?",
                value="• **Release Duplicates:** `/pokemon release` gives 20 coins.\n• **Daily:** `/pokemon daily` gives coins + pulls.",
                inline=False,
            )
            embed.add_field(
                name="What are Coins for?",
                value="Type `/pokemon shop`. You can buy **More Pulls**!\n• 1 Pull = 100 Coins\n• 10 Pulls = 900 Coins (Discount)",
                inline=False,
            )
            await interaction.response.edit_message(embed=embed)


class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(HelpSelect())


# --- MAIN COG ---
class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Master Guide to the Bot")
    async def help(self, interaction: discord.Interaction):
        # Initial Embed
        embed = discord.Embed(
            title="🤖 Bot Manual",
            description="Select a category below to learn about the system!",
            color=discord.Color.brand_green(),
        )
        embed.set_thumbnail(
            url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )

        await interaction.response.send_message(embed=embed, view=HelpView())


async def setup(bot):
    await bot.add_cog(Help(bot))
