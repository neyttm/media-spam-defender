import discord
from discord.ext import commands
import config

# Настройка намерений (Intents) для работы с участниками и сообщениями
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    print("------")
    
    # Загрузка модуля антирейда
    try:
        bot.load_extension("cogs.antiraid")
        print("AntiRaid module successfully loaded.")
    except Exception as e:
        print(f"Failed to load AntiRaid module: {e}")

if __name__ == "__main__":
    if config.BOT_TOKEN:
        bot.run(config.BOT_TOKEN)
    else:
        print("Error: BOT_TOKEN is not found in config or .env file.")
