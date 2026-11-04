import unittest

from src.dashboard_questions import CASE_COUNT, COMPARE_REPORTING, match_named_question, resolve_lga


class NamedDashboardQuestionTests(unittest.TestCase):
    def test_comparison_uses_two_locations_and_a_shared_month(self):
        self.assertEqual(
            match_named_question("Compare the reporting rate between Oji River LGA in Enugu and Offa in Kwara for 2025-01"),
            (COMPARE_REPORTING, "2025-01", ("oji river lga in enugu", "offa in kwara")),
        )

    def test_named_case_question_keeps_the_location_and_date(self):
        self.assertEqual(
            match_named_question("How many malaria cases were reported in Oji River in Enugu in 2025-01?"),
            (CASE_COUNT, "2025-01", ("oji river in enugu",)),
        )

    def test_state_disambiguates_without_falling_back_to_a_different_state(self):
        roster = [("a", "Example North Local Government Area", "First State"),
                  ("b", "Example North Local Government Area", "Second State")]
        self.assertEqual(resolve_lga("Example-North LGA in Second State", roster), "b")
        with self.assertRaisesRegex(ValueError, "More than one LGA"):
            resolve_lga("Example North", roster)
        with self.assertRaisesRegex(ValueError, "couldn’t match"):
            resolve_lga("Example North in Third State", roster)
