import httpx
from app.services import bot_service

TELEGRAM_API_BASE = "https://api.telegram.org/bot"

async def send_message(token: str, chat_id: str, text: str):
    url = f"{TELEGRAM_API_BASE}{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown" # Optional, but good for formmating
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        except Exception as e:
            print(f"❌ Telegram Send Failed: {e}")

async def process_webhook(token: str, payload: dict):
    """
    Process Telegram Webhook Update.
    The 'token' identifies the bot instance (and thus the tenant).
    """
    # 1. Extract Message Data
    # We only care about text messages for now
    message = payload.get("message")
    if not message:
        return {"status": "ignored", "reason": "no_message"}

    chat_id = str(message.get("chat", {}).get("id"))
    user_text = message.get("text")

    if not chat_id or not user_text:
         return {"status": "ignored", "reason": "no_chat_id_or_text"}

    # Telegram doesn't usually send "from_me" via webhook updates unless we listen to 'channel_post' or 'edited_message'
    # For standard user interactions, it's always from the user.
    # Whatever, we can default from_me=False.
    # Note: If we want to support "Commanding the bot" via admin account on Telegram, we'd need to identify the admin ID.
    # For now, treat all inputs as user inputs.
    from_me = False

    # 2. Define Reply Callback
    async def reply_to_telegram(text: str):
        await send_message(token, chat_id, text)

    # 3. Delegate to Bot Service
    # Note: We use the 'token' as the instance_id for lookup in the mappings table.
    return await bot_service.process_message(
        instance_id=token,
        user_id=chat_id,
        text=user_text,
        reply_callback=reply_to_telegram,
        from_me=from_me
    )
