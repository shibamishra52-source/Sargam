from pyrogram import Client as Bot
from callsmusic import run
from config import API_ID, API_HASH, BOT_TOKEN
bot = Bot(
    "sargam_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="modules")
)
bot.start()
run()
