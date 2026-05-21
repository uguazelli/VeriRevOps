import unittest

from src.core.json_utils import parse_json_object


class ParseJsonObjectTests(unittest.TestCase):
    def test_parses_plain_json_object(self):
        result = parse_json_object('{"data": "ok"}', fallback=lambda: {"data": "fallback"})

        self.assertEqual(result, {"data": "ok"})

    def test_parses_embedded_json_object(self):
        result = parse_json_object(
            'Here is the result: {"data": {"answer": "ok"}}',
            fallback=lambda: {"data": "fallback"},
        )

        self.assertEqual(result, {"data": {"answer": "ok"}})

    def test_returns_fallback_for_invalid_json(self):
        result = parse_json_object("not-json", fallback=lambda: {"data": "fallback"})

        self.assertEqual(result, {"data": "fallback"})


if __name__ == "__main__":
    unittest.main()
