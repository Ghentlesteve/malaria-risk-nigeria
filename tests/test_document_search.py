from pathlib import Path
import unittest

from src.document_search import search_documents


class ProjectEvidenceTests(unittest.TestCase):
    def test_methodology_questions_retrieve_the_relevant_evidence(self):
        root = Path(__file__).resolve().parents[1]
        examples = {
            "How did the backtest prevent future data from leaking into forecasts?":
                "avoids leaking future data",
            "Does rainfall cause more malaria cases?":
                "the association alone cannot show",
            "How do you calculate reporting completeness and timeliness?":
                "completed reports divided by expected reports",
            "How are missing case reports handled?":
                "Missing reports remain missing",
            "Does the dashboard have a live forecast?":
                "A live forecast for a future month is unavailable",
        }
        for question, evidence in examples.items():
            with self.subTest(question=question):
                self.assertTrue(any(evidence in match["excerpt"] for match in search_documents(root, question)))
