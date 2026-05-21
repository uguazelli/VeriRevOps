import unittest

from src.modules.chatwoot.payload import (
    get_chatwoot_body,
    get_first_attachment_url,
    get_message_kind,
    get_text_message_content,
    process_chatwoot_payload,
)


class ChatwootPayloadTests(unittest.TestCase):
    def test_get_chatwoot_body_accepts_wrapped_payload(self):
        payload = {"body": {"content": "hello"}}

        self.assertEqual(get_chatwoot_body(payload), {"content": "hello"})

    def test_get_chatwoot_body_accepts_raw_payload(self):
        payload = {"content": "hello"}

        self.assertEqual(get_chatwoot_body(payload), payload)

    def test_process_chatwoot_payload_allows_incoming_non_open_public_message(self):
        result = process_chatwoot_payload(
            {
                "conversation": {"status": "pending"},
                "message_type": "incoming",
                "private": False,
                "event": "message_created",
            }
        )

        self.assertEqual(result, {"should_respond": True, "reason": None})

    def test_process_chatwoot_payload_rejects_open_conversation(self):
        result = process_chatwoot_payload(
            {
                "conversation": {"status": "open"},
                "message_type": "incoming",
                "private": False,
                "event": "message_created",
            }
        )

        self.assertEqual(result, {"should_respond": False, "reason": "status open"})

    def test_get_text_message_content_trims_text(self):
        self.assertEqual(get_text_message_content({"content": "  hello  "}), "hello")

    def test_get_message_kind_uses_first_attachment_file_type(self):
        payload = {"attachments": [{"file_type": "image"}]}

        self.assertEqual(get_message_kind(payload), "image")

    def test_get_first_attachment_url_checks_known_url_keys(self):
        payload = {"attachments": [{"download_url": "https://example.com/file.wav"}]}

        self.assertEqual(get_first_attachment_url(payload), "https://example.com/file.wav")


if __name__ == "__main__":
    unittest.main()
