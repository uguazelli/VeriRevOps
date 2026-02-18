from fastapi import APIRouter, Body

router = APIRouter(
    prefix="/api",
    tags=["chatwoot"]
)

@router.post("/webhook/{alias}")
async def handle_webhook(alias: str, webhook_data: dict = Body(...)):
    print(f"Received webhook for alias: {alias}")
    print(f"Webhook data: {webhook_data}")
    return {"status": "ok", "message": "Webhook received successfully"}