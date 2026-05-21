import unittest
from unittest.mock import patch

from src.modules.ai import factory


class AiFactoryTests(unittest.TestCase):
    def test_normalize_gemini_model_name_adds_models_prefix(self):
        self.assertEqual(
            factory.normalize_gemini_model_name("gemini-2.0-flash"),
            "models/gemini-2.0-flash",
        )

    def test_normalize_gemini_model_name_keeps_existing_models_prefix(self):
        self.assertEqual(
            factory.normalize_gemini_model_name("models/gemini-2.0-flash"),
            "models/gemini-2.0-flash",
        )

    def test_get_openai_async_client_requires_api_key(self):
        factory._openai_async_client = None

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                factory.get_openai_async_client()

    def test_get_gemini_model_requires_api_key(self):
        factory._gemini_model_instances.clear()

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                factory.get_gemini_model("gemini-2.0-flash")


if __name__ == "__main__":
    unittest.main()
