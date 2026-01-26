import logging
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.dtos.webhook import ChatwootEvent, IntegrationEvent
from app.bot.actions import (
    check_subscription_quota,
    execute_crm_action,
    get_client_and_config,
    get_crm_integrations,
    handle_audio_message,
    handle_chatwoot_response,
    handle_conversation_resolution,
)
from app.core.logging import log_error, log_skip, log_start, log_success

logger = logging.getLogger(__name__)


async def process_integration_event(client_slug: str, payload_dict: dict, db: AsyncSession):
    log_start(logger, f"Processing Integration Event for {client_slug}")

    try:
        # ==================================================================================
        # STEP 1: VALIDATE PAYLOAD
        # Ensure the incoming webhook payload matches our expected schema (IntegrationEvent).
        # ==================================================================================
        try:
            event = IntegrationEvent(**payload_dict)
        except Exception as e:
            log_error(logger, f"Invalid Payload: {e}")
            return {"status": "invalid_payload"}

        # ==================================================================================
        # STEP 2: LOAD CLIENT & CRM CONFIGURATIONS
        # access the database to get client details and active CRM credentials (HubSpot, EspoCRM, etc.)
        # ==================================================================================
        client, configs = await get_client_and_config(client_slug, db)

        crms = get_crm_integrations(configs)

        # ==================================================================================
        # STEP 3: HANDLE "CONVERSATION CREATED" (New Lead)
        # When a new conversation starts, we treat the user as a potential Lead.
        # We sync their Name, Email, and Phone to all connected CRMs.
        # ==================================================================================
        if event.event == "conversation_created":
            if crms:
                sender = event.effective_sender
                if sender and (sender.email or sender.phone_number):
                    await execute_crm_action(
                        crms,
                        "lead",
                        lambda crm: crm.sync_lead(
                            name=sender.name, email=sender.email, phone_number=sender.phone_number
                        ),
                    )
                else:
                    log_skip(logger, "Skipping CRM sync: No email or phone provided")
            else:
                log_skip(logger, "Skipping CRM sync: No CRM configured")

            return {"status": "conversation_created_processed"}

        # ==================================================================================
        # STEP 4: HANDLE "CONTACT UPDATED"
        # If a contact's details change in Chatwoot, we mirror those changes to the CRM.
        # ==================================================================================
        elif event.event in ("contact_created", "contact_updated"):
            if crms:
                await execute_crm_action(crms, f"contact ({event.event})", lambda crm: crm.sync_contact(payload_dict))
            else:
                log_skip(logger, "Skipping CRM sync: No CRM configured")

            return {"status": "contact_event_processed"}

        # ==================================================================================
        # STEP 5: HANDLE "CONVERSATION RESOLVED"
        # This is critical for the RAG/Summarization loop.
        # When a ticket is marked "Resolved":
        # 1. We fetch the full chat history.
        # 2. We use an LLM to generate a summary (Issue, Resolution, Sentiment).
        # 3. We push this summary to the Client's CRM note/timeline.
        # ==================================================================================
        elif event.event == "conversation_status_changed":
            status = payload_dict.get("status")
            if isinstance(event.content, dict):
                status = event.content.get("status", status)
                conversation_data = event.content
            else:
                conversation_data = payload_dict.get("content", payload_dict)

            if status == "resolved":
                log_start(logger, "Conversation resolved. Initiating Summarization & Sync.")

                sender = event.effective_sender
                await handle_conversation_resolution(client, configs, conversation_data, sender, db)
                return {"status": "conversation_status_processed"}

        return {"status": "ignored_event"}
    except Exception as e:
        log_error(logger, f"Integration event processing failed: {e}", exc_info=True)
        return {"status": "error"}


async def process_bot_event(client_slug: str, payload_dict: dict, db: AsyncSession):
    log_start(logger, f"Processing Bot Event for {client_slug}")

    # ==================================================================================
    # STEP 1: VALIDATE PAYLOAD
    # ==================================================================================
    try:
        event = ChatwootEvent(**payload_dict)
    except Exception as e:
        log_error(logger, f"Invalid Bot Payload: {e}")
        return {"status": "invalid_payload"}

    # ==================================================================================
    # STEP 2: LOAD CLIENT & CONFIGURATION
    # ==================================================================================
    client, configs = await get_client_and_config(client_slug, db)

    # ==================================================================================
    # STEP 3: CHECK SUBSCRIPTION QUOTA
    # ==================================================================================
    subscription = await check_subscription_quota(client.id, client_slug, db)
    if not subscription:
        return {"status": "quota_exceeded"}

    # Validate essential configs
    rag_config = configs.get("rag")
    chatwoot_config = configs.get("chatwoot")
    if not rag_config or not chatwoot_config:
        log_error(logger, f"Missing configs for {client_slug}")
        raise HTTPException(status_code=500, detail="Configuration missing")

    # ==================================================================================
    # STEP 4: FILTER EVENTS
    # ==================================================================================
    if not event.is_valid_bot_command:
        if event.event != "message_created":
            return {"status": "ignored_event"}
        if not event.is_incoming:
            return {"status": "ignored_outgoing"}
        if event.conversation and event.conversation.status in ("snoozed", "open"):
            return {"status": f"ignored_{event.conversation.status}"}
        return {"status": "ignored_generic"}

    # Basic Message Data
    conversation_id = event.conversation_id
    user_query = event.content
    logger.info(f"Message from {event.message_type} in conversation {conversation_id}")

    try:
        # ==================================================================================
        # STEP 5: HANDLE AUDIO ATTACHMENTS
        # ==================================================================================
        if not user_query and event.attachments:
            transcript = await handle_audio_message(event.attachments, rag_config)
            if transcript:
                user_query = transcript

        if not user_query:
            log_skip(logger, "Empty message content")
            return {"status": "empty_message"}

        # ==================================================================================
        # STEP 6: SESSION MANAGEMENT (Delegated to Service)
        # ==================================================================================
        from app.services.session_service import get_or_create_bot_session
        session = await get_or_create_bot_session(db, client.id, conversation_id)

        # ==================================================================================
        # STEP 7 & 8: EXECUTE AGENT (Delegated to Service)
        # ==================================================================================
        from app.services.agent_service import run_agent_pipeline

        answer, requires_human = await run_agent_pipeline(
            db=db,
            session=session,
            user_query=user_query,
            configs=configs,
            event_data=event
        )

        # ==================================================================================
        # STEP 9: SEND RESPONSE
        # ==================================================================================
        await handle_chatwoot_response(conversation_id, answer, requires_human, chatwoot_config)

        # ==================================================================================
        # STEP 10: UPDATE USAGE QUOTA
        # ==================================================================================
        subscription.usage_count += 1
        db.add(subscription)
        # session is already refreshed/attached in service, but we ensure it persists if needed
        db.add(session)
        await db.commit()
    except Exception as e:
        logger.error(f"Global Bot Error: {e}", exc_info=True)
        # Fallback Message
        fallback_msg = "I apologize, but I am experiencing a temporary system error. I am connecting you to a human agent now."
        await handle_chatwoot_response(conversation_id, fallback_msg, True, chatwoot_config)
        return {"status": "error_handled"}

    log_success(logger, "Bot Event Processed Successfully")
    return {"status": "processed"}
