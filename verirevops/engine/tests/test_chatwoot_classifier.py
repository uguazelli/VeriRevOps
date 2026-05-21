import unittest

from src.modules.chatwoot.classifier import (
    get_classification_category,
    parse_chatwoot_classification,
)


class ChatwootClassifierTests(unittest.TestCase):
    def test_parse_invalid_json_defaults_to_handoff(self):
        with self.assertLogs("src.modules.chatwoot.classifier", level="ERROR"):
            classification = parse_chatwoot_classification("not-json")

        self.assertEqual(get_classification_category(classification), "HANDOFF")

    def test_low_confidence_classification_requires_handoff(self):
        classification = {
            "data": {
                "category": "RETRIEVAL",
                "confidence": 0.5,
                "allowed_to_answer": True,
                "handoff_required": False,
            }
        }

        self.assertEqual(get_classification_category(classification), "HANDOFF")

    def test_safe_retrieval_classification_keeps_category(self):
        classification = {
            "data": {
                "category": "RETRIEVAL",
                "confidence": 0.9,
                "allowed_to_answer": True,
                "handoff_required": False,
            }
        }

        self.assertEqual(get_classification_category(classification), "RETRIEVAL")

    def test_unknown_category_defaults_to_handoff(self):
        classification = {
            "data": {
                "category": "UNKNOWN",
                "confidence": 0.9,
                "allowed_to_answer": True,
                "handoff_required": False,
            }
        }

        self.assertEqual(get_classification_category(classification), "HANDOFF")


if __name__ == "__main__":
    unittest.main()
