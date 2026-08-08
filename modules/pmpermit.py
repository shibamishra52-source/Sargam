from pyrogram import filters
from pyrogram.types import Message
from callsmusic.callsmusic import client as USER
@USER.on_message(filters.text & filters.private & ~filters.me & ~filters.bot)
async def pmPermit(client, message: Message)
 await message.reply_text("⚠️ *Warning!* Owner is currently busy right now. "
        "Please wait, we will talk to you when free. Do not spam!")
                          
