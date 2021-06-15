import discord
import os
from discord.ext import commands
from discord.ext.commands import CommandNotFound
from dotenv import load_dotenv

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_ADMIN_ID = int(os.getenv("DISCORD_ADMIN_ID"))

bot = commands.Bot(command_prefix="!", activity=discord.Game(name="Descent into Avernus"))

@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandNotFound):
        return

    raise error

bot.load_extension("cog_npchelper_dnd5e")
bot.run(DISCORD_BOT_TOKEN)
