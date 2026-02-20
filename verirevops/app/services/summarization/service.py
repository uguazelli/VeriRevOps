from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.config import settings
from app.core.chatwoot import ChatwootClient
from app.core.logger import Log
from app.models import IntegrationConfig, ContactMapping, ChatSession
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

    async def summarize_conversation(self, tenant_id: int, account_id: int, conversation_id: int, status: str, contact_id: Optional[int] = None):
        """
        Main entry point for summarizing a conversation based on its status logic.
        """
        Log.info(f"🚀 Starting summarization for Conversation {conversation_id} (Tenant {tenant_id}, Status: {status})")

        try:
            # 0. Get Session to find last_summarized_message_id
            stmt = select(ChatSession).where(
                ChatSession.tenant_id == tenant_id,
                ChatSession.chatwoot_account_id == account_id,
                ChatSession.chatwoot_conversation_id == conversation_id
            )
            res = await self.db.execute(stmt)
            session = res.scalars().first()

            last_id = session.last_summarized_message_id if session else None

            # 1. Fetch messages from Chatwoot (Source of Truth)
            # Using 'after' to detect new messages only if status is 'resolved'
            if status == "resolved":
                new_messages = await self.chatwoot_client.get_messages(account_id, conversation_id, after=last_id, limit=100)
                if not new_messages:
                    Log.info(f"No new messages since ID {last_id} for resolved conversation. Skipping summarization.")
                    return
                all_messages = await self.chatwoot_client.get_messages(account_id, conversation_id, limit=100)
                if not all_messages:
                    Log.warning(f"Failed to fetch all messages for resolved Conversation {conversation_id}. Aborting.")
                    return
                latest_msg_id = new_messages[-1].get("id")
            else: # status == "open"
                all_messages = await self.chatwoot_client.get_messages(account_id, conversation_id, limit=100)
                if not all_messages:
                    Log.warning(f"Failed to fetch messages for Conversation {conversation_id}. Skipping summarization.")
                    return
                latest_msg_id = None # We don't update tracking ID on 'open'

            # 2. Format transcript for LLM
            transcript = self._format_messages(all_messages)
            if not transcript.strip():
                Log.info(f"No valid transcript content for Conversation {conversation_id}. Skipping.")
                return

            # 3. Generate Summary
            summary = await self._generate_summary(transcript)

            if not summary:
                Log.error("Failed to generate summary.")
                return

            # 4. Push Private Note to Chatwoot
            await self.chatwoot_client.send_message(account_id, conversation_id, summary, private=True)

            # 5. Optional: Push to CRM (Only on Resolve)
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

            # 7. Update tracking ID on 'resolved'
            if status == "resolved" and latest_msg_id:
                if session:
                    session.last_summarized_message_id = latest_msg_id
                else:
                    # Need to create session if it doesn't exist
                    new_session = ChatSession(
                        id=conversation_id,
                        tenant_id=tenant_id,
                        chatwoot_account_id=account_id,
                        chatwoot_conversation_id=conversation_id,
                        last_summarized_message_id=latest_msg_id
                    )
                    self.db.add(new_session)
                await self.db.commit()

            Log.success(f"✨ Summarization complete for Conversation {conversation_id} (Status: {status})")
        except Exception as e:
            Log.error(f"Error in summarize_conversation for {conversation_id}: {e}")
            await self.db.rollback()
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

