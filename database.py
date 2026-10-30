"""SQLite persistence layer for LearnLyt."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from pathlib import Path
import sqlite3

from retention import retention_percentage, schedule_review


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "learnlyt.db"


class Database:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self):
        schema = """
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            color TEXT NOT NULL DEFAULT '#6C5CE7',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'General',
            difficulty TEXT NOT NULL DEFAULT 'Medium',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            ease_factor REAL NOT NULL DEFAULT 2.5,
            interval_days INTEGER NOT NULL DEFAULT 0,
            repetitions INTEGER NOT NULL DEFAULT 0,
            next_review TEXT NOT NULL DEFAULT (date('now')),
            last_reviewed TEXT,
            correct_count INTEGER NOT NULL DEFAULT 0,
            incorrect_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS review_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flashcard_id INTEGER NOT NULL,
            quality INTEGER NOT NULL,
            remembered INTEGER NOT NULL,
            reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (flashcard_id) REFERENCES flashcards(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_topics_subject ON topics(subject_id);
        CREATE INDEX IF NOT EXISTS idx_cards_topic ON flashcards(topic_id);
        CREATE INDEX IF NOT EXISTS idx_cards_due ON flashcards(next_review);
        CREATE INDEX IF NOT EXISTS idx_history_reviewed ON review_history(reviewed_at);
        """
        with self.connect() as connection:
            connection.executescript(schema)

    # Subjects
    def create_subject(self, name: str, description: str = "", color: str = "#6C5CE7") -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO subjects (name, description, color) VALUES (?, ?, ?)",
                (name.strip(), description.strip(), color),
            )
            return int(cursor.lastrowid)

    def update_subject(self, subject_id: int, name: str, description: str, color: str):
        with self.connect() as connection:
            return connection.execute(
                "UPDATE subjects SET name=?, description=?, color=? WHERE id=?",
                (name.strip(), description.strip(), color, subject_id),
            ).rowcount > 0

    def get_subject(self, subject_id: int):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM subjects WHERE id=?", (subject_id,)).fetchone()
            return dict(row) if row else None

    def list_subjects(self):
        query = """
        SELECT s.*, COUNT(DISTINCT t.id) AS topic_count,
               COUNT(DISTINCT f.id) AS card_count,
               COALESCE(SUM(f.correct_count), 0) AS correct_count,
               COALESCE(SUM(f.incorrect_count), 0) AS incorrect_count,
               COUNT(DISTINCT CASE WHEN f.next_review <= date('now') THEN f.id END) AS due_count
        FROM subjects s
        LEFT JOIN topics t ON t.subject_id=s.id
        LEFT JOIN flashcards f ON f.topic_id=t.id
        GROUP BY s.id ORDER BY s.created_at DESC, s.id DESC
        """
        with self.connect() as connection:
            subjects = [dict(row) for row in connection.execute(query).fetchall()]
        for subject in subjects:
            subject["retention"] = retention_percentage(subject["correct_count"], subject["incorrect_count"])
        return subjects

    def delete_subject(self, subject_id: int):
        with self.connect() as connection:
            return connection.execute("DELETE FROM subjects WHERE id=?", (subject_id,)).rowcount > 0

    # Topics
    def create_topic(self, subject_id: int, title: str, category: str, difficulty: str, notes: str) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO topics (subject_id,title,category,difficulty,notes) VALUES (?,?,?,?,?)",
                (subject_id, title.strip(), category.strip() or "General", difficulty, notes.strip()),
            )
            return int(cursor.lastrowid)

    def update_topic(self, topic_id: int, subject_id: int, title: str, category: str, difficulty: str, notes: str):
        with self.connect() as connection:
            return connection.execute(
                """UPDATE topics SET subject_id=?,title=?,category=?,difficulty=?,notes=?,
                   updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (subject_id, title.strip(), category.strip() or "General", difficulty, notes.strip(), topic_id),
            ).rowcount > 0

    def get_topic(self, topic_id: int):
        query = """
        SELECT t.*, s.name AS subject_name, s.color AS subject_color,
               COUNT(DISTINCT f.id) AS card_count,
               COALESCE(SUM(f.correct_count),0) AS correct_count,
               COALESCE(SUM(f.incorrect_count),0) AS incorrect_count
        FROM topics t JOIN subjects s ON s.id=t.subject_id
        LEFT JOIN flashcards f ON f.topic_id=t.id
        WHERE t.id=? GROUP BY t.id
        """
        with self.connect() as connection:
            row = connection.execute(query, (topic_id,)).fetchone()
        if not row:
            return None
        topic = dict(row)
        topic["retention"] = retention_percentage(topic["correct_count"], topic["incorrect_count"])
        return topic

    def list_topics(self, subject_id: int | None = None, category: str = "", difficulty: str = "", search: str = ""):
        query = """
        SELECT t.*, s.name AS subject_name, s.color AS subject_color,
               COUNT(DISTINCT f.id) AS card_count,
               COUNT(DISTINCT CASE WHEN f.next_review <= date('now') THEN f.id END) AS due_count,
               COALESCE(SUM(f.correct_count),0) AS correct_count,
               COALESCE(SUM(f.incorrect_count),0) AS incorrect_count
        FROM topics t JOIN subjects s ON s.id=t.subject_id
        LEFT JOIN flashcards f ON f.topic_id=t.id WHERE 1=1
        """
        parameters: list[object] = []
        if subject_id:
            query += " AND t.subject_id=?"
            parameters.append(subject_id)
        if category:
            query += " AND t.category=?"
            parameters.append(category)
        if difficulty:
            query += " AND t.difficulty=?"
            parameters.append(difficulty)
        if search:
            query += " AND (t.title LIKE ? OR t.notes LIKE ?)"
            parameters.extend([f"%{search}%", f"%{search}%"])
        query += " GROUP BY t.id ORDER BY t.updated_at DESC, t.id DESC"
        with self.connect() as connection:
            topics = [dict(row) for row in connection.execute(query, parameters).fetchall()]
        for topic in topics:
            topic["retention"] = retention_percentage(topic["correct_count"], topic["incorrect_count"])
        return topics

    def list_categories(self):
        with self.connect() as connection:
            return [row[0] for row in connection.execute("SELECT DISTINCT category FROM topics ORDER BY category")]

    def delete_topic(self, topic_id: int):
        with self.connect() as connection:
            return connection.execute("DELETE FROM topics WHERE id=?", (topic_id,)).rowcount > 0

    # Flashcards
    def create_flashcard(self, topic_id: int, question: str, answer: str) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO flashcards (topic_id,question,answer) VALUES (?,?,?)",
                (topic_id, question.strip(), answer.strip()),
            )
            return int(cursor.lastrowid)

    def update_flashcard(self, card_id: int, topic_id: int, question: str, answer: str):
        with self.connect() as connection:
            return connection.execute(
                "UPDATE flashcards SET topic_id=?,question=?,answer=? WHERE id=?",
                (topic_id, question.strip(), answer.strip(), card_id),
            ).rowcount > 0

    def get_flashcard(self, card_id: int):
        query = """
        SELECT f.*, t.title AS topic_title, t.subject_id, s.name AS subject_name,
               s.color AS subject_color
        FROM flashcards f JOIN topics t ON t.id=f.topic_id
        JOIN subjects s ON s.id=t.subject_id WHERE f.id=?
        """
        with self.connect() as connection:
            row = connection.execute(query, (card_id,)).fetchone()
        if not row:
            return None
        card = dict(row)
        card["retention"] = retention_percentage(card["correct_count"], card["incorrect_count"])
        return card

    def list_flashcards(self, topic_id: int | None = None):
        query = """
        SELECT f.*, t.title AS topic_title, s.name AS subject_name, s.color AS subject_color
        FROM flashcards f JOIN topics t ON t.id=f.topic_id
        JOIN subjects s ON s.id=t.subject_id
        """
        parameters: list[object] = []
        if topic_id:
            query += " WHERE f.topic_id=?"
            parameters.append(topic_id)
        query += " ORDER BY f.created_at DESC, f.id DESC"
        with self.connect() as connection:
            cards = [dict(row) for row in connection.execute(query, parameters).fetchall()]
        for card in cards:
            card["retention"] = retention_percentage(card["correct_count"], card["incorrect_count"])
        return cards

    def due_flashcards(self, limit: int = 100):
        query = """
        SELECT f.*, t.title AS topic_title, s.name AS subject_name, s.color AS subject_color
        FROM flashcards f JOIN topics t ON t.id=f.topic_id
        JOIN subjects s ON s.id=t.subject_id
        WHERE f.next_review <= date('now')
        ORDER BY f.next_review, f.repetitions, f.id LIMIT ?
        """
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(query, (limit,)).fetchall()]

    def record_review(self, card_id: int, quality: int):
        card = self.get_flashcard(card_id)
        if not card:
            return None
        result = schedule_review(
            quality,
            card["repetitions"],
            card["interval_days"],
            card["ease_factor"],
        )
        with self.connect() as connection:
            connection.execute(
                """UPDATE flashcards SET repetitions=?, interval_days=?, ease_factor=?,
                   next_review=?, last_reviewed=CURRENT_TIMESTAMP,
                   correct_count=correct_count+?, incorrect_count=incorrect_count+? WHERE id=?""",
                (
                    result.repetitions, result.interval_days, result.ease_factor,
                    result.next_review, int(result.remembered), int(not result.remembered), card_id,
                ),
            )
            connection.execute(
                "INSERT INTO review_history (flashcard_id,quality,remembered) VALUES (?,?,?)",
                (card_id, quality, int(result.remembered)),
            )
        return result

    def delete_flashcard(self, card_id: int):
        with self.connect() as connection:
            return connection.execute("DELETE FROM flashcards WHERE id=?", (card_id,)).rowcount > 0

    # Analytics and backup
    def dashboard_stats(self):
        query = """
        SELECT (SELECT COUNT(*) FROM subjects) AS subjects,
               (SELECT COUNT(*) FROM topics) AS topics,
               (SELECT COUNT(*) FROM flashcards) AS flashcards,
               (SELECT COUNT(*) FROM flashcards WHERE next_review <= date('now')) AS due_today,
               COALESCE((SELECT SUM(correct_count) FROM flashcards),0) AS correct,
               COALESCE((SELECT SUM(incorrect_count) FROM flashcards),0) AS incorrect,
               (SELECT COUNT(*) FROM review_history WHERE date(reviewed_at)=date('now')) AS reviewed_today
        """
        with self.connect() as connection:
            result = dict(connection.execute(query).fetchone())
            activity = [dict(row) for row in connection.execute(
                """SELECT date(reviewed_at) AS day, COUNT(*) AS count,
                   SUM(remembered) AS remembered FROM review_history
                   WHERE date(reviewed_at) >= date('now','-6 days')
                   GROUP BY date(reviewed_at) ORDER BY day"""
            ).fetchall()]
        result["retention"] = retention_percentage(result["correct"], result["incorrect"])
        result["activity"] = activity
        return result

    def report_data(self):
        subjects = self.list_subjects()
        weakest = sorted(
            [topic for topic in self.list_topics() if topic["correct_count"] + topic["incorrect_count"] > 0],
            key=lambda item: item["retention"],
        )[:5]
        return {"subjects": subjects, "weakest_topics": weakest, "stats": self.dashboard_stats()}

    def export_data(self):
        with self.connect() as connection:
            return {
                "format": "LearnLyt Backup",
                "version": 1,
                "subjects": [dict(row) for row in connection.execute("SELECT * FROM subjects ORDER BY id")],
                "topics": [dict(row) for row in connection.execute("SELECT * FROM topics ORDER BY id")],
                "flashcards": [dict(row) for row in connection.execute("SELECT * FROM flashcards ORDER BY id")],
                "review_history": [dict(row) for row in connection.execute("SELECT * FROM review_history ORDER BY id")],
            }

    def import_data(self, payload: dict):
        if payload.get("format") != "LearnLyt Backup" or payload.get("version") != 1:
            raise ValueError("This is not a supported LearnLyt backup file.")
        subject_map: dict[int, int] = {}
        topic_map: dict[int, int] = {}
        card_map: dict[int, int] = {}
        with self.connect() as connection:
            for item in payload.get("subjects", []):
                base_name = str(item["name"]).strip()
                candidate = base_name
                suffix = 2
                while connection.execute("SELECT 1 FROM subjects WHERE name=?", (candidate,)).fetchone():
                    candidate = f"{base_name} (Imported {suffix})"
                    suffix += 1
                cursor = connection.execute(
                    "INSERT INTO subjects (name,description,color) VALUES (?,?,?)",
                    (candidate, item.get("description", ""), item.get("color", "#6C5CE7")),
                )
                subject_map[int(item["id"])] = int(cursor.lastrowid)
            for item in payload.get("topics", []):
                if int(item["subject_id"]) not in subject_map:
                    continue
                cursor = connection.execute(
                    "INSERT INTO topics (subject_id,title,category,difficulty,notes) VALUES (?,?,?,?,?)",
                    (subject_map[int(item["subject_id"])], item["title"], item.get("category", "General"), item.get("difficulty", "Medium"), item.get("notes", "")),
                )
                topic_map[int(item["id"])] = int(cursor.lastrowid)
            for item in payload.get("flashcards", []):
                if int(item["topic_id"]) not in topic_map:
                    continue
                cursor = connection.execute(
                    """INSERT INTO flashcards (topic_id,question,answer,ease_factor,interval_days,
                       repetitions,next_review,last_reviewed,correct_count,incorrect_count)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (topic_map[int(item["topic_id"])], item["question"], item["answer"], item.get("ease_factor",2.5), item.get("interval_days",0), item.get("repetitions",0), item.get("next_review",date.today().isoformat()), item.get("last_reviewed"), item.get("correct_count",0), item.get("incorrect_count",0)),
                )
                card_map[int(item["id"])] = int(cursor.lastrowid)
            for item in payload.get("review_history", []):
                if int(item["flashcard_id"]) in card_map:
                    connection.execute(
                        "INSERT INTO review_history (flashcard_id,quality,remembered,reviewed_at) VALUES (?,?,?,?)",
                        (card_map[int(item["flashcard_id"])], item["quality"], item["remembered"], item.get("reviewed_at")),
                    )
        return {"subjects": len(subject_map), "topics": len(topic_map), "flashcards": len(card_map)}
