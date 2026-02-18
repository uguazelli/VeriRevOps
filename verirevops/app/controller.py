
def handle_webhook(alias: str, webhook_data: dict):
    print(f"Received webhook for alias: {alias}")
    print(f"Webhook data: {webhook_data}")
    return {"status": "ok", "message": "Tenant created successfully"}