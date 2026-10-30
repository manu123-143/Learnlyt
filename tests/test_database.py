import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "test.db")
        self.db.initialize()

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_learning_flow(self):
        subject_id = self.db.create_subject("Cybersecurity", "Security concepts", "#6C5CE7")
        topic_id = self.db.create_topic(subject_id, "Cryptography", "Security", "Medium", "Key concepts")
        card_id = self.db.create_flashcard(topic_id, "What is AES?", "Advanced Encryption Standard")
        self.assertEqual(self.db.dashboard_stats()["due_today"], 1)
        self.assertEqual(self.db.get_topic(topic_id)["card_count"], 1)

        result = self.db.record_review(card_id, 4)
        self.assertTrue(result.remembered)
        self.assertEqual(self.db.get_flashcard(card_id)["correct_count"], 1)
        self.assertEqual(self.db.dashboard_stats()["retention"], 100)

    def test_json_export_and_import(self):
        subject_id = self.db.create_subject("AI")
        topic_id = self.db.create_topic(subject_id, "Neural Networks", "AI", "Hard", "")
        self.db.create_flashcard(topic_id, "What is a neuron?", "A computational unit")
        payload = self.db.export_data()

        second_db = Database(Path(self.temp.name) / "imported.db")
        second_db.initialize()
        counts = second_db.import_data(payload)
        self.assertEqual(counts, {"subjects": 1, "topics": 1, "flashcards": 1})
        self.assertEqual(second_db.dashboard_stats()["flashcards"], 1)

    def test_cascade_delete(self):
        subject_id = self.db.create_subject("Python")
        topic_id = self.db.create_topic(subject_id, "Lists", "Basics", "Easy", "")
        self.db.create_flashcard(topic_id, "Mutable?", "Yes")
        self.db.delete_subject(subject_id)
        self.assertEqual(self.db.dashboard_stats()["topics"], 0)
        self.assertEqual(self.db.dashboard_stats()["flashcards"], 0)


if __name__ == "__main__":
    unittest.main()
