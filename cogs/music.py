import asyncio

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = []
        self.is_playing = False
        self.current_song = None

        # Optimization for speed
        self.ytdl_opts = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "default_search": "ytsearch",
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "no_check_certificate": True,
        }

        # Network optimization
        self.ffmpeg_opts = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 2",
            "options": "-vn",
        }

        self.ytdl = yt_dlp.YoutubeDL(self.ytdl_opts)

    @commands.Cog.listener()
    async def on_ready(self):
        print("Music Cog is ready.")

    music_group = app_commands.Group(name="music", description="Music commands")

    # --- AUTO-DISCONNECT LOGIC ---
    async def check_inactivity(self, interaction):
        """Waits 3 minutes. If still not playing, disconnects."""
        await asyncio.sleep(180)  # 3 Minutes

        voice_client = interaction.guild.voice_client
        # If connected, queue is empty, and audio is not playing
        if (
            voice_client
            and voice_client.is_connected()
            and not voice_client.is_playing()
            and len(self.queue) == 0
        ):
            await voice_client.disconnect()
            await interaction.channel.send(
                "💤 Left the voice channel due to inactivity."
            )

    # --- CORE PLAYER ---
    def get_stream_source(self, query):
        try:
            if not query.startswith("http"):
                query = f"ytsearch1:{query}"

            data = self.ytdl.extract_info(query, download=False)

            if "entries" in data:
                data = data["entries"][0]

            return {"source": data["url"], "title": data["title"]}
        except Exception as e:
            print(f"Error finding song: {e}")
            return None

    def play_next(self, interaction):
        if len(self.queue) > 0:
            self.is_playing = True

            song = self.queue.pop(0)
            self.current_song = song["title"]

            voice_client = interaction.guild.voice_client

            asyncio.run_coroutine_threadsafe(
                interaction.channel.send(f"🎶 **Now Playing:** {song['title']}"),
                self.bot.loop,
            )

            voice_client.play(
                discord.FFmpegPCMAudio(song["source"], **self.ffmpeg_opts),
                after=lambda e: self.play_next(interaction),
            )
        else:
            # Queue is empty! Start the disconnect timer.
            self.is_playing = False
            self.current_song = None
            asyncio.run_coroutine_threadsafe(
                interaction.channel.send(
                    "✅ Queue finished. Waiting for more songs..."
                ),
                self.bot.loop,
            )
            self.bot.loop.create_task(self.check_inactivity(interaction))

    # --- COMMANDS ---

    @music_group.command(name="play", description="Stream a song from YouTube")
    async def play(self, interaction: discord.Interaction, search: str):
        # 1. Join if needed
        if not interaction.guild.voice_client:
            if interaction.user.voice:
                await interaction.user.voice.channel.connect()
            else:
                await interaction.response.send_message(
                    "❌ Join a voice channel first.", ephemeral=True
                )
                return

        await interaction.response.defer()

        loop = asyncio.get_running_loop()
        song = await loop.run_in_executor(None, lambda: self.get_stream_source(search))

        if not song:
            await interaction.followup.send("❌ Could not find song.")
            return

        self.queue.append(song)
        voice_client = interaction.guild.voice_client

        if not self.is_playing:
            self.play_next(interaction)
            await interaction.followup.send(
                f"🔎 Found: **{song['title']}** (Loading...)"
            )
        else:
            await interaction.followup.send(f"📝 Added to queue: **{song['title']}**")

    @music_group.command(name="skip", description="Skip current song")
    async def skip(self, interaction: discord.Interaction):
        if (
            interaction.guild.voice_client
            and interaction.guild.voice_client.is_playing()
        ):
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped.")
        else:
            await interaction.response.send_message("❌ Nothing playing.")

    @music_group.command(name="stop", description="Disconnect")
    async def stop(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            self.queue.clear()
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("🛑 Disconnected.")
        else:
            await interaction.response.send_message("❌ Not connected.")


async def setup(bot):
    await bot.add_cog(Music(bot))
