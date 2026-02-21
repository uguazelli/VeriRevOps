from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.config import settings
from app.core.chatwoot import ChatwootClient
from app.core.logger import Log
from app.core.decorators import log_and_ignore
from app.schemas.chat import ChatwootStatusChangePayload
from app.models import IntegrationConfig, ContactMapping, ChatSession
from app.services.chat_session_service import ChatSessionService
from app.services.crm.factory import CRMFactory
from app.services.integration_service import IntegrationService
from app.prompts.llm_prompts import VERI_SUMMARY_SYSTEM_PROMPT

class SummarizationService:
    """
    Service responsible for summarizing Chatwoot conversations
    and pushing them to CRM and Chatwoot nodes.
    """

    def __init__(self, db: AsyncSession, chatwoot_client: ChatwootClient):
        self.db = db
        self.chatwoot_client = chatwoot_client

    async def process_webhook_status_change(self, payload: ChatwootStatusChangePayload, tenant_id: int):
        """
        Handles the robust extraction of data from a Chatwoot status_change webhook
        and triggers the summarization process.
        """
        status = payload.status or (payload.conversation.status if payload.conversation else None)
        account_id = payload.account_id or (payload.account.id if payload.account else None)
        conversation_id = payload.id or (payload.conversation.id if payload.conversation else None)

        if not account_id or not conversation_id or not status:
            Log.warning(f"Incomplete status change payload: account_id={account_id}, conv_id={conversation_id}, status={status}")
            return

        chat_session_service = ChatSessionService(self.db)
        await chat_session_service.update_session_activity(tenant_id, int(account_id), int(conversation_id), status)

        if status != "resolved":
            return

        # 3. Resolve Contact ID (Variations in payload)
        contact_id = payload.conversation.contact_id if payload.conversation else None

        if not contact_id and payload.contact_inbox:
            contact_id = payload.contact_inbox.get("contact_id")

        if not contact_id and payload.meta:
            contact_id = payload.meta.get("sender", {}).get("id")

        # 4. Extract latest_message_id
        conv = payload.conversation
        latest_message_id = conv.last_message_id if conv else None

        if not latest_message_id and payload.messages:
            latest_message_id = payload.messages[-1].get("id")

        Log.info(f"Conversation {conversation_id} status changed to '{status}' (Contact: {contact_id}). Triggering summarization.")

        # 5. Invoke Summarization
        await self.summarize_conversation(
            tenant_id,
            int(account_id),
            conversation_id,
            status=status,
            contact_id=contact_id,
            latest_message_id=latest_message_id
        )

    async def summarize_conversation(self, tenant_id: int, account_id: int, conversation_id: int, status: str, contact_id: Optional[int] = None, latest_message_id: Optional[int] = None):
        """
        Main entry point for summarizing a conversation based on its status logic.
        """
        Log.info(f"🚀 Starting summarization for Conversation {conversation_id} (Tenant {tenant_id}, Status: {status})")

        # 0. Get Session to find last_summarized_message_id
        chat_session_service = ChatSessionService(self.db)
        session = await chat_session_service.get_session(tenant_id, account_id, conversation_id)

        last_id = session.last_summarized_message_id if session else None

        # 1. Fetch incremental messages from Chatwoot (Source of Truth)
        # We fetch messages AFTER last_id and UP TO (before) latest_message_id if provided
        fetch_before = latest_message_id + 1 if latest_message_id else None
        Log.info(f"🔍 Summarization window: after={last_id}, before={fetch_before}")

        incremental_messages = await self.chatwoot_client.get_messages(
            account_id,
            conversation_id,
            after=last_id,
            before=fetch_before,
            limit=100
        )

        if not incremental_messages:
            Log.info(f"No new messages for Conversation {conversation_id} (last_id: {last_id}, up_to: {latest_message_id}). Skipping.")
            return

        msg_ids = [m.get("id") for m in incremental_messages]
        Log.info(f"📦 Found {len(incremental_messages)} incremental messages: {msg_ids}")

        # Determine tracking ID for updates
        tracking_id = latest_message_id or incremental_messages[-1].get("id")

        # 2. Format transcript for LLM
        transcript = self._format_messages(incremental_messages)
        Log.info(f"📝 Transcript length: {len(transcript)} chars")
        if not transcript.strip():
            Log.info(f"No valid transcript content for Conversation {conversation_id}. Skipping.")
            return

        # 3. Calculate Date/Time Range
        date_range = self._calculate_date_range(incremental_messages)

        # 4. Generate Summary
        summary = await self._generate_summary(transcript, date_range)

        if not summary:
            Log.error("Failed to generate summary.")
            return

        # 5. Push Private Note to Chatwoot
        await self.chatwoot_client.send_message(account_id, conversation_id, summary, private=True)

        # 6. Optional: Push to CRM (Only on Resolve)
        if status == "resolved":
            # If contact_id not provided, try to resolve it
            if not contact_id:
                conv_data = await self.chatwoot_client.get_conversation(account_id, conversation_id)
                conversation = conv_data.get("payload") if conv_data and "payload" in conv_data else conv_data

                if conversation:
                    # 1. Direct field
                    contact_id = conversation.get("contact_id")
                    # 2. Inside contact_inbox (Common in webhook data)
                    if not contact_id:
                        contact_id = conversation.get("contact_inbox", {}).get("contact_id")
                    # 3. Inside meta (Common in API responses)
                    if not contact_id:
                        meta = conversation.get("meta", {})
                        # sender is standard for API v1
                        contact_id = meta.get("sender", {}).get("id")
                        # contact is sometimes seen in SDKs/specific events
                        if not contact_id:
                            contact_id = meta.get("contact", {}).get("id")

            if contact_id:
                await self._push_to_crms(tenant_id, contact_id, summary)
            else:
                Log.warning(f"Could not resolve contact_id for conversation {conversation_id}. Skipping CRM sync.")

        # 7. Update tracking ID (Lock the progress for next summary)
        if tracking_id:
            chat_session_service = ChatSessionService(self.db)
            await chat_session_service.update_tracking_id(
                tenant_id, account_id, conversation_id, tracking_id, status
            )
            Log.success(f"✨ Summarization complete for Conversation {conversation_id}")

    def _calculate_date_range(self, messages: list) -> str:
        """Calculates the date/time range from a list of Chatwoot messages."""
        if not messages:
            return "Unknown Period"

        # Chatwoot created_at is usually Unix timestamp (integer)
        timestamps = []
        for msg in messages:
            ts = msg.get("created_at")
            if ts:
                try:
                    timestamps.append(int(ts))
                except (ValueError, TypeError):
                    continue

        if not timestamps:
            return "Unknown Period"

        start_dt = datetime.fromtimestamp(min(timestamps))
        end_dt = datetime.fromtimestamp(max(timestamps))

        # Format: "Feb 20, 2026 06:00 - 06:45"
        # If the dates are the same day, we can simplify
        if start_dt.date() == end_dt.date():
            return f"{start_dt.strftime('%b %d, %Y %H:%M')} - {end_dt.strftime('%H:%M')}"
        else:
            return f"{start_dt.strftime('%b %d, %Y %H:%M')} - {end_dt.strftime('%b %d, %Y %H:%M')}"

    def _format_messages(self, messages: list) -> str:
        """Formats Chatwoot messages into a clean transcript for the LLM."""
        lines = []
        for msg in messages:
            sender = msg.get("sender", {}).get("name", "Unknown")
            content = msg.get("content") or ""
            if not content:
                continue
            lines.append(f"{sender}: {content}")
        return "\n".join(lines)

    @log_and_ignore(default_return="", log_level="error")
    async def _generate_summary(self, transcript: str, date_range: str) -> str:
        """Invokes the LLM to generate the Veri-Summary."""
        llm = ChatGoogleGenerativeAI(
            model=settings.MODEL,
            temperature=settings.TEMPERATURE,
            google_api_key=settings.GOOGLE_API_KEY
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", VERI_SUMMARY_SYSTEM_PROMPT),
            ("human", "Summary Period: {date_range}\n\nPlease summarize the following conversation:\n\n{transcript}")
        ])

        chain = prompt | llm | StrOutputParser()
        summary = await chain.ainvoke({"transcript": transcript, "date_range": date_range})
        return summary

    async def _push_to_crms(self, tenant_id: int, cw_contact_id: int, summary: str):
        """Finds mapped CRM contacts and adds the summary as a note."""
        # We need to find all mappings for this Chatwoot Contact
        # and push the note to each CRM.
        # Wait, the mapping table uses (tenant_id, chatwoot_contact_id, service_name)

        # 1. Fetch active CRM configs
        integration_service = IntegrationService(self.db)
        configs = await integration_service.get_active_configs(
            tenant_id,
            service_names=["hubspot", "espocrm"]
        )

        for config in configs:
            # 2. Find mapping for this specific CRM
            stmt_mapping = select(ContactMapping.external_id).where(
                ContactMapping.tenant_id == tenant_id,
                ContactMapping.chatwoot_contact_id == cw_contact_id,
                ContactMapping.service_name == config.service_name.lower()
            )
            result_mapping = await self.db.execute(stmt_mapping)
            external_id = result_mapping.scalars().first()

            if not external_id:
                Log.warning(f"No mapping found for {config.service_name} for Chatwoot ID {cw_contact_id}. Skipping note.")
                continue

            # 3. Use adapter to add note
            adapter = CRMFactory.get_adapter(config)
            if adapter:
                await adapter.add_note(external_id, "Conversation Summary", summary)


