from pyrogram import Client as Bot

from callsmusic import run
from config import API_ID, API_HASH, BOT_TOKEN

bot = Bot(
    "sargam_bot"
    API_ID,
    API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="modules")
)

bot.start()
run()
