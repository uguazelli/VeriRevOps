import httpx

class MattermostService:
    def __init__(self):
        pass

    async def send_message(self, server_url: str, bot_token: str, channel_id: str, text: str, username: str = None):
        """
        Sends a message to a Mattermost channel.
        """
        url = f"{server_url}/api/v4/posts"
        headers = {
            "Authorization": f"Bearer {bot_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "channel_id": channel_id,
            "message": text
        }

        # If username override is needed/allowed by permissions
        if username:
            # We can use props to override username/icon if the bot account has permissions
            # or just rely on the message text formatting.
            # For this implementation, we'll try props but it might be ignored if not enabled in System Console.
            payload["props"] = {
                "override_username": username
            }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
            except Exception as e:
                print(f"Failed to send Mattermost message: {e}")
