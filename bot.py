import os

import discord
import motor.motor_asyncio

from discord.ext import commands
from discord.ext.commands import CommandNotFound
from dotenv import load_dotenv
from pymongo.database import Database

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_ADMIN_ID = int(os.getenv("DISCORD_ADMIN_ID"))
MONGO_USER = os.getenv("MONGO_BOT_USER")
MONGO_PASSWORD = os.getenv("MONGO_BOT_PASSWORD")

COGS = ["cog_npchelper_dnd5e"]


class NpcHelper(commands.Bot):
    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.mclient = motor.motor_asyncio.AsyncIOMotorClient(f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@localhost:58017/npchelper")
        self.mdb: Database = self.mclient["npchelper"]


bot = NpcHelper(command_prefix="!", activity=discord.Game(name="Dungeons & Dragons"))


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandNotFound):
        return

    raise error

for cog in COGS:
    bot.load_extension(cog)

bot.run(DISCORD_BOT_TOKEN)
