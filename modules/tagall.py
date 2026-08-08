from pyrogram import filters
from pyrogram.types import Message
from callsmusic import app
@app.on_message(filters.command(["tagall", "all")] & filters.group)
async def tag_all (client, message: Message):
  chat_id = message.chat.id
  if len(message.command) < 2:
    reason = "attention everyone!"
  else:
    reason = message.text.split(None, 1)[1]
    tag_list = ""
    async for member in client.get_chat_members(chat_id):
        if member.user.is_bot or member.user.is_deleted:
          continue
           tag_list += f"[{member.user.first_name}](tg://user?id={member.user.id}) "
           if len(tag_list) > 4000:
              await client.send_message(chat_id, f"{reason}\n\n{tag_list}")
            tag_list = ""
          if tag_list:
             await client.send_message(chat_id, f"{reason}\n\n{tag_list}")
