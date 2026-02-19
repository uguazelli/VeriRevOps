from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.config import settings
from app.core.chatwoot import ChatwootClient
from app.core.logger import Log
from app.models import IntegrationConfig, ContactMapping, ChatMessage, ChatSession
from app.services.crm.factory import CRMFactory
from app.prompts.llm_prompts import VERI_SUMMARY_SYSTEM_PROMPT

class SummarizationService:
    """
    Service responsible for summarizing Chatwoot conversations
    and pushing them to CRM and Chatwoot nodes.
    """

    def __init__(self, db: AsyncSession, chatwoot_client: ChatwootClient):
        self.db = db
        self.chatwoot_client = chatwoot_client

    async def summarize_conversation(self, tenant_id: int, account_id: int, conversation_id: int, send_to_crm: bool = False, cleanup_history: bool = False):
        """
        Main entry point for summarizing a conversation.
        """
        Log.info(f"🚀 Starting summarization for Conversation {conversation_id} (Tenant {tenant_id})")

        # 0. Get Session to find last_summarized_message_id
        stmt = select(ChatSession).where(ChatSession.id == conversation_id, ChatSession.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        session = res.scalars().first()

        last_id = session.last_summarized_message_id if session else None

        # 1. Fetch messages from Chatwoot (Source of Truth)
        # Using 'after' to detect new messages
        new_messages = await self.chatwoot_client.get_messages(account_id, conversation_id, after=last_id)

        if not new_messages:
            Log.info(f"No new messages since ID {last_id}. Skipping summarization.")
            return

        # Fetch ALL messages for full context summary (or just the new ones + previous summary)
        # For now, let's fetch all to ensure the summary is high quality,
        # but we only trigger because there ARE new ones.
        all_messages = await self.chatwoot_client.get_messages(account_id, conversation_id)

        # 2. Format transcript for LLM
        transcript = self._format_messages(all_messages)

        # 3. Generate Summary
        summary = await self._generate_summary(transcript)

        if not summary:
            Log.error("Failed to generate summary.")
            return

        # 4. Push Private Note to Chatwoot
        await self.chatwoot_client.send_message(account_id, conversation_id, summary, private=True)

        # 5. Optional: Push to CRM
        if send_to_crm:
            # Fetch conversation to get the actual contact_id
            conversation = await self.chatwoot_client.get_conversation(account_id, conversation_id)
            contact_id = conversation.get("contact_id") if conversation else None

            if contact_id:
                await self._push_to_crms(tenant_id, contact_id, summary)
            else:
                Log.warning(f"Could not resolve contact_id for conversation {conversation_id}. Skipping CRM sync.")

        # 6. Optional: Cleanup local ChatMessage history
        if cleanup_history:
            await self._cleanup_local_history(conversation_id)

        # 7. Update tracking ID
        # Get the ID of the last message in current batch
        latest_msg_id = new_messages[-1].get("id")
        if session:
            session.last_summarized_message_id = latest_msg_id
            await self.db.commit()

        Log.success(f"✨ Summarization complete for Conversation {conversation_id} (CRM: {send_to_crm}, Cleanup: {cleanup_history})")

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

    async def _generate_summary(self, transcript: str) -> str:
        """Invokes the LLM to generate the Veri-Summary."""
        try:
            llm = ChatGoogleGenerativeAI(
                model=settings.MODEL,
                temperature=0,
                google_api_key=settings.GOOGLE_API_KEY
            )

            prompt = ChatPromptTemplate.from_messages([
                ("system", VERI_SUMMARY_SYSTEM_PROMPT),
                ("human", "Please summarize the following conversation:\n\n{transcript}")
            ])

            chain = prompt | llm | StrOutputParser()
            summary = await chain.ainvoke({"transcript": transcript})
            return summary
        except Exception as e:
            Log.error(f"LLM Summarization failed: {e}")
            return ""

    async def _push_to_crms(self, tenant_id: int, cw_contact_id: int, summary: str):
        """Finds mapped CRM contacts and adds the summary as a note."""
        # We need to find all mappings for this Chatwoot Contact
        # and push the note to each CRM.
        # Wait, the mapping table uses (tenant_id, chatwoot_contact_id, service_name)

        # 1. Fetch active CRM configs
        stmt_configs = select(IntegrationConfig).where(
            IntegrationConfig.tenant_id == tenant_id,
            IntegrationConfig.is_active == True,
            IntegrationConfig.service_name.in_(["hubspot", "espocrm"])
        )
        result_configs = await self.db.execute(stmt_configs)
        configs = result_configs.scalars().all()

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

    async def _cleanup_local_history(self, conversation_id: int):
        """Deletes local ChatMessage history for the conversation (session_id)."""
        try:
            stmt = delete(ChatMessage).where(ChatMessage.session_id == conversation_id)
            await self.db.execute(stmt)
            await self.db.commit()
            Log.info(f"Cleaned up local history for Session {conversation_id}")
        except Exception as e:
            Log.error(f"Failed to cleanup history for Session {conversation_id}: {e}")
