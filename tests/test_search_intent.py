import unittest

from agent.search_intent import match_search_intent


class SearchIntentTests(unittest.TestCase):
    def test_catches_all_trigger_phrases(self):
        cases = [
            ("find the water bottle", "water bottle"),
            ("search for a bottle", "a bottle"),
            ("find my keys", "keys"),         # "find my" trigger strips "my"
            ("look for the dog", "the dog"),
            ("where is my phone", "my phone"),
            ("where's the remote", "remote"),  # "where's the" trigger strips "the"
            ("locate the bottle", "the bottle"),
            ("find a chair", "chair"),         # "find a" trigger strips "a"
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(match_search_intent(text), expected)

    def test_case_insensitive(self):
        self.assertEqual(match_search_intent("FIND THE BOTTLE"), "bottle")

    def test_strips_trailing_period(self):
        self.assertEqual(match_search_intent("find the bottle."), "bottle")

    def test_returns_none_for_non_search_text(self):
        non_search = [
            "stand up",
            "walk forward",
            "hello",
            "what time is it",
            "stop",
        ]
        for text in non_search:
            with self.subTest(text=text):
                self.assertIsNone(match_search_intent(text))

    def test_returns_none_for_trigger_with_no_target(self):
        self.assertIsNone(match_search_intent("find the"))
        self.assertIsNone(match_search_intent("search for"))


if __name__ == "__main__":
    unittest.main()
