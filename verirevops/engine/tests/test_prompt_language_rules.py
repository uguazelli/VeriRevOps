import unittest

from src.core.prompts import (
    CHATWOOT_CHITCHAT_PROMPT,
    CHATWOOT_HANDOFF_PROMPT,
    CHATWOOT_RAG_RESPONSE_PROMPT,
    RAG_SYSTEM_PROMPT,
    USER_LANGUAGE_RULES,
)
from src.modules.chatwoot.responses import build_chitchat_prompt, build_handoff_prompt


class PromptLanguageRulesTests(unittest.TestCase):
    def test_user_response_prompts_include_language_rules(self):
        prompts = [
            RAG_SYSTEM_PROMPT,
            CHATWOOT_RAG_RESPONSE_PROMPT,
            CHATWOOT_CHITCHAT_PROMPT,
            CHATWOOT_HANDOFF_PROMPT,
        ]

        for prompt in prompts:
            with self.subTest(prompt=prompt[:40]):
                self.assertIn(USER_LANGUAGE_RULES, prompt)
                self.assertIn("Do not mix languages in the same response.", prompt)

    def test_chatwoot_prompts_avoid_english_response_templates(self):
        self.assertNotIn("Based on the information I have", CHATWOOT_RAG_RESPONSE_PROMPT)
        self.assertNotIn("Glad to assist", CHATWOOT_CHITCHAT_PROMPT)
        self.assertNotIn(
            "I want to make sure you get the right answer",
            CHATWOOT_HANDOFF_PROMPT,
        )

    def test_built_chitchat_prompt_keeps_language_rules_near_user_query(self):
        prompt = build_chitchat_prompt("Obrigado")

        self.assertIn("Obrigado", prompt)
        self.assertIn("Detect the user's language from the current user message", prompt)
        self.assertIn("If the user writes in Portuguese", prompt)

    def test_built_handoff_prompt_prioritizes_user_message_language(self):
        prompt = build_handoff_prompt([], "Preciso falar com uma pessoa", "Needs human review")

        self.assertIn("Preciso falar com uma pessoa", prompt)
        self.assertIn("Needs human review", prompt)
        self.assertIn(
            "not from retrieved context, examples, handoff reasons, or system instructions",
            prompt,
        )


if __name__ == "__main__":
    unittest.main()
