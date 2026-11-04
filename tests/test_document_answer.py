import json
import unittest
from unittest.mock import patch

from src.document_answer import select_document_evidence


class LocalDocumentAnswerTests(unittest.TestCase):
    excerpts = [
        {"file": "guide.md", "section": "Data", "excerpt": "Rainfall is measured in millimetres."},
        {"file": "guide.md", "section": "Methods", "excerpt": "The backtest uses rolling forecast origins."},
    ]

    @patch("src.document_answer.HTTPConnection")
    def test_sends_only_question_and_excerpt_text_and_resolves_citations(self, connection):
        response = connection.return_value.getresponse.return_value
        response.status = 200
        response.read.return_value = self.response(["2", "2"])

        selected = select_document_evidence("local-model", "How did you evaluate the model?", self.excerpts)

        self.assertEqual(selected, [self.excerpts[1]])
        connection.assert_called_once_with("127.0.0.1", 11434, timeout=20)
        method, path, body, _ = connection.return_value.request.call_args.args
        self.assertEqual((method, path), ("POST", "/api/chat"))
        request = json.loads(body)
        self.assertEqual(json.loads(request["messages"][1]["content"]), {
            "question": "How did you evaluate the model?",
            "excerpts": {"1": self.excerpts[0]["excerpt"], "2": self.excerpts[1]["excerpt"]},
        })

    @patch("src.document_answer.HTTPConnection")
    def test_unusable_answers_fall_back_to_document_search(self, connection):
        response = connection.return_value.getresponse.return_value
        response.status = 200
        for body in (b"invalid JSON", self.response([]), self.response(["3"]), self.response([1]),
                     self.response(["1", "2", "1"]), self.response(["1"], reason="length"),
                     self.response(["1"], answer="Unverified generated text")):
            with self.subTest(body=body):
                response.read.return_value = body
                self.assertIsNone(select_document_evidence("local-model", "Question", self.excerpts))

    @patch("src.document_answer.HTTPConnection", side_effect=ConnectionRefusedError)
    def test_unavailable_local_service_falls_back(self, _connection):
        self.assertIsNone(select_document_evidence("local-model", "Question", self.excerpts))

    @staticmethod
    def response(source_ids, reason="stop", **extra):
        return json.dumps({"done": True, "done_reason": reason, "message": {
            "content": json.dumps({"source_ids": source_ids, **extra}),
        }}).encode()
