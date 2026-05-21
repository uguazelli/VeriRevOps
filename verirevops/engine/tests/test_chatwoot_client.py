import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from src.modules.chatwoot.client import (
    ChatwootApiContext,
    get_chatwoot_api_context,
    get_response_text,
)


class ChatwootClientTests(unittest.TestCase):
    def test_get_response_text_reads_standard_response_data(self):
        self.assertEqual(get_response_text({"data": "  hello  "}), "hello")

    def test_get_response_text_serializes_non_string_data(self):
        self.assertEqual(get_response_text({"data": {"answer": "ok"}}), '{"answer": "ok"}')

    def test_get_response_text_returns_empty_string_for_missing_data(self):
        self.assertEqual(get_response_text({"reason": "empty"}), "")

    def test_chatwoot_api_context_builds_conversation_urls(self):
        context = ChatwootApiContext(
            base_url="https://chatwoot.example.com",
            account_id="7",
            api_key="secret",
        )

        self.assertEqual(
            context.conversation_url(42, "messages"),
            "https://chatwoot.example.com/api/v1/accounts/7/conversations/42/messages",
        )

    def test_get_chatwoot_api_context_validates_service_config(self):
        tenant_settings = SimpleNamespace(tenant=SimpleNamespace(services={}))

        with self.assertRaises(HTTPException):
            get_chatwoot_api_context(tenant_settings)


if __name__ == "__main__":
    unittest.main()
